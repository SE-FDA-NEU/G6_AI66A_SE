import { test, expect } from '@playwright/test';
import { user } from './helpers';

const folders = [{ id: 1, name: 'Hợp đồng' }, { id: 2, name: 'Báo cáo' }];
const documents = [
  { id: 41, original_filename: 'contract-2026.pdf', ai_label: 'Contract', ai_confidence: .9, folder_id: 1 },
  { id: 42, original_filename: 'budget.docx', ai_label: 'Budget', folder_id: null },
];

test.beforeEach(async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.route('**/api/folders?*', route => route.fulfill({ json: folders }));
  await page.route('**/api/documents?*', route => {
    const params = new URL(route.request().url()).searchParams;
    return route.fulfill({ json: documents.filter(doc => (!params.get('folder_id') || doc.folder_id === Number(params.get('folder_id')))
      && (!params.get('unassigned') || doc.folder_id == null)
      && (!params.get('filename') || doc.original_filename.includes(params.get('filename')))) });
  });
});

test('folder tiles, sidebar, breadcrumbs and browser history open the same folder', async ({ page }) => {
  await page.goto('/workspace');
  await expect(page.getByRole('button', { name: /^Mở thư mục / })).toHaveCount(2);
  await page.getByRole('button', { name: 'Mở thư mục Hợp đồng', exact: true }).click();
  await expect(page).toHaveURL('/workspace?folder=1');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(1);
  await expect(page.getByRole('navigation', { name: 'Điều hướng thư viện' }).getByRole('button', { name: 'Hợp đồng', exact: true })).toHaveAttribute('aria-current', 'page');
  await page.reload();
  await expect(page.getByLabel('Đường dẫn thư mục')).toContainText('Hợp đồng');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(1);
  await page.getByLabel('Đường dẫn thư mục').getByRole('button', { name: 'Thư viện', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Mở thư mục Báo cáo', exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByLabel('Thư mục hiển thị', { exact: true })).toHaveValue('1');
});

test('unassigned is a filter; filename search sends its scope and leaves content search independent', async ({ page }) => {
  await page.goto('/workspace');
  await page.getByLabel('Điều hướng thư viện').getByRole('button', { name: 'Chưa phân thư mục', exact: true }).click();
  await expect(page).toHaveURL('/workspace?folder=unassigned');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(1);
  await expect(page.getByTestId('workspace-document-row')).toContainText('budget.docx');
  await page.getByLabel('Tìm theo tên tệp', { exact: true }).fill('missing');
  const request = page.waitForRequest(r => r.url().includes('/api/documents?') && r.url().includes('filename=missing'));
  await page.getByRole('button', { name: 'Tìm tệp', exact: true }).click();
  expect(new URL((await request).url()).searchParams.get('unassigned')).toBe('true');
  await expect(page.getByText('Không tìm thấy tệp có tên chứa “missing”.', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Tìm kiếm trong tài liệu', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Xóa tên tệp', exact: true }).click();
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(1);
  await page.getByLabel('Điều hướng thư viện').getByRole('button', { name: 'Tất cả tài liệu', exact: true }).click();
  await expect(page.getByRole('button', { name: /^Mở thư mục / })).toHaveCount(2);
});

test('mobile folder panel toggles and closes after opening a folder without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/workspace');
  const toggle = page.getByRole('button', { name: 'Mở thư mục', exact: true });
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await toggle.click();
  await page.getByLabel('Điều hướng thư viện').getByRole('button', { name: 'Báo cáo', exact: true }).click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByLabel('Đường dẫn thư mục')).toContainText('Báo cáo');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
