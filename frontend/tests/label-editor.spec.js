import { test, expect } from '@playwright/test';
import { user } from './helpers';

test.beforeEach(async ({ page }) => {
  expect((await page.request.post('/auth/login', { form: { username: user.email, password: user.password } })).status()).toBe(200);
});

test('real workspace confirmation at 79/80 and reader edits persist after reload without changing AI or folders', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: 'review@example.com', password: user.password } });
  const documents = await (await page.request.get('/api/documents')).json();
  expect(documents).toHaveLength(2);
  await page.goto('/workspace');
  for (const document of documents) {
    const row = page.locator(`[data-testid="workspace-document-row"][data-document-id="${document.id}"]`);
    const confidence = row.getByTestId('document-ai-confidence');
    await expect(confidence).toContainText(document.ai_confidence === .79 ? '79%' : '80%');
    await expect(confidence).toHaveAttribute('data-confidence-level', document.ai_confidence === .79 ? 'low' : 'high');
    await expect(row.getByTestId('document-review-state')).not.toContainText('Đã xác nhận');
    await row.getByRole('button', { name: 'Xác nhận nhãn AI', exact: true }).click();
    await expect(row.getByTestId('document-review-state')).toContainText('Đã xác nhận');
    await expect(row.getByTestId('document-user-label')).toContainText('Macroeconomics');
    await expect(row.getByTestId('document-user-decision')).toHaveText('Người dùng đã xác nhận gợi ý AI');
    await expect(row.getByTestId('document-folder-placement')).toContainText('Economics 101');
  }
  await page.reload();
  await expect(page.getByTestId('document-user-label')).toHaveCount(2);
  const original = documents.find(document => document.ai_confidence === .79);
  const row = page.locator(`[data-testid="workspace-document-row"][data-document-id="${original.id}"]`);
  await row.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  await row.getByLabel('Nhãn người dùng', { exact: true }).fill('My reviewed classification');
  await row.getByRole('button', { name: 'Lưu nhãn', exact: true }).click();
  await expect(row.getByTestId('document-user-label')).toContainText('My reviewed classification');
  await expect(row.getByTestId('document-user-decision')).toHaveText('Người dùng đã chỉnh sửa và xác nhận');
  await page.reload();
  await expect(row.getByTestId('document-user-label')).toContainText('My reviewed classification');
  await row.getByRole('link').click();
  await page.getByRole('combobox', { name: 'Chọn trang nguồn', exact: true }).selectOption('2');
  const metadata = page.locator('.reader-document-metadata');
  await expect(metadata.getByTestId('document-ai-label')).toContainText('Macroeconomics');
  await expect(metadata.getByTestId('document-user-label')).toContainText('My reviewed classification');
  await page.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  await page.getByLabel('Nhãn người dùng', { exact: true }).fill('Reader classification');
  await page.getByRole('button', { name: 'Lưu nhãn', exact: true }).click();
  await expect(metadata.getByTestId('document-user-label')).toContainText('Reader classification');
  await expect(page.getByText('Trang 2/2', { exact: true })).toBeVisible();
  await page.reload();
  await expect(metadata.getByTestId('document-user-label')).toContainText('Reader classification');
  await expect(metadata.getByTestId('document-ai-confidence')).toContainText('79%');
  await expect(metadata.getByTestId('document-folder-placement')).toHaveAttribute('data-folder-id', String(original.folder_id));
  const saved = (await (await page.request.get('/api/documents')).json()).find(document => document.id === original.id);
  expect(saved).toEqual({ ...original, user_label: 'Reader classification', review_state: 'confirmed',
    last_accessed_at: saved.last_accessed_at, expires_at: saved.expires_at });
  expect(new Date(saved.expires_at + 'Z') - new Date(saved.last_accessed_at + 'Z')).toBe(30 * 86400000);
  expect(new Date(saved.last_accessed_at + 'Z').getTime()).toBeGreaterThanOrEqual(new Date(original.last_accessed_at + 'Z').getTime());
});

