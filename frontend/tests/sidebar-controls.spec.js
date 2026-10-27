import { test, expect } from '@playwright/test';
import { user } from './helpers';

test.beforeEach(async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.route('**/api/documents?*', route => route.fulfill({ json: [{ id: 41, original_filename: 'recent.pdf', ai_label: 'Research', folder_id: null }] }));
  await page.route('**/api/folders?*', route => route.fulfill({ json: [{ id: 1, name: 'Existing folder' }] }));
});

test('sidebar replaces new document with a focused, creation-only folder form', async ({ page }) => {
  await page.route('**/api/folders', route => {
    expect(route.request().postDataJSON()).toEqual({ name: 'New folder' });
    return route.fulfill({ status: 201, json: { id: 2, name: 'New folder' } });
  });
  await page.goto('/workspace');
  const sidebar = page.getByRole('complementary');
  await expect(sidebar.getByRole('button', { name: 'Recents', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('button', { name: 'Tài liệu mới', exact: true })).toHaveCount(0);
  await sidebar.locator('[aria-controls="create-folder-panel"]').click();
  const form = sidebar.getByRole('form', { name: 'Tạo thư mục', exact: true });
  await expect(form.getByLabel('Tên thư mục mới')).toBeFocused();
  await expect(form.locator('select')).toHaveCount(0);
  await expect(sidebar.locator('#workspace-folder-select')).toHaveCount(0);
  await form.getByLabel('Tên thư mục mới').fill(' New folder ');
  await form.getByRole('button', { name: 'Tạo thư mục', exact: true }).click();
  await expect(sidebar.getByRole('button', { name: 'Mở thư mục New folder', exact: true })).toBeVisible();
  await expect(form.getByLabel('Tên thư mục mới')).toHaveValue('');
});

test('sidebar buttons and history links keep their colors on hover', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/workspace');
  const sidebar = page.getByRole('complementary');
  const items = [sidebar.locator('[aria-controls="create-folder-panel"]'), sidebar.getByRole('button', { name: 'Mở thư mục Existing folder', exact: true }), sidebar.getByRole('button', { name: 'Recents', exact: true }), sidebar.getByRole('link', { name: 'recent.pdf', exact: true })];
  for (const item of items) {
    await expect(item).toBeVisible();
    const before = await item.evaluate(el => ({ background: getComputedStyle(el).backgroundColor, color: getComputedStyle(el).color, icon: getComputedStyle(el.querySelector('svg')).color }));
    await item.hover();
    await expect(item).toHaveCSS('background-color', before.background);
    await expect(item).toHaveCSS('color', before.color);
    await expect(item.locator('svg')).toHaveCSS('color', before.icon);
  }
});
