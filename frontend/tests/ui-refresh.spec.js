import { test, expect } from '@playwright/test';
import { user } from './helpers';

test('industrial landing exposes login, six modules and keyboard-operable demo tabs', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
  await expect(page.locator('#modules article')).toHaveCount(6);
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(9, 9, 11)');
  const first = page.getByRole('tab', { name: /SUMMARY/ });
  await first.focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('tab', { name: /CLAUSES/ })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('tabpanel')).toContainText('120.000.000 VND');
  await page.getByRole('tab', { name: /SOURCES/ }).click();
  await expect(page.getByRole('tabpanel')).toContainText('source_matched');
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: testInfo.outputPath('landing-desktop.png'), fullPage: true });
});

test('library keeps existing document and folder APIs in the new desktop and mobile layout', async ({ page }, testInfo) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.route('**/api/folders?*', route => route.fulfill({ json: [{ id: 1, name: 'Hợp đồng' }, { id: 2, name: 'Nghiên cứu' }] }));
  await page.route('**/api/documents?*', route => route.fulfill({ json: [
    { id: 71, original_filename: 'Hop_dong_dich_vu_2026.pdf', file_format: 'PDF', ai_label: 'Hợp đồng', ai_confidence: .92, folder_id: 1 },
    { id: 72, original_filename: 'Research_notes.docx', file_format: 'DOCX', ai_label: 'Nghiên cứu', ai_confidence: .76, folder_id: 2 },
  ] }));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/workspace');
  await page.getByRole('button', { name: 'Danh sách trong Hợp đồng', exact: true }).click();
  await page.getByRole('button', { name: 'Danh sách trong Nghiên cứu', exact: true }).click();
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(2);
  await page.screenshot({ path: testInfo.outputPath('library-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.getByRole('button', { name: 'Mở lịch sử', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('library-mobile.png'), fullPage: true });
});

test('upload has a clear two-step workflow without changing submission endpoints', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.goto('/upload');
  await expect(page.getByRole('navigation', { name: 'Các bước làm việc' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Chọn hoặc kéo thả tệp vào đây' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Tải lên và phân tích', exact: true })).toBeDisabled();
});

test('buttons invert black and white on hover and restore their original colors', async ({ page }) => {
  await page.goto('/');
  const primary = page.locator('button.primary').first();
  const secondary = page.locator('a.btn:not(.primary)').first();
  await expect(primary).toBeEnabled();
  await expect(primary).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await primary.hover();
  await expect(primary).toHaveCSS('background-color', 'rgb(9, 9, 11)');
  await expect(primary).toHaveCSS('color', 'rgb(255, 255, 255)');
  await secondary.hover();
  await expect(primary).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await expect(secondary).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await expect(secondary).toHaveCSS('color', 'rgb(0, 0, 0)');
  await page.mouse.move(0, 0);
  await expect(secondary).toHaveCSS('background-color', 'rgb(9, 9, 11)');
});

test('beginner guide explains the first action and remembers when it is hidden', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.goto('/upload');
  const guide = page.getByRole('region', { name: 'Hướng dẫn sử dụng trang này' });
  await expect(guide.getByRole('heading', { name: 'Đọc nhanh', exact: true })).toBeVisible();
  await guide.getByRole('button', { name: 'Ẩn hướng dẫn' }).click();
  await expect(guide.getByRole('button', { name: 'Mở hướng dẫn' })).toHaveAttribute('aria-expanded', 'false');
  await page.reload();
  await expect(guide.getByRole('button', { name: 'Mở hướng dẫn' })).toHaveAttribute('aria-expanded', 'false');
  await guide.getByRole('button', { name: 'Mở hướng dẫn' }).click();
  await expect(guide.getByRole('heading', { name: 'Đọc nhanh', exact: true })).toBeVisible();
  await expect(guide.getByRole('heading', { name: 'So sánh hợp đồng' })).toBeVisible();
  await expect(guide.getByRole('heading', { name: 'Học và nghiên cứu' })).toBeVisible();
});
