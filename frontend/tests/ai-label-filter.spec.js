import { test, expect } from '@playwright/test';
import { user } from './helpers';

test.beforeEach(async ({ page }) => {
  expect((await page.request.post('/auth/login', { form: { username: 'label@example.com', password: user.password } })).status()).toBe(200);
});

test('real API filters eight of twenty across folders and clearing restores both unfiltered pages', async ({ page }) => {
  const requests = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname === '/api/documents') requests.push(Object.fromEntries(url.searchParams));
  });
  await page.goto('/workspace');
  const rows = page.getByTestId('workspace-document-row');
  const pagination = page.getByRole('navigation', { name: 'Phân trang tài liệu', exact: true });
  await expect(rows).toHaveCount(10);
  await expect(rows.getByTestId('document-ai-label').first()).toContainText('Microeconomics');
  await pagination.getByRole('button', { name: 'Trang sau' }).click();
  await expect(pagination).toContainText('Trang 2');
  const filter = page.getByRole('region', { name: 'Lọc danh sách tài liệu', exact: true });
  await filter.getByLabel('Nhãn AI hiển thị', { exact: true }).fill('Macroeconomics');
  await filter.getByRole('button', { name: 'Áp dụng nhãn AI', exact: true }).click();
  await expect(rows).toHaveCount(8);
  expect(requests.at(-1)).toEqual({ skip: '0', limit: '11', label: 'Macroeconomics' });
  await expect(rows.getByTestId('document-ai-label')).toHaveText(Array(8).fill('Nhãn AI: Macroeconomics'));
  await expect(rows.getByTestId('document-user-label')).toHaveText(Array(8).fill('Nhãn người dùng: User correction'));
  const placements = await rows.getByTestId('document-folder-placement').allTextContents();
  expect(placements.some(text => text.includes('Economics 101'))).toBe(true);
  expect(placements.some(text => text.includes('Research'))).toBe(true);
  await filter.getByRole('button', { name: 'Xóa lọc nhãn AI', exact: true }).click();
  await expect(rows).toHaveCount(10);
  expect(requests.at(-1)).toEqual({ skip: '0', limit: '11' });
  const firstIds = await rows.evaluateAll(elements => elements.map(element => element.dataset.documentId));
  await pagination.getByRole('button', { name: 'Trang sau' }).click();
  await expect(pagination).toContainText('Trang 2');
  await expect(rows).toHaveCount(10);
  const secondIds = await rows.evaluateAll(elements => elements.map(element => element.dataset.documentId));
  expect(new Set([...firstIds, ...secondIds]).size).toBe(20);
  await expect(pagination.getByRole('button', { name: 'Trang sau' })).toBeDisabled();
});

test('combined folder/AI label is explicit AND; clear-label preserves the folder and clear-all removes both', async ({ page }) => {
  const folders = await (await page.request.get('/api/folders')).json();
  const folder = folders.find(item => item.name === 'Economics 101');
  await page.goto('/workspace');
  await page.getByLabel('Thư mục hiển thị', { exact: true }).selectOption(String(folder.id));
  const filter = page.getByRole('region', { name: 'Lọc danh sách tài liệu', exact: true });
  await filter.getByLabel('Nhãn AI hiển thị', { exact: true }).fill('Macroeconomics');
  await filter.getByRole('button', { name: 'Áp dụng nhãn AI', exact: true }).click();
  const rows = page.getByTestId('workspace-document-row');
  await expect(rows).toHaveCount(4);
  await expect(filter.getByRole('status')).toContainText('Macroeconomics');
  await expect(filter.getByRole('status')).toContainText('Economics 101');
  await expect(filter).toContainText('tài liệu phải khớp đồng thời cả hai');
  await filter.getByRole('button', { name: 'Xóa lọc nhãn AI', exact: true }).click();
  await expect(rows).toHaveCount(10);
  await expect(page.getByLabel('Thư mục hiển thị', { exact: true })).toHaveValue(String(folder.id));
  await filter.getByRole('button', { name: 'Xóa lọc danh sách', exact: true }).click();
  await expect(page.getByLabel('Thư mục hiển thị', { exact: true })).toHaveValue('');
  await expect(filter.getByRole('status')).toHaveText('Tất cả nhãn AI · Tất cả thư mục');
  await expect(page.getByRole('navigation', { name: 'Phân trang tài liệu', exact: true })).toBeVisible();
});

test('unmatched AI label has a filter-specific empty message and clear restores documents', async ({ page }) => {
  await page.goto('/workspace');
  const filter = page.getByRole('region', { name: 'Lọc danh sách tài liệu', exact: true });
  await filter.getByLabel('Nhãn AI hiển thị', { exact: true }).fill('macroeconomics');
  await filter.getByRole('button', { name: 'Áp dụng nhãn AI', exact: true }).click();
  await expect(page.getByText('Không có tài liệu khớp nhãn AI đã chọn.', { exact: true })).toBeVisible();
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(0);
  await filter.getByRole('button', { name: 'Xóa lọc danh sách', exact: true }).click();
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(10);
});

test('filter values survive loading/error and retry uses the same exact query', async ({ page }) => {
  let attempts = 0;
  let release;
  await page.route('**/api/documents?*', async route => {
    const params = new URL(route.request().url()).searchParams;
    if (params.get('label')) {
      expect(params.get('label')).toBe('Macroeconomics');
      expect(params.get('skip')).toBe('0');
      if (++attempts === 1) {
        await new Promise(resolve => { release = resolve; });
        return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
      }
    }
    return route.fulfill({ json: [] });
  });
  await page.goto('/workspace');
  const filter = page.getByRole('region', { name: 'Lọc danh sách tài liệu', exact: true });
  const input = filter.getByLabel('Nhãn AI hiển thị', { exact: true });
  await input.fill('Macroeconomics');
  await filter.getByRole('button', { name: 'Áp dụng nhãn AI', exact: true }).click();
  await expect.poll(() => typeof release).toBe('function');
  await expect(page.getByText('Đang tải danh sách tài liệu…')).toBeVisible();
  await expect(input).toHaveValue('Macroeconomics');
  release();
  await expect(page.locator('.workspace-documents').getByRole('alert')).toContainText('Không thể tải danh sách');
  await page.getByRole('button', { name: 'Thử lại danh sách', exact: true }).click();
  await expect(page.getByText('Không có tài liệu khớp nhãn AI đã chọn.', { exact: true })).toBeVisible();
  expect(attempts).toBe(2);
});