test('pending/error preserves the draft and metadata; retry saves only human fields and cancel writes nothing', async ({ page }) => {
  let saved = { id: 77, original_filename: 'review.pdf', ai_label: 'Macroeconomics', ai_confidence: .79,
    user_label: null, review_state: 'needs_review', folder_id: 5 };
  await page.route('**/api/folders?*', route => route.fulfill({ json: [{ id: 5, name: 'Economics 101' }] }));
  await page.route('**/api/documents?*', route => route.fulfill({ json: [saved] }));
  let calls = 0;
  let release;
  await page.route('**/api/documents/77/label', async route => {
    expect(route.request().postDataJSON()).toEqual({ user_label: 'My correction', review_state: 'confirmed' });
    if (++calls === 1) {
      await new Promise(resolve => { release = resolve; });
      return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    }
    saved = { ...saved, user_label: 'My correction', review_state: 'confirmed' };
    return route.fulfill({ json: saved });
  });
  await page.goto('/workspace');
  const row = page.getByTestId('workspace-document-row');
  await row.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  const input = row.getByLabel('Nhãn người dùng', { exact: true });
  await expect(input).toHaveValue('Macroeconomics');
  await expect(input).toHaveAttribute('maxlength', '100');
  await input.fill('  ');
  await expect(row.getByRole('button', { name: 'Lưu nhãn', exact: true })).toBeDisabled();
  await input.fill('My correction');
  await row.getByRole('button', { name: 'Lưu nhãn', exact: true }).click();
  await expect.poll(() => typeof release).toBe('function');
  await expect(input).toBeDisabled();
  await expect(row.getByRole('button', { name: 'Đang lưu…', exact: true })).toBeDisabled();
  await expect(row.getByRole('button', { name: 'Hủy chỉnh sửa', exact: true })).toBeDisabled();
  await expect(row.getByTestId('document-user-label')).toHaveCount(0);
  release();
  await expect(row.getByRole('alert')).toContainText('Không thể lưu nhãn');
  await expect(input).toHaveValue('My correction');
  await expect(row.getByTestId('document-ai-label')).toContainText('Macroeconomics');
  await expect(row.getByTestId('document-folder-placement')).toContainText('Economics 101');
  await row.getByRole('button', { name: 'Lưu nhãn', exact: true }).click();
  await expect(row.getByTestId('document-user-label')).toContainText('My correction');
  await expect(row.getByTestId('document-ai-confidence')).toContainText('79%');
  await row.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  await input.fill('Unsaved changes');
  await row.getByRole('button', { name: 'Hủy chỉnh sửa', exact: true }).click();
  await row.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  await expect(input).toHaveValue('My correction');
  expect(calls).toBe(2);
});

test('reader save failure keeps the source page, draft and original suggestion without false confirmation', async ({ page }) => {
  const version = 'a'.repeat(64);
  await page.route('**/api/documents/99/pages', route => route.fulfill({ json: { original_filename: 'source.pdf',
    page_count: 2, page_kind: 'page', reader_version: version, reader_url: `/documents/99/reader.pdf?version=${version}`,
    pages: [{ page: 1, text: 'First page' }, { page: 2, text: 'Second page' }],
    ai_label: 'Macroeconomics', ai_confidence: .8, folder_id: 5, user_label: null, review_state: 'needs_review' } }));
  await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF' }));
  await page.route('**/api/documents/99/label', route => route.fulfill({ status: 404, json: { detail: 'Document not found' } }));
  await page.goto('/documents/99?page=2');
  await page.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  await page.getByLabel('Nhãn người dùng', { exact: true }).fill('My draft');
  await page.getByRole('button', { name: 'Lưu nhãn', exact: true }).click();
  await expect(page.getByTestId('document-label-editor').getByRole('alert')).toContainText('Không thể lưu nhãn');
  await expect(page.getByLabel('Nhãn người dùng', { exact: true })).toHaveValue('My draft');
  await expect(page.getByTestId('document-review-state')).not.toContainText('Đã xác nhận');
  await expect(page.getByText('Trang 2/2', { exact: true })).toBeVisible();
  await expect(page.getByTestId('document-ai-label')).toContainText('Macroeconomics');
});
