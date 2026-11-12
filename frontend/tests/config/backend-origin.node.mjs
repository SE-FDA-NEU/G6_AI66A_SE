import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getBackendOrigin, backendRewrites, assertBuiltBackend } from '../../lib/backend-origin.mjs';

test('production rejects missing, local and malformed backend origins', () => {
  for (const value of ['', 'http://localhost:8001', 'http://LOCALHOST.:8001',
    'http://127.1:8001', 'http://0.0.0.0:8001', 'http://[::1]:8001',
    'http://[::ffff:127.0.0.1]:8001', 'ftp://backend.example.com',
    'https://backend.example.com/api', 'https://backend.example.com?x=1',
    'https://backend.example.com/#x', 'https://user:secret@backend.example.com']) {
    assert.throws(() => getBackendOrigin({ BACKEND_ORIGIN: value }, true), undefined, value);
  }
});

test('development retains local fallback; production normalizes explicit origins', () => {
  assert.equal(getBackendOrigin({}, false), 'http://127.0.0.1:8001');
  assert.equal(getBackendOrigin({ BACKEND_ORIGIN: ' https://backend.example.com/ ' }, true), 'https://backend.example.com');
  assert.equal(getBackendOrigin({ BACKEND_ORIGIN: 'http://backend:8001' }, true), 'http://backend:8001');
});

test('runtime must agree with every baked-in proxy destination', () => {
  const origin = 'https://backend.example.com';
  const rules = backendRewrites(origin);
  assertBuiltBackend({ beforeFiles: [], afterFiles: rules, fallback: [] }, origin);
  assert.throws(() => assertBuiltBackend(rules, 'https://another.example.com'), /Rebuild/);
  for (let index = 0; index < rules.length; index++) {
    assert.throws(() => assertBuiltBackend(rules.filter((_, i) => i !== index), origin), /Rebuild/);
  }
});
