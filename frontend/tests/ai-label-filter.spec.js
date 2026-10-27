import { test, expect } from '@playwright/test';
import { user } from './helpers';

test('label history search matches partial AI/user labels without accents and excludes filename-only matches', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.route('**/api/folders?*', route => route.fulfill({ json: [] }));
  await page.route('**/api/documents?*', route => route.fulfill({ json: [
    { id: 1, original_filename: 'first.pdf', ai_label: 'Contract', user_label: 'Hợp đồng dịch vụ' },
    { id: 2, original_filename: 'second.pdf', ai_label: 'Hợp đồng thuê' },
    { id: 3, original_filename: 'hop dong.pdf', ai_label: 'Research' },
  ] }));
  let searches = 0;
  await page.route('**/api/search?*', route => { searches++; return route.abort(); });
  await page.goto('/workspace');
  const input = page.getByLabel('Tìm lịch sử theo nhãn');
  await input.fill('HOP DONG');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(2);
  await input.fill('contract');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(1);
  await input.fill('absent');
  await expect(page.getByText('Không tìm thấy nhãn phù hợp. Thử một từ khác.')).toBeVisible();
  await page.getByRole('button', { name: 'Xóa tìm kiếm nhãn' }).click();
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(3);
  expect(searches).toBe(0);
});
