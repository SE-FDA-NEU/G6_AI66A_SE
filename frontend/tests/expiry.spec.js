import { test, expect } from '@playwright/test';
import { openWorkspaceControls, user } from './helpers';

const old = { id: 61, original_filename: 'march-contract.pdf', ai_label: 'Contract', ai_confidence: .9,
  review_state: 'needs_review', folder_id: null, last_accessed_at: '2026-03-01T00:00:00', expires_at: '2026-03-31T00:00:00' };

test.beforeEach(async ({ page }) => {
  expect((await page.request.post('/auth/login', { form: { username: user.email, password: user.password } })).status()).toBe(200);
});

async function list(page, getDocument = () => old) {
  await page.route('**/api/documents?*', route => route.fulfill({ json: [getDocument()] }));
  await page.goto('/workspace');
  await openWorkspaceControls(page);
}

test('March 1 access has March 31 expiry, with seven-day warning starting exactly March 24 UTC', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-03-23T23:59:59Z') });
  await list(page);
  await expect(page.getByTestId('document-expiry')).toContainText('31/03/2026');
  await expect(page.getByTestId('expiry-warning')).toHaveCount(0);
  await page.clock.fastForward(1000);
  await expect(page.getByTestId('expiry-warning')).toContainText('Sắp hết hạn');
  await expect(page.locator('time')).toHaveAttribute('datetime', '2026-03-31T00:00:00.000Z');
  await page.reload();
  await openWorkspaceControls(page);
  await expect(page.getByTestId('expiry-warning')).toBeVisible();
});

test('UTC dates are stable in another browser timezone; elapsed and unknown dates are explicit', async ({ browser }) => {
  const context = await browser.newContext({ timezoneId: 'America/Los_Angeles' });
  const page = await context.newPage();
  try {
    await page.request.post('http://127.0.0.1:18000/auth/login', { form: { username: user.email, password: user.password } });
    await page.clock.install({ time: new Date('2026-03-31T00:00:00Z') });
    await page.route('**/api/documents?*', route => route.fulfill({ json: [old, { ...old, id: 62, expires_at: 'invalid' }] }));
    await page.goto('http://127.0.0.1:18000/workspace');
    await openWorkspaceControls(page);
    await expect(page.getByTestId('document-expiry').first()).toContainText('31/03/2026');
    await expect(page.getByTestId('expiry-elapsed')).toContainText('Đã tới hạn lưu');
    await expect(page.getByTestId('expiry-warning')).toHaveCount(0);
    await expect(page.getByTestId('document-expiry').last()).toHaveText('Chưa có ngày hết hạn.');
  } finally { await context.close(); }
});

test('workspace refetches metadata on return from another tab without opening or renewing the listed documents', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-03-24T12:00:00Z') });
  let current = old;
  let opens = 0;
  await page.route('**/api/documents/61', route => { opens++; return route.abort(); });
  await list(page, () => current);
  await expect(page.getByTestId('expiry-warning')).toBeVisible();
  current = { ...old, last_accessed_at: '2026-03-25T12:00:00', expires_at: '2026-04-24T12:00:00' };
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await page.clock.fastForward(100);
  await expect(page.getByTestId('document-expiry')).toContainText('24/04/2026');
  await expect(page.getByTestId('expiry-warning')).toHaveCount(0);
  expect(opens).toBe(0);
});

