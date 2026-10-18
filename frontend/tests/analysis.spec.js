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
    await expect(analysis.getByRole('link', { name: 'contract.pdf — trang 2', exact: true }))
      .toHaveAttribute('href', '/documents/17?page=2&start=0&end=10&evidence=17-2-0-10&job=77');
    await expect(analysis.getByTestId('document-ai-label')).toHaveAttribute('data-original-label', 'Hợp đồng');
    if (mode === 'bullet') {
      await expect(analysis.getByText('Chưa xác thực · Cần kiểm tra')).toBeVisible();
      await expect(analysis.getByRole('link', { name: 'contract.pdf — trang 2' })).toHaveCount(1);
    }
    if (mode === 'table') await expect(analysis.getByText('Không có thông tin · Chưa xác thực')).toHaveCount(2);
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

test('same claim keeps separate source links, including passages for Chưa xác thực review', async ({ page }) => {
  const document = result('bullet');
  const claim = document.output.bullets[0];
  claim.unverified = true;
  claim.verification_issues = ['unsupported_fact'];
  claim.evidence.push({ ...claim.evidence[0], document_id: 18, start: 20, end: 30 });
  await page.route('**/jobs/77', route => route.fulfill({ json: job(document) }));
  await page.goto('/results/77');
  const region = page.getByRole('region', { name: 'Kết quả phân tích AI' });
  await expect(region.getByRole('link', { name: 'contract.pdf — trang 2', exact: true }))
    .toHaveAttribute('href', '/documents/17?page=2&start=0&end=10&evidence=17-2-0-10&job=77');
  await expect(region.getByRole('link', { name: 'Tài liệu #18 — trang 2', exact: true }))
    .toHaveAttribute('href', '/documents/18?page=2&start=20&end=30&evidence=18-2-20-30&job=77');
  await expect(region.getByText('Chưa xác thực · Cần kiểm tra')).toHaveCount(2);
  await page.reload();
  await expect(region.getByRole('link', { name: /— trang 2/ })).toHaveCount(2);
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

test('financial clause upload submits five contracts in one job through the real proxy', async ({ page }) => {
  const login = await page.request.post('/auth/login', { form: { username: 'reader@example.com', password: user.password } });
  expect(login.status()).toBe(200);
  await page.goto('/upload');
  const contracts = Array.from({ length: 5 }, (_, index) => ({
    name: `contract-${index + 1}.pdf`, mimeType: 'application/pdf', buffer: pdf(),
  }));
  const uploads = [];
  await page.route('**/api/upload', route => {
    uploads.push(route.request());
    return route.continue();
  });
  await page.getByLabel('Chọn tệp tài liệu').setInputFiles(contracts);
  await page.getByLabel('Kiểu phân tích').selectOption('table');
  await expect(page.getByRole('status')).toContainText('5/5 tệp hợp lệ');
  await page.getByRole('button', { name: 'Tải lên và phân tích', exact: true }).click();
  await expect(page).toHaveURL(/\/results\/\d+$/);
  await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText('Hoàn tất', { timeout: 15000 });
  await expect(page.getByText(/Thêm GEMINI_API_KEY/)).toHaveCount(5); // isolated backend never uses paid APIs
  const jobId = new URL(page.url()).pathname.split('/').pop();
  const saved = await (await page.request.get(`/jobs/${jobId}`)).json();
  expect(uploads).toHaveLength(1);
  const form = await new Request(uploads[0].url(), {
    method: 'POST', headers: uploads[0].headers(), body: uploads[0].postDataBuffer(),
  }).formData();
  expect(form.getAll('mode')).toEqual(['table']);
  expect(form.getAll('files').map(file => file.name)).toEqual(contracts.map(file => file.name));
  for (const file of form.getAll('files')) {
    expect(Buffer.from(await file.arrayBuffer())).toEqual(pdf());
  }
  expect(saved.id).toBe(Number(jobId));
  expect(saved.mode).toBe('table');
  expect(saved.file_count).toBe(5);
  expect(saved.completed_count).toBe(5);
  expect(saved.job_files.map(file => file.original_filename).sort()).toEqual(contracts.map(file => file.name).sort());
  await expect(page.getByRole('list', { name: 'Trạng thái từng tệp' }).getByRole('listitem')).toHaveCount(5);
  await expect(page.getByRole('progressbar', { name: 'Tiến độ xử lý', exact: true })).toHaveJSProperty('value', 5);
  for (const file of saved.job_files) {
    expect(saved.result_data.documents[String(file.document_id)].output.type).toBe('table');
  }
});

for (const failure of ['server', 'network', 'invalid job']) {
  test(`financial clause batch preserves files and mode during loading and ${failure} failure, then retries`, async ({ page }) => {
    let releaseUpload;
    const uploads = [];
    await page.route('**/api/upload', async route => {
      uploads.push(route.request());
      if (uploads.length > 1) return route.continue();
      await new Promise(resolve => { releaseUpload = resolve; });
      if (failure === 'network') return route.abort('failed');
      return route.fulfill(failure === 'server'
        ? { status: 503, json: { detail: 'Unavailable' } }
        : { status: 202, json: { jobId: 'invalid' } });
    });
    await page.goto('/upload');
    const selector = page.getByLabel('Kiểu phân tích');
    await expect(selector).toBeEnabled();
    await selector.selectOption('table');
    await page.reload();
    await expect(selector).toBeEnabled();
    await expect(selector).toHaveValue('table');
    const contracts = Array.from({ length: 5 }, (_, index) => ({
      name: `retry-contract-${index + 1}.pdf`, mimeType: 'application/pdf', buffer: pdf(),
    }));
    const picker = page.getByLabel('Chọn tệp tài liệu');
    await picker.setInputFiles(contracts);
    await page.getByRole('button', { name: 'Tải lên và phân tích', exact: true }).click();
    await expect.poll(() => uploads.length).toBe(1);
    try {
      await expect(selector).toBeDisabled();
      await expect(selector).toHaveValue('table');
      await expect(picker).toBeDisabled();
      await expect(page.getByRole('button', { name: 'Đang gửi…', exact: true })).toBeDisabled();
      for (const button of await page.getByRole('button', { name: /^Xóa / }).all()) {
        await expect(button).toBeDisabled();
      }
      const transfer = await page.evaluateHandle(() => {
        const data = new DataTransfer();
        data.items.add(new File(['ignored'], 'during-upload.pdf', { type: 'application/pdf' }));
        return data;
      });
      await page.locator('.upload-picker').dispatchEvent('drop', { dataTransfer: transfer });
      await transfer.dispose();
      await expect(page.getByRole('listitem')).toHaveCount(5);
    } finally {
      releaseUpload();
    }
    await expect(page.locator('.upload-page').getByRole('alert')).toHaveText(/Không thể gửi tài liệu/);
    await expect(page).toHaveURL('/upload');
    await expect(selector).toBeEnabled();
    await expect(selector).toHaveValue('table');
    await expect(picker).toBeEnabled();
    for (const contract of contracts) {
      await expect(page.getByText(contract.name, { exact: true })).toBeVisible();
    }
    await expect(page.getByRole('status')).toContainText('5/5 tệp hợp lệ');
    const retry = page.getByRole('button', { name: 'Tải lên và phân tích', exact: true });
    await expect(retry).toBeEnabled();
    await retry.click();
    await expect(page).toHaveURL(/\/results\/\d+$/);
    expect(uploads).toHaveLength(2);
    const forms = await Promise.all(uploads.map(request => new Request(request.url(), {
      method: 'POST', headers: request.headers(), body: request.postDataBuffer(),
    }).formData()));
    for (const form of forms) {
      expect(form.getAll('mode')).toEqual(['table']);
      expect(form.getAll('files').map(file => file.name)).toEqual(contracts.map(file => file.name));
      for (const file of form.getAll('files')) {
        expect(Buffer.from(await file.arrayBuffer())).toEqual(pdf());
      }
    }
  });
}

test('upload errors keep selection and allow an explicit retry', async ({ page }) => {
  await page.route('**/api/upload', route => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }));
  await page.goto('/upload');
  await page.getByLabel('Chọn tệp tài liệu').setInputFiles({ name: 'retry.pdf', mimeType: 'application/pdf', buffer: pdf() });
  await page.getByRole('button', { name: 'Tải lên và phân tích', exact: true }).click();
  await expect(page.locator('.upload-page').getByRole('alert')).toHaveText(/Không thể gửi tài liệu/);
  await expect(page.getByRole('button', { name: 'Tải lên và phân tích', exact: true })).toBeEnabled();
  await expect(page.getByText('retry.pdf', { exact: true })).toBeVisible();
});

