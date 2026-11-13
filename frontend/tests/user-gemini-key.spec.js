import { test, expect } from '@playwright/test';
import { user } from './helpers';

test.beforeEach(async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.request.delete('/auth/gemini-key');
});

test('upload saves a personal key and never persists plaintext in browser storage', async ({ page }) => {
  await page.goto('/upload');
  await page.getByLabel('Chọn tệp tài liệu').setInputFiles({
    name: 'report.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-test'),
  });
  const submit = page.getByRole('button', { name: 'Tải lên và phân tích' });
  const input = page.locator('#gemini-api-key');
  await expect(submit).toBeDisabled();
  await expect(input).toHaveAttribute('type', 'password');
  await input.fill('personal-ui-key');
  await expect(submit).toBeEnabled();
  let sent = false;
  await page.route('**/api/upload', async route => {
    const request = route.request();
    expect(request.headers()['x-gemini-api-key']).toBe('personal-ui-key');
    expect(request.url()).not.toContain('personal-ui-key');
    expect(request.postData()).not.toContain('personal-ui-key');
    sent = true;
    await route.fulfill({ status: 400, json: { detail: 'Enter your Gemini API key to analyze documents.' } });
  });
  await submit.click();
  await expect(page.locator('.upload-page').getByRole('alert')).toContainText('Nhập Gemini API key');
  expect(sent).toBe(true);
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain('personal-ui-key');
  await page.reload();
  await expect(input).toHaveValue('');
  await expect(page.getByText('Đã lưu API key vào tài khoản.', { exact: false })).toBeVisible();
});

test('personal key help follows the selected language', async ({ page }) => {
  await page.goto('/upload');
  await page.getByLabel('Ngôn ngữ').selectOption('en');
  await expect(page.getByLabel('Your Gemini API key')).toBeVisible();
  await expect(page.getByText('Your key is saved encrypted to your account', { exact: false })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Get a Gemini API key' })).toHaveAttribute('href', 'https://aistudio.google.com/api-keys');
});

test('save, replace and remove a key across reloads without revealing it', async ({ page }) => {
  await page.goto('/upload');
  const input = page.locator('#gemini-api-key');
  await input.fill('first-ui-private-key');
  await page.getByRole('button', { name: 'Lưu API key', exact: true }).click();
  await expect(input).toHaveValue('');
  await page.reload();
  await expect(page.getByText('Đã lưu API key vào tài khoản.', { exact: false })).toBeVisible();
  await input.fill('second-ui-private-key');
  await page.getByRole('button', { name: 'Đổi API key', exact: true }).click();
  await expect(input).toHaveValue('');
  await page.reload();
  await expect(input).toHaveValue('');
  await page.getByLabel('Chọn tệp tài liệu').setInputFiles({ name: 'source.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-test') });
  await expect(page.getByRole('button', { name: 'Tải lên và phân tích' })).toBeEnabled();
  expect(await (await page.request.get('/auth/gemini-key')).json()).toEqual({ configured: true });
  await page.getByRole('button', { name: 'Xóa key đã lưu', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Tải lên và phân tích' })).toBeDisabled();
  await page.reload();
  expect(await (await page.request.get('/auth/gemini-key')).json()).toEqual({ configured: false });
});

for (const [code, expected] of [
  ['gemini_configuration_error', 'Gemini API key của bạn không hợp lệ'],
  ['gemini_quota_exceeded', 'Gemini key của bạn đã chạm hạn mức'],
  ['gemini_unavailable', 'Gemini tạm thời không khả dụng'],
  ['gemini_incomplete_response', 'Gemini chưa trả về bản tóm tắt đầy đủ'],
]) {
  test(`explains ${code} without exposing raw provider details`, async ({ page }) => {
    await page.route('**/jobs/778', route => route.fulfill({ json: {
      id: 778, mode: 'bullet', status: 'failed', file_count: 1, completed_count: 0,
      result_data: null,
      job_files: [{ id: 1, document_id: 17, original_filename: 'report.pdf',
        status: 'failed', attempt_count: 1, error_message: `${code}: private provider detail` }],
    } }));
    await page.goto('/results/778');
    await expect(page.locator('.job-file-error')).toContainText(expected);
    await expect(page.locator('main')).not.toContainText('private provider detail');
  });
}
