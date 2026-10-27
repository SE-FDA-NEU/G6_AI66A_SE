import { test, expect } from '@playwright/test';
import { user } from './helpers';

function pdfFixture() {
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 1 /Kids [4 0 R] >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>',
    `<< /Length 20 >>\nstream\nBT /F1 12 Tf ET\nendstream`,
  ];
  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${offsets.length}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) {
    pdf += `${String(offset).padStart(10, '0')} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf);
}

test('folder upload assigns every file before processing; leaving the folder uploads outside after reload', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: 'workspace@example.com', password: user.password } });
  const created = await page.request.post('/api/folders', { data: { name: 'Auto upload folder' } });
  expect(created.status()).toBe(201);
  const folder = await created.json();
  await page.goto(`/workspace?folder=${folder.id}`);
  await expect(page.getByRole('status').filter({ hasText: 'Tài liệu mới sẽ được lưu' })).toContainText(folder.name);
  const chooser = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Chọn tệp tài liệu', exact: true }).click();
  await (await chooser).setFiles(['first.pdf', 'second.pdf'].map(name => ({ name, mimeType: 'application/pdf', buffer: pdfFixture() })));
  const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/upload' && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Tải lên và phân tích' }).click();
  const uploaded = await response;
  expect(uploaded.status()).toBe(202);
  await expect(page).toHaveURL(/\/results\/[1-9]\d*$/);
  const saved = await (await page.request.get(`/api/documents?folder_id=${folder.id}`)).json();
  expect(saved.map(doc => doc.original_filename).sort()).toEqual(['first.pdf', 'second.pdf']);
  expect(saved.every(doc => doc.folder_id === folder.id)).toBe(true);
  await page.goto(`/workspace?folder=${folder.id}`);
  const group = page.locator(`[data-folder-id="${folder.id}"]`);
  await expect(group.getByTestId('workspace-document-row')).toHaveCount(2);
  await page.reload();
  await expect(group.getByTestId('workspace-document-row')).toHaveCount(2);
  await page.getByRole('button', { name: 'Ra ngoài thư mục' }).click();
  await expect(page).toHaveURL('/workspace');
  await expect(page.getByRole('status').filter({ hasText: 'Tài liệu mới sẽ nằm ngoài' })).toBeVisible();
  await page.getByLabel('Chọn tệp tài liệu', { exact: true }).setInputFiles({ name: 'outside.pdf', mimeType: 'application/pdf', buffer: pdfFixture() });
  const outsideResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/upload' && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Tải lên và phân tích' }).click();
  const outsideUploaded = await outsideResponse;
  expect(outsideUploaded.status()).toBe(202);
  await expect(page).toHaveURL(/\/results\/[1-9]\d*$/);
  const outsideSaved = await (await page.request.get('/api/documents?unassigned=true')).json();
  expect(outsideSaved.find(doc => doc.original_filename === 'outside.pdf')?.folder_id).toBeNull();
  await page.goto('/workspace');
  await expect(page.getByRole('region', { name: 'Recents', exact: true }).getByRole('link', { name: 'outside.pdf', exact: true })).toBeVisible();
});

test('a stale folder cannot silently turn an upload into an outside document', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.route('**/api/folders?*', route => route.fulfill({ json: [] }));
  await page.route('**/api/documents?*', route => route.fulfill({ json: [] }));
  let uploads = 0;
  await page.route('**/api/upload', route => { uploads++; return route.abort(); });
  await page.goto('/workspace?folder=99999');
  await page.getByLabel('Chọn tệp tài liệu', { exact: true }).setInputFiles({ name: 'saved.pdf', mimeType: 'application/pdf', buffer: pdfFixture() });
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Không thể dùng thư mục này');
  await expect(page.getByRole('button', { name: 'Tải lên và phân tích' })).toBeDisabled();
  expect(uploads).toBe(0);
  await page.getByRole('button', { name: 'Ra ngoài thư mục' }).click();
  await expect(page.getByRole('button', { name: 'Tải lên và phân tích' })).toBeEnabled();
});

test('folder access failure retains files and keeps the selected destination', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.route('**/api/folders?*', route => route.fulfill({ json: [{ id: 71, name: 'Deleted folder' }] }));
  await page.route('**/api/documents?*', route => route.fulfill({ json: [] }));
  await page.route('**/api/upload', route => route.fulfill({ status: 404 }));
  await page.goto('/workspace?folder=71');
  await page.getByLabel('Chọn tệp tài liệu', { exact: true }).setInputFiles({ name: 'saved.pdf', mimeType: 'application/pdf', buffer: pdfFixture() });
  await page.getByRole('button', { name: 'Tải lên và phân tích' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Thư mục không còn khả dụng');
  await expect(page.locator('.upload-files')).toContainText('saved.pdf');
  await expect(page).toHaveURL('/workspace?folder=71');
});