test.describe('AI Label Prediction and Confidence Boundary (US06 / US10)', () => {
  for (const { score, level, needsReviewText } of [
    { score: 0.87, level: 'high', needsReviewText: false },
    { score: 0.80, level: 'high', needsReviewText: false },
    { score: 0.79, level: 'low', needsReviewText: true },
    { score: 0.72, level: 'low', needsReviewText: true },
  ]) {
    test(`renders AI label prediction for ${Math.round(score * 100)}% score (${level} confidence)`, async ({ page }) => {
      const doc = result('bullet');
      doc.label = {
        ai_label: 'Hợp đồng',
        ai_confidence: score,
        confidence_level: level,
        review_state: 'needs_review',
        user_label: null,
      };
      await page.route('**/jobs/77', route => route.fulfill({ json: job(doc) }));
      await page.goto('/results/77');

      const labelPara = page.locator('.analysis-label');
      await expect(labelPara).toBeVisible();
      await expect(labelPara.getByTestId('document-ai-label')).toHaveAttribute('data-original-label', 'Hợp đồng');
      await expect(labelPara.getByTestId('document-ai-confidence')).toContainText(`${Math.round(score * 100)}%`);

      if (needsReviewText) {
        await expect(labelPara).toContainText('Cần kiểm tra');
      } else {
        await expect(labelPara).not.toContainText('Cần kiểm tra');
      }
    });
  }

  test('AI label suggestion renders alongside user_label independently', async ({ page }) => {
    const doc = result('bullet');
    doc.label = {
      ai_label: 'Hợp đồng',
      ai_confidence: 0.87,
      confidence_level: 'high',
      review_state: 'confirmed',
      user_label: 'Tài liệu pháp lý',
    };
    await page.route('**/jobs/77', route => route.fulfill({ json: job(doc) }));
    await page.goto('/results/77');

    const labelPara = page.locator('.analysis-label');
    await expect(labelPara).toBeVisible();
    await expect(labelPara.getByTestId('document-ai-label')).toHaveAttribute('data-original-label', 'Hợp đồng');
    await expect(labelPara.getByTestId('document-ai-confidence')).toContainText('87%');
    await expect(labelPara.getByTestId('document-user-label')).toContainText('Tài liệu pháp lý');
    await expect(labelPara).not.toContainText('Cần kiểm tra');
  });
});
