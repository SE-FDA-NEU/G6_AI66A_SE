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
