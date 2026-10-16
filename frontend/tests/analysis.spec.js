import { test, expect } from '@playwright/test';
import { user } from './helpers';

function result(mode) {
  const claim = { text: 'Phạt 0.05% mỗi ngày.', unverified: false, evidence: [
    { document_id: 17, page: 2, start: 0, end: 10, quote: 'Đoạn nguồn', reader_version: 'a'.repeat(64) },
  ] };
  const missing = { text: null, evidence: [], unverified: true };
  return {
    schema_version: 1, document_id: 17, original_filename: 'contract.pdf', mode,
    analysis_status: 'completed', reader: { page_count: 2, page_kind: 'page' },
    label: { ai_label: 'Hợp đồng', ai_confidence: .87, confidence_level: 'high' }, warnings: [],
    output: mode === 'bullet' ? { type: mode, bullets: [claim], actions: [
      { text: 'Đề xuất chưa có bằng chứng', evidence: [], unverified: true },
    ] } : mode === 'table' ? { type: mode, value: missing, payment_term: missing, penalty: claim }
      : { type: mode, concepts: [{ name: 'Phạt chậm trả', description: claim }] },
  };
}

function job(document) {
  return { id: 77, status: 'completed', file_count: 1, completed_count: 1,
    job_files: [{ id: 1, document_id: 17, original_filename: 'contract.pdf', status: 'completed', attempt_count: 1 }],
    result_data: { schema_version: 1, documents: { 17: document } } };
}

test.beforeEach(async ({ page }) => {
  const login = await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(login.status()).toBe(200);
});

for (const mode of ['bullet', 'table', 'concept']) {
  test(`renders ${mode} AI output, source links and saved results after reload`, async ({ page }) => {
    await page.route('**/jobs/77', route => route.fulfill({ json: job(result(mode)) }));
    await page.goto('/results/77');
    const analysis = page.getByRole('region', { name: 'Kết quả phân tích AI' });
    await expect(analysis.getByText('Phạt 0.05% mỗi ngày.', { exact: true })).toBeVisible();
    await expect(analysis.getByRole('link', { name: 'Trang 2 · #17', exact: true }))
      .toHaveAttribute('href', '/documents/17?page=2&start=0&end=10');
    await expect(analysis.getByText(/Nhãn AI:/)).toContainText('Hợp đồng');
    if (mode === 'bullet') {
      await expect(analysis.getByText('Unverified · Cần kiểm tra')).toBeVisible();
      await expect(analysis.getByRole('link', { name: 'Trang 2' })).toHaveCount(1);
    }
    if (mode === 'table') await expect(analysis.getByText('Không có thông tin · Unverified')).toHaveCount(2);
    await page.reload();
    await expect(analysis.getByText('Phạt 0.05% mỗi ngày.', { exact: true })).toBeVisible();
  });
}

test('shows partial coverage and cache use without treating AI text as HTML', async ({ page }) => {
  const document = result('bullet');
  document.warnings = ['source_truncated'];
  document.analysis_metadata = { cache_hit: true };
  document.output.bullets[0].text = '<script>window.unsafeAI = true</script>';
  await page.route('**/jobs/77', route => route.fulfill({ json: job(document) }));
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/results/77');
  await expect(page.getByText(/Kết quả chưa bao quát toàn bộ/)).toBeVisible();
  await expect(page.getByText(/không gọi lại Gemini/)).toBeVisible();
  await expect(page.getByText(document.output.bullets[0].text, { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.unsafeAI)).toBeUndefined();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('missing key is explained instead of displaying invented AI output', async ({ page }) => {
  const document = result('bullet');
  document.analysis_status = 'not_configured';
  document.label = {};
  document.warnings = ['analysis_not_configured'];
  document.output = { type: 'bullet', bullets: [], actions: [] };
  await page.route('**/jobs/77', route => route.fulfill({ json: job(document) }));
  await page.goto('/results/77');
  await expect(page.getByText(/Thêm GEMINI_API_KEY/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Tóm tắt', exact: true })).toHaveCount(0);
});

test('same claim keeps separate source links, including passages for Unverified review', async ({ page }) => {
  const document = result('bullet');
  const claim = document.output.bullets[0];
  claim.unverified = true;
  claim.verification_issues = ['unsupported_fact'];
  claim.evidence.push({ ...claim.evidence[0], document_id: 18, start: 20, end: 30 });
  await page.route('**/jobs/77', route => route.fulfill({ json: job(document) }));
  await page.goto('/results/77');
  const region = page.getByRole('region', { name: 'Kết quả phân tích AI' });
  await expect(region.getByRole('link', { name: 'Trang 2 · #17', exact: true }))
    .toHaveAttribute('href', '/documents/17?page=2&start=0&end=10');
  await expect(region.getByRole('link', { name: 'Trang 2 · #18', exact: true }))
    .toHaveAttribute('href', '/documents/18?page=2&start=20&end=30');
  await expect(region.getByText('Unverified · Cần kiểm tra')).toHaveCount(2);
  await page.reload();
  await expect(region.getByRole('link', { name: /Trang 2 · #/ })).toHaveCount(2);
});

function pdf() {
  const text = 'BT /F1 12 Tf 72 720 Td (Contract fee 0.05% per day.) Tj ET';
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Count 1 /Kids [4 0 R] >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>',
    `<< /Length ${text.length} >>\nstream\n${text}\nendstream`];
  let output = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((value, index) => { offsets.push(output.length); output += `${index + 1} 0 obj\n${value}\nendobj\n`; });
  const xref = output.length;
  output += `xref\n0 ${offsets.length}\n0000000000 65535 f \n`;
  offsets.slice(1).forEach(offset => { output += `${String(offset).padStart(10, '0')} 00000 n \n`; });
  return Buffer.from(output + `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
}

test('upload UI sends selected mode through the real proxy and opens its results', async ({ page }) => {
  const login = await page.request.post('/auth/login', { form: { username: 'reader@example.com', password: user.password } });
  expect(login.status()).toBe(200);
  await page.goto('/upload');
  await page.getByLabel('Chọn tệp tài liệu').setInputFiles({ name: 'ai-flow.pdf', mimeType: 'application/pdf', buffer: pdf() });
  await page.getByLabel('Kiểu phân tích').selectOption('table');
  await page.getByRole('button', { name: 'Tải lên và phân tích', exact: true }).click();
  await expect(page).toHaveURL(/\/results\/\d+$/);
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Completed', { timeout: 15000 });
  await expect(page.getByText(/Thêm GEMINI_API_KEY/)).toBeVisible(); // isolated backend never uses paid APIs
  const jobId = new URL(page.url()).pathname.split('/').pop();
  const saved = await (await page.request.get(`/jobs/${jobId}`)).json();
  expect(saved.mode).toBe('table');
  expect(saved.result_data.documents[String(saved.job_files[0].document_id)].output.type).toBe('table');
});

test('upload errors keep selection and allow an explicit retry', async ({ page }) => {
  await page.route('**/api/upload', route => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }));
  await page.goto('/upload');
  await page.getByLabel('Chọn tệp tài liệu').setInputFiles({ name: 'retry.pdf', mimeType: 'application/pdf', buffer: pdf() });
  await page.getByRole('button', { name: 'Tải lên và phân tích', exact: true }).click();
  await expect(page.locator('.upload-page').getByRole('alert')).toHaveText(/Không thể gửi tài liệu/);
  await expect(page.getByRole('button', { name: 'Tải lên và phân tích', exact: true })).toBeEnabled();
  await expect(page.getByText('retry.pdf', { exact: true })).toBeVisible();
});
