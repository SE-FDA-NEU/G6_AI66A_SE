import { createHash } from 'node:crypto';
import { test, expect } from '@playwright/test';
import { user } from './helpers';

function pdfFixture() {
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 3 /Kids [4 0 R 6 0 R 8 0 R] >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'];
  for (const text of ['First native page', '', 'Third native page']) {
    const stream = text ? `BT /F1 12 Tf 72 720 Td (${text}) Tj ET` : '';
    const streamId = objects.length + 2;
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${streamId} 0 R >>`);
    objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
  }
  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 ${offsets.length}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) pdf += `${String(offset).padStart(10, '0')} 00000 n \n`;
  pdf += `trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf);
}

test.beforeEach(async ({ page }) => {
  const response = await page.request.post('/auth/login', { form: { username: 'reader@example.com', password: user.password } });
  expect(response.status()).toBe(200);
});

test('reader displays the pinned backend PDF and navigates real source pages', async ({ page }) => {
  const source = pdfFixture();
  const upload = await page.request.post('http://127.0.0.1:18001/upload', {
    multipart: { files: { name: 'reader.pdf', mimeType: 'application/pdf', buffer: source } },
  });
  expect(upload.status()).toBe(202);
  const { jobId } = await upload.json();
  let job;
  await expect.poll(async () => {
    job = await (await page.request.get(`/jobs/${jobId}`)).json();
    return ['completed', 'failed'].includes(job.status);
  }).toBe(true);
  expect(job.status).toBe('completed');
  const id = job.job_files[0].document_id;
  const savedResult = job.result_data.documents[String(id)];
  expect(savedResult.reader.page_count).toBe(3);
  expect(savedResult.analysis_status).toBe('not_configured');
  const pages = await (await page.request.get(`/api/documents/${id}/pages`)).json();
  const file = await page.request.get(`/api${pages.reader_url}`);
  expect(file.status()).toBe(200);
  expect(await file.body()).toEqual(source);
  expect(createHash('sha256').update(await file.body()).digest('hex')).toBe(pages.reader_version);
  expect(pages.pages[2]).toMatchObject({ page: 3, text: 'Third native page' });

  await page.goto(`/documents/${id}?page=3`);
  const frame = page.getByTitle('Bản đọc PDF — Trang 3');
  await expect(frame).toHaveAttribute('src', `/api${pages.reader_url}#page=3`);
  await expect(page.getByText('Trang 3/3', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Trước', exact: true }).click();
  await expect(page.getByTitle('Bản đọc PDF — Trang 2')).toHaveAttribute('src', `/api${pages.reader_url}#page=2`);
  await expect(page.getByText('Trang này không có lớp chữ để highlight chính xác.')).toBeVisible();
  await expect(page).toHaveURL(`/documents/${id}?page=2`);
  await page.reload();
  await expect(page.getByTitle('Bản đọc PDF — Trang 2')).toHaveAttribute('src', `/api${pages.reader_url}#page=2`);
  const revisited = await (await page.request.get(`/jobs/${jobId}`)).json();
  expect(revisited.result_data.documents[String(id)]).toEqual(savedResult);
  expect(revisited.status).toBe('completed');
});

test('PPTX references are labelled as slides and target the same PDF page', async ({ page }) => {
  const version = 'a'.repeat(64);
  await page.route('**/api/documents/77/pages', route => route.fulfill({ json: {
    page_count: 3, page_kind: 'slide', reader_version: version,
    reader_url: `/documents/77/reader.pdf?version=${version}`,
    pages: [1, 2, 3].map(page => ({ page, text: page === 2 ? 'Hidden slide text' : '' })),
  } }));
  await page.route('**/api/documents/77/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: pdfFixture() }));
  await page.goto('/documents/77?page=2');
  await expect(page.getByText('Slide 2/3', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Slide 2')).toHaveAttribute('src', `/api/documents/77/reader.pdf?version=${version}#page=2`);
  await page.getByRole('combobox', { name: 'Chọn trang nguồn' }).selectOption('3');
  await expect(page.getByTitle('Bản đọc PDF — Slide 3')).toHaveAttribute('src', `/api/documents/77/reader.pdf?version=${version}#page=3`);
});

test('conversion failure is shown explicitly without fabricated reader pages', async ({ page }) => {
  await page.route('**/api/documents/77/pages', route => route.fulfill({ status: 409,
    json: { detail: { code: 'reader_not_ready', message: 'A stable reader PDF has not been prepared yet.' } } }));
  await page.route('**/api/documents/77/reader', route => route.fulfill({ status: 422,
    json: { detail: { code: 'conversion_failed', message: 'Office to PDF conversion failed.' } } }));
  await page.goto('/documents/77');
  await page.getByRole('button', { name: 'Chuẩn bị bản đọc' }).click();
  await expect(page.locator('.reader-page').getByRole('alert')).toContainText('Office to PDF conversion failed.');
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.getByRole('combobox')).toHaveCount(0);
});

function mockContract24() {
  const version = 'c'.repeat(64);
  const pages = Array.from({ length: 24 }, (_, i) => ({
    page: i + 1,
    text: i === 11 ? 'Điều khoản hợp đồng trang 12: Phí dịch vụ 0.05% mỗi ngày.' : (i === 12 ? '' : `Nội dung hợp đồng trang ${i + 1}`),
  }));
  return {
    page_count: 24,
    page_kind: 'page',
    reader_version: version,
    reader_url: `/documents/99/reader.pdf?version=${version}`,
    pages,
  };
}

test('page-12 direct link in a 24-page contract and browser history navigation', async ({ page }) => {
  const contract = mockContract24();
  await page.route('**/api/documents/99/pages', route => route.fulfill({ json: contract }));
  await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: pdfFixture() }));

  // 1. Direct link to page 12
  await page.goto('/documents/99?page=12');

  // Verify page 12 of 24 is loaded directly
  await expect(page.getByText('Trang 12/24', { exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Chọn trang nguồn' })).toHaveValue('12');
  const frame = page.getByTitle('Bản đọc PDF — Trang 12');
  await expect(frame).toHaveAttribute('src', `/api${contract.reader_url}#page=12`);

  // Verify text layer for page 12
  await expect(page.getByText(/Điều khoản hợp đồng trang 12/)).toBeVisible();

  // Both Previous and Next buttons are enabled on page 12
  await expect(page.getByRole('button', { name: 'Trước', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Sau', exact: true })).toBeEnabled();

  // 2. Click Next -> Page 13
  await page.getByRole('button', { name: 'Sau', exact: true }).click();
  await expect(page).toHaveURL('/documents/99?page=13');
  await expect(page.getByText('Trang 13/24', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Trang 13')).toBeVisible();

  // Page 13 has no text layer in our mock
  await expect(page.getByText('Trang này không có lớp chữ để highlight chính xác.')).toBeVisible();

  // 3. Browser Back navigation
  await page.goBack();
  await expect(page).toHaveURL('/documents/99?page=12');
  await expect(page.getByText('Trang 12/24', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Trang 12')).toBeVisible();

  // 4. Browser Forward navigation
  await page.goForward();
  await expect(page).toHaveURL('/documents/99?page=13');
  await expect(page.getByText('Trang 13/24', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Trang 13')).toBeVisible();
});

test('missing document state shows 404 message and library link without iframe', async ({ page }) => {
  await page.route('**/api/documents/999/pages', route => route.fulfill({
    status: 404,
    json: { detail: 'Document not found' },
  }));
  await page.goto('/documents/999');
  await expect(page.locator('.reader-page .error-box')).toContainText('Không tìm thấy tài liệu.');
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.locator('.reader-error').getByRole('link', { name: 'Về thư viện' })).toBeVisible();
});

test('access-denied document state shows 403 message and library link without iframe', async ({ page }) => {
  await page.route('**/api/documents/888/pages', route => route.fulfill({
    status: 403,
    json: { detail: 'Access denied' },
  }));
  await page.goto('/documents/888');
  await expect(page.locator('.reader-page .error-box')).toContainText('Access denied');
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.locator('.reader-error').getByRole('link', { name: 'Về thư viện' })).toBeVisible();
});

test('invalid-page state displays out-of-range error and allows returning to page 1', async ({ page }) => {
  const contract = mockContract24();
  await page.route('**/api/documents/99/pages', route => route.fulfill({ json: contract }));
  await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: pdfFixture() }));

  // Request page 99 in a 24-page contract
  await page.goto('/documents/99?page=99');

  await expect(page.locator('.reader-page .error-box')).toContainText('Trang nguồn không tồn tại');
  await expect(page.locator('.reader-page .error-box')).toContainText('24 trang');
  await expect(page.locator('iframe')).toHaveCount(0);

  // Click 'Về trang 1'
  await page.getByRole('button', { name: 'Về trang 1' }).click();
  await expect(page).toHaveURL('/documents/99?page=1');
  await expect(page.getByText('Trang 1/24', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Trang 1')).toBeVisible();
});


