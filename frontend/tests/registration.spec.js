import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { user } from './helpers';

async function openRegistration(page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Đăng ký', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Tạo tài khoản DocuMind' })).toBeVisible();
}

test('register, persist session, logout and sign in with the new account', async ({ page, context }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openRegistration(page);
  await page.screenshot({ path: 'test-results/registration-mobile.png', fullPage: true });
  const identity = `member_${randomUUID().replaceAll('-', '').slice(0, 12)}`;
  const email = `${identity}@example.com`;
  const secret = randomUUID();
  await page.getByLabel('Tên tài khoản', { exact: true }).fill(identity);
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Mật khẩu', { exact: true }).fill(secret);
  await page.getByLabel('Xác nhận mật khẩu', { exact: true }).fill(`${secret}different`);
  await page.getByRole('button', { name: 'Đăng ký', exact: true }).click();
  await expect(page.locator('#login-error')).toContainText('Mật khẩu xác nhận không khớp.');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel('Xác nhận mật khẩu', { exact: true }).fill(secret);
  await page.getByRole('button', { name: 'Đăng ký', exact: true }).click();
  await expect(page).toHaveURL('/workspace');
  expect((await context.cookies()).find(c => c.name === 'documind_session')?.httpOnly).toBe(true);
  await page.reload();
  await page.getByRole('button', { name: 'Mở lịch sử', exact: true }).click();
  await expect(page.getByRole('complementary')).toContainText(email);
  await page.getByRole('button', { name: 'Mở menu điều hướng', exact: true }).click();
  await page.getByRole('button', { name: 'Đăng xuất' }).click();
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Mật khẩu', { exact: true }).fill(secret);
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await expect(page).toHaveURL('/workspace');
});

test('duplicate account shows an error and allows returning to login', async ({ page }) => {
  await openRegistration(page);
  await page.getByLabel('Tên tài khoản', { exact: true }).fill(`duplicate_${randomUUID().slice(0, 8)}`);
  await page.getByLabel('Email', { exact: true }).fill(user.email);
  await page.getByLabel('Mật khẩu', { exact: true }).fill(user.password);
  await page.getByLabel('Xác nhận mật khẩu', { exact: true }).fill(user.password);
  await page.getByRole('button', { name: 'Đăng ký', exact: true }).click();
  await expect(page.locator('#login-error')).toContainText('Email hoặc tên tài khoản đã được sử dụng.');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await expect(page.getByLabel('Xác nhận mật khẩu', { exact: true })).toHaveCount(0);
  await expect(page.locator('#login-error')).toBeEmpty();
});

test('registration validation is localized in English', async ({ page, context }) => {
  await context.addCookies([{ name: 'documind_language', value: 'en', url: 'http://127.0.0.1:18000' }]);
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign up', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Create your DocuMind account' })).toBeVisible();
  await page.getByLabel('Username', { exact: true }).fill('english_member');
  await page.getByLabel('Email', { exact: true }).fill('english@example.com');
  await page.getByLabel('Password', { exact: true }).fill(randomUUID());
  await page.getByLabel('Confirm password', { exact: true }).fill(randomUUID());
  await page.getByRole('button', { name: 'Sign up', exact: true }).click();
  await expect(page.locator('#login-error')).toContainText('Passwords do not match.');
});
