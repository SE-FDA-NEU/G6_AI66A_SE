import { createHmac } from 'node:crypto';
import { test, expect } from '@playwright/test';
import { user } from './helpers';

const protectedPaths = [
  '/workspace', '/workspace?tab=documents', '/upload',
  '/results', '/results/7', '/results/7/export',
  '/documents', '/documents/42', '/documents/42/source.pdf',
];

// Sign fixtures with the key used only by serve_auth_e2e.py, never a local .env.
function token(exp, key = 'isolated-playwright-test-key-not-for-production') {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ sub: '1', exp })).toString('base64url');
  const signature = createHmac('sha256', key).update(`${header}.${payload}`).digest('base64url');
  return `${header}.${payload}.${signature}`;
}

test('fresh browser session opening workspace returns to sign-in', async ({ page, context }) => {
  expect(await context.cookies()).toEqual([]);
  await page.goto('/workspace');
  await expect(page).toHaveURL('/');
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Đăng nhập', exact: true })).toBeVisible();
});

test('missing token redirects every protected route before rendering', async ({ request }) => {
  for (const path of protectedPaths) {
    const response = await request.get(path, { maxRedirects: 0 });
    expect(response.status(), path).toBe(307);
    expect(new URL(response.headers().location, response.url()).pathname, path).toBe('/');
    expect(response.headers()['cache-control'], path).toBe('no-store');
  }
});

for (const kind of ['expired', 'forged']) {
  test(`${kind} JWT redirects every protected route`, async ({ page, context, baseURL }) => {
    const now = Math.floor(Date.now() / 1000);
    const value = kind === 'expired' ? token(now - 60) : token(now + 3600, 'wrong-test-signing-key');
    // Keep the cookie alive so the guard must verify the JWT itself.
    await context.addCookies([{ name: 'documind_session', value, url: baseURL, httpOnly: true, expires: now + 3600 }]);
    expect((await context.cookies()).find(c => c.name === 'documind_session')?.value).toBe(value);
    expect((await page.request.get('/auth/me')).status()).toBe(401);
    for (const path of protectedPaths) {
      const response = await page.request.get(path, { maxRedirects: 0 });
      expect(response.status(), path).toBe(307);
      expect(new URL(response.headers().location, response.url()).pathname, path).toBe('/');
    }
    await page.goto('/workspace');
    await expect(page).toHaveURL('/');
  });
}

test('valid session passes the guard for all protected routes', async ({ request }) => {
  const login = await request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(login.status()).toBe(200);
  for (const path of protectedPaths) {
    const response = await request.get(path, { maxRedirects: 0 });
    // Upload/results/reader pages belong to later tasks and currently return 404.
    expect(response.status(), path).toBe(path.startsWith('/workspace') ? 200 : 404);
    expect(response.headers().location, path).toBeUndefined();
  }
});

test('landing and auth endpoints remain public', async ({ request }) => {
  expect((await request.get('/', { maxRedirects: 0 })).status()).toBe(200);
  expect((await request.get('/auth/me', { maxRedirects: 0 })).status()).toBe(401);
  const response = await request.post('/auth/login', { form: { username: user.email, password: 'incorrect-password' } });
  expect(response.status()).toBe(401);
});
