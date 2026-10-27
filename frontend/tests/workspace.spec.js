import { test, expect } from '@playwright/test';
import { user } from './helpers';

test.beforeEach(async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.route('**/api/folders?*', route => route.fulfill({ json: [] }));
});
const docs = [{ id: 41, original_filename: 'contract.pdf', ai_label: 'Contract', user_label: 'Hợp đồng', folder_id: null },
  { id: 42, original_filename: 'notes.docx', ai_label: 'Research', folder_id: null }];

test('upload is the main view; history is in the sidebar with label titles and source links', async ({ page }, info) => {
  await page.route('**/api/documents?*', route => route.fulfill({ json: docs }));
  await page.goto('/workspace');
  const main = page.getByRole('main');
  const side = page.getByRole('complementary');
  await expect(main.getByRole('heading', { name: 'Bạn muốn khám phá điều gì?' })).toBeVisible();
  await expect(main.getByRole('button', { name: 'Chọn tệp tài liệu' })).toBeVisible();
  await expect(main.getByTestId('workspace-document-row')).toHaveCount(0);
  await expect(side.getByTestId('workspace-document-row')).toHaveCount(2);
  await expect(side.getByRole('link', { name: 'contract.pdf', exact: true })).toContainText('Hợp đồng');
  await expect(side.getByRole('link', { name: 'contract.pdf', exact: true })).toHaveAttribute('href', '/documents/41?page=1');
  await expect(page.locator('.workspace-search, .workspace-label-filter')).toHaveCount(0);
  await expect(page.getByLabel('Tìm kiếm trong tài liệu', { exact: true })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath('workspace-desktop.png'), fullPage: true });
});

test('history reads all metadata pages and searches labels beyond the visible history page', async ({ page }) => {
  const all = Array.from({ length: 101 }, (_, i) => ({ id: i + 1, original_filename: `file-${i}.pdf`, ai_label: i === 100 ? 'Special research' : 'Contract' }));
  const skips = [];
  await page.route('**/api/documents?*', route => {
    const params = new URL(route.request().url()).searchParams;
    const skip = Number(params.get('skip')); skips.push(skip);
    return route.fulfill({ json: all.slice(skip, skip + Number(params.get('limit'))) });
  });
  await page.goto('/workspace');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(10);
  await page.getByRole('navigation', { name: 'Phân trang tài liệu' }).getByRole('button', { name: 'Trang sau' }).click();
  await expect(page.getByTestId('workspace-document-row').first()).toHaveAttribute('data-document-id', '11');
  await page.getByLabel('Tìm lịch sử theo nhãn').fill('special');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(1);
  await expect(page.getByTestId('workspace-document-row')).toHaveAttribute('data-document-id', '101');
  expect(skips).toEqual([0, 100]);
});

test('history errors offer retry without preventing upload', async ({ page }) => {
  let calls = 0;
  await page.route('**/api/documents?*', route => ++calls === 1 ? route.fulfill({ status: 503 }) : route.fulfill({ json: docs }));
  await page.goto('/workspace');
  await expect(page.getByRole('complementary').getByRole('alert')).toContainText('Không thể tải danh sách');
  await expect(page.getByLabel('Chọn tệp tài liệu', { exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Thử lại danh sách' }).click();
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(2);
});

test('home upload retains selection after failure and sends the existing upload payload', async ({ page }) => {
  await page.route('**/api/documents?*', route => route.fulfill({ json: [] }));
  let calls = 0;
  await page.route('**/api/upload', route => {
    const body = route.request().postDataBuffer().toString();
    expect(body).toContain('name="files"; filename="notes.pdf"');
    expect(body).toContain('name="mode"\r\n\r\nconcept');
    expect(body).toContain('name="language"\r\n\r\nvi');
    return ++calls === 1 ? route.fulfill({ status: 503 }) : route.fulfill({ json: { jobId: 801 } });
  });
  await page.route('**/jobs/801', route => route.fulfill({ json: { id: 801, status: 'completed', completed_count: 1, file_count: 1, job_files: [] } }));
  await page.goto('/workspace');
  await expect(page.getByRole('button', { name: 'Tải lên và phân tích' })).toBeDisabled();
  await page.getByLabel('Chọn tệp tài liệu', { exact: true }).setInputFiles({ name: 'notes.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') });
  await page.getByRole('button', { name: 'Hiểu các khái niệm' }).click();
  await page.getByRole('button', { name: 'Tải lên và phân tích' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Không thể gửi tài liệu');
  await expect(page.locator('.upload-files')).toContainText('notes.pdf');
  await expect(page.getByRole('button', { name: 'Hiểu các khái niệm' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Tải lên và phân tích' }).click();
  await expect(page).toHaveURL('/results/801');
  expect(calls).toBe(2);
});

test('mobile starts with upload and expands history without horizontal overflow', async ({ page }, info) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.route('**/api/documents?*', route => route.fulfill({ json: docs }));
  await page.goto('/workspace');
  await expect(page.getByLabel('Tìm lịch sử theo nhãn')).toBeHidden();
  await page.getByRole('button', { name: 'Mở lịch sử' }).click();
  await expect(page.getByLabel('Tìm lịch sử theo nhãn')).toBeVisible();
  await page.locator('[aria-controls="create-folder-panel"]').click();
  await expect(page.getByLabel('Tên thư mục mới')).toBeFocused();
  await page.getByRole('button', { name: 'Đóng lịch sử' }).click();
  await expect(page.getByRole('button', { name: 'Mở lịch sử' })).toHaveAttribute('aria-expanded', 'false');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('workspace-mobile.png'), fullPage: true });
});