test('real label and folder updates refresh persisted expiry in workspace and reader without losing the current page', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: 'expiry@example.com', password: user.password } });
  const docs = await (await page.request.get('/api/documents')).json();
  const doc = docs.find(item => item.ai_confidence === .79);
  await page.goto('/workspace');
  await openWorkspaceControls(page);
  const row = page.locator(`[data-document-id="${doc.id}"]`);
  await row.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  await row.getByLabel('Nhãn người dùng', { exact: true }).fill('Retention review');
  const updated = page.waitForResponse(response => response.url().endsWith(`/documents/${doc.id}/label`) && response.request().method() === 'PATCH');
  await row.getByRole('button', { name: 'Lưu nhãn', exact: true }).click();
  const label = await (await updated).json();
  await expect(row.locator('time')).toHaveAttribute('datetime', new Date(`${label.expires_at}Z`).toISOString());
  const moving = page.waitForResponse(response => response.url().endsWith(`/documents/${doc.id}/folder`) && response.request().method() === 'PATCH');
  await row.getByRole('button', { name: 'Bỏ thư mục', exact: true }).click();
  const moved = await (await moving).json();
  await expect(row.locator('time')).toHaveAttribute('datetime', new Date(`${moved.expires_at}Z`).toISOString());
  await page.goto(`/documents/${doc.id}?page=2`);
  await expect(page.getByText('Trang 2/2', { exact: true })).toBeVisible();
  const afterOpen = await (await page.request.get(`/api/documents/${doc.id}/pages`)).json();
  expect(new Date(afterOpen.expires_at + 'Z') - new Date(afterOpen.last_accessed_at + 'Z')).toBe(30 * 86400000);
  await expect(page.getByTestId('document-expiry')).not.toContainText('Chưa có');
  await page.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  await page.getByLabel('Nhãn người dùng', { exact: true }).fill('Reader retention');
  const saving = page.waitForResponse(response => response.url().endsWith(`/documents/${doc.id}/label`) && response.request().method() === 'PATCH');
  await page.getByRole('button', { name: 'Lưu nhãn', exact: true }).click();
  const saved = await (await saving).json();
  await expect(page.locator('time')).toHaveAttribute('datetime', new Date(saved.expires_at + 'Z').toISOString());
  await expect(page.getByText('Trang 2/2', { exact: true })).toBeVisible();
});

test('reader revalidation clears previously visible content when the source expires', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: 'expiry@example.com', password: user.password } });
  const [doc] = await (await page.request.get('/api/documents')).json();
  await page.goto(`/documents/${doc.id}`);
  await expect(page.locator('iframe')).toBeVisible();
  await page.route(`**/api/documents/${doc.id}/pages`, route => route.fulfill({ status: 410,
    json: { detail: { code: 'source_expired', message: 'Source expired.' } } }));
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await expect(page.locator('main').getByRole('alert')).toContainText('Nguồn đã hết hạn');
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.getByTestId('document-label-editor')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Chuẩn bị bản đọc', exact: true })).toHaveCount(0);
});

test('returning to terminal results revalidates expiry, hides old facts and disables export', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: 'export@example.com', password: user.password } });
  const completed = await (await page.request.get('/jobs/9002')).json();
  await page.goto('/results/9002');
  await expect(page.getByRole('button', { name: 'Xuất bảng', exact: true })).toBeEnabled();
  const expired = structuredClone(completed);
  expired.job_files[0].status = 'failed';
  expired.job_files[0].error_message = 'source_expired: Source expired and is no longer available.';
  expired.status = 'failed'; expired.completed_count = 4;
  // Even a stale saved snapshot must not surface after source_expired is known.
  await page.route('**/jobs/9002', route => route.fulfill({ json: expired }));
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await expect(page.locator('main').getByRole('alert')).toContainText('Nguồn đã hết hạn');
  await expect(page.getByText('1,200,000,000 VND', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /— page/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Xuất bảng', exact: true })).toBeDisabled();
});

test('reader removes the old source if it expires during a label update', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: 'expiry@example.com', password: user.password } });
  const [doc] = await (await page.request.get('/api/documents')).json();
  await page.goto(`/documents/${doc.id}?page=2`);
  await expect(page.locator('iframe')).toBeVisible();
  await page.route(`**/api/documents/${doc.id}/label`, route => route.fulfill({ status: 410,
    json: { detail: { code: 'source_expired' } } }));
  await page.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).click();
  await page.getByLabel('Nhãn người dùng', { exact: true }).fill('Expired edit');
  await page.getByRole('button', { name: 'Lưu nhãn', exact: true }).click();
  await expect(page.locator('main').getByRole('alert')).toContainText('Nguồn đã hết hạn');
  await expect(page.locator('iframe')).toHaveCount(0);
});
