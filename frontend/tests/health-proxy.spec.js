import { test, expect } from '@playwright/test';

test('public frontend health proxies backend readiness instead of returning a page 404', async ({ request }) => {
  const origin = process.env.HEALTH_TEST_BACKEND_ORIGIN || 'http://127.0.0.1:18001';
  const backend = await request.get(`${origin}/health`);
  const frontend = await request.get('/health');
  // Preserve the real backend status, including 503 for an unavailable DB.
  expect([200, 503]).toContain(backend.status());
  expect(frontend.status()).toBe(backend.status());
  expect(await frontend.json()).toEqual(await backend.json());
  expect(frontend.headers()['cache-control']).toBe('no-store');
});
