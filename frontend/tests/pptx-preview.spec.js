import { readFile } from 'node:fs/promises';
import { test, expect } from '@playwright/test';
import { user } from './helpers';
const version = 'a'.repeat(64);
const file = await readFile(new URL('./fixtures/visual-preview.pptx', import.meta.url));
test.beforeEach(async ({ page }) => {
  expect((await page.request.post('/auth/login', { form: { username: user.email, password: user.password } })).status()).toBe(200);
  await page.route('**/api/documents/703/pages', route => route.fulfill({ json: {
    file_format: 'PPTX', reader_layout: 'text', page_kind: 'slide', page_count: 3,
    reader_version: version, reader_url: `/documents/703/reader.pdf?version=${version}`,
    original_filename: 'visual-preview.pptx',
    pages: [1, 2, 3].map(page => ({ page, text: page === 3 ? '' : 'Saved source text.', positions: [] })),
  } }));
  await page.route('**/api/documents/703/summary*', route => route.fulfill({ json: { document: null } }));
  await page.route('**/api/documents/703/file', route => route.fulfill({ contentType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', body: file }));
});

test('renders real PPTX images and positioned text; navigates hidden/blank slides without a converter', async ({ page }) => {
  await page.goto('/documents/703');
  const preview = page.getByTestId('pptx-preview');
  await expect(preview).toHaveAttribute('data-status', 'ready');
  const frame = page.frameLocator('[data-testid="pptx-preview"] iframe');
  await expect(frame.getByText('Preview slide one', { exact: true })).toBeVisible();
  await expect(frame.locator('img')).toHaveCount(1);
  await expect(frame.locator('img')).toBeVisible();
  await expect(preview.locator('iframe')).toHaveAttribute('sandbox', 'allow-scripts');
  const sandboxed = await frame.locator('body').evaluate(() => {
    try { return Boolean(parent.document); } catch { return false; }
  });
  expect(sandboxed).toBe(false);
  await page.getByRole('button', { name: 'Sau', exact: true }).click();
  await expect(frame.getByText('Hidden slide two', { exact: true })).toBeVisible();
  await expect(frame.locator('canvas, svg').first()).toBeVisible();
  await expect(frame.locator('body')).not.toContainText('PRIVATE SPEAKER NOTES');
  await page.getByLabel('Chọn trang nguồn').selectOption('3');
  await expect(preview.locator('iframe')).toHaveAttribute('title', 'Trang chiếu PowerPoint 3');
  await expect(frame.locator('.pptx-preview-slide-wrapper-2')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sau', exact: true })).toBeDisabled();
  await page.setViewportSize({ width: 375, height: 812 });
  expect((await preview.locator('iframe').boundingBox()).width).toBeLessThanOrEqual(375);
  await page.getByRole('button', { name: 'Mở bản đọc văn bản', exact: true }).click();
  await expect(page.locator('iframe.reader-pdf')).toHaveAttribute('src', /reader.pdf.*#page=3/);
  await expect(preview).toHaveCount(0);
});

test('corrupt PPTX provides localized fallback instead of a blank preview', async ({ page }) => {
  await page.route('**/api/documents/703/file', route => route.fulfill({ body: 'not a zip file' }));
  await page.goto('/documents/703');
  await expect(page.getByTestId('pptx-preview')).toHaveAttribute('data-status', 'error');
  await expect(page.getByTestId('pptx-preview').getByRole('alert')).toContainText('Không thể hiển thị trang chiếu');
  await page.getByLabel('Ngôn ngữ').selectOption('en');
  await expect(page.getByTestId('pptx-preview').getByRole('alert')).toContainText('This slide could not be previewed');
  await expect(page.getByRole('link', { name: 'Download original PowerPoint' })).toHaveAttribute('href', '/api/documents/703/file');
  await page.getByTestId('pptx-preview').getByRole('alert').getByRole('button', { name: 'Open text reader' }).click();
  await expect(page.locator('iframe.reader-pdf')).toBeVisible();
});
