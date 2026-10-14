import { test, expect } from '@playwright/test';
import { login, user } from './helpers';

test('email sign-in errors, HttpOnly session, persistence and logout', async ({ page, context }) => {
  await login(page, { ...user, password: 'incorrect-password' });
  await expect(page.locator('.auth-form').getByRole('alert')).toContainText('Email hoặc mật khẩu không đúng');
  await expect(page.getByRole('button', { name: 'Đăng nhập', exact: true })).toBeEnabled();
  await expect(page).toHaveURL('/');
  expect((await context.cookies()).some(c => c.name === 'documind_session')).toBe(false);

  // Retry the same form after an error, exercising the real FastAPI login.
  await page.getByLabel('Mật khẩu', { exact: true }).fill(user.password);
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await expect(page).toHaveURL('/workspace');
  await expect(page.getByRole('heading', { name: 'Không gian tài liệu' })).toBeVisible();
  await expect(page.getByText(`Bạn đã đăng nhập với ${user.email}.`)).toBeVisible();
  const cookie = (await context.cookies()).find(c => c.name === 'documind_session');
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe('Lax');
  expect(await page.evaluate(() => document.cookie.includes('documind_session'))).toBe(false);
  expect(await page.evaluate(() => localStorage.getItem('documind_token'))).toBeNull();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Không gian tài liệu' })).toBeVisible();
  await page.goto('/');
  await expect(page).toHaveURL('/workspace');
  await page.getByRole('button', { name: 'Đăng xuất' }).click();
  await expect(page).toHaveURL('/');
  expect((await context.cookies()).some(c => c.name === 'documind_session')).toBe(false);
  expect((await page.request.get('/workspace', { maxRedirects: 0 })).status()).toBe(307);
});

test('guests and forged cookies cannot open workspace', async ({ page, context }) => {
  await page.goto('/workspace');
  await expect(page).toHaveURL('/');
  await context.addCookies([{ name: 'documind_session', value: 'forged-token', url: 'http://127.0.0.1:18000' }]);
  await page.goto('/workspace');
  await expect(page).toHaveURL('/');
  expect((await page.request.get('/auth/me')).status()).toBe(401);
});

test('unknown email returns the same inline error', async ({ page }) => {
  await login(page, { ...user, email: 'unknown@example.com' });
  await expect(page.locator('.auth-form').getByRole('alert')).toContainText('Email hoặc mật khẩu không đúng');
  await expect(page).toHaveURL('/');
});

test('connection failure shows a retryable inline message', async ({ page }) => {
  await page.route('**/auth/login', route => route.abort('failed'));
  await login(page);
  await expect(page.locator('.auth-form').getByRole('alert')).toContainText('Không thể kết nối máy chủ');
  await expect(page.getByRole('button', { name: 'Đăng nhập', exact: true })).toBeEnabled();
});

test('email validation prevents invalid form submission', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('invalid-email');
  await page.getByLabel('Mật khẩu', { exact: true }).fill(user.password);
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  expect(await page.getByLabel('Email', { exact: true }).evaluate(el => el.validity.typeMismatch)).toBe(true);
  await expect(page).toHaveURL('/');
});

test('mobile landing fits viewport and can sign in', async ({ page }) => {
  await page.goto('/');
  await page.screenshot({ path: 'test-results/landing-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Biến tài liệu thành/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/landing-mobile.png', fullPage: true });
  await login(page);
  await expect(page).toHaveURL('/workspace');
});

test('legacy username login remains compatible with API clients', async ({ request }) => {
  const response = await request.post('/auth/login', { form: { username: 'playwright_user', password: user.password } });
  expect(response.status()).toBe(200);
  expect((await response.json()).token_type).toBe('bearer');
  const me = await request.get('/auth/me');
  expect(me.status()).toBe(200);
  expect((await me.json()).email).toBe(user.email);
});
