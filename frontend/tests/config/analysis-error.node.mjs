import { test } from 'node:test';
import assert from 'node:assert/strict';
import { analysisErrorText } from '../../lib/analysis-error.mjs';
const t = (text, ...values) => text.replace(/\{(\d+)\}/g, (_, i) => values[i]);
for (const [code, expected] of [
  ['renderer_unavailable', 'LibreOffice'], ['gemini_daily_quota_exceeded', 'daily'], ['gemini_quota_exceeded', 'HTTP 429'],
  ['gemini_output_limit', 'MAX_TOKENS'], ['gemini_context_limit', 'context'],
  ['gemini_invalid_response', 'JSON'], ['gemini_incomplete_response', 'major topics'],
  ['gemini_unavailable', 'server/overload'], ['gemini_connection_failed', 'network'],
  ['gemini_blocked', 'blocked'], ['invalid_result', 'citations'],
]) test(`specific safe error for ${code}`, () => {
  const text = analysisErrorText(`${code}: private-source-and-key`, t);
  assert.ok(text.includes(expected));
  assert.ok(!text.includes('private-source-and-key'));
});
test('provider, document and BR deadlines are distinct', () => {
  assert.match(analysisErrorText('gemini_request_timeout: Gemini request exceeded 45 seconds.', t), /45 seconds per request/);
  assert.match(analysisErrorText('Processing timed out after 3 attempts (102 seconds per attempt).', t), /102 seconds per attempt/);
  assert.match(analysisErrorText('Bullet processing exceeded the 180-second target.', t), /BR processing deadline of 180/);
  assert.match(analysisErrorText('Contract batch processing exceeded the 300-second target.', t), /BR processing deadline of 300/);
  assert.equal(analysisErrorText('unknown: private provider text', t), null);
});
