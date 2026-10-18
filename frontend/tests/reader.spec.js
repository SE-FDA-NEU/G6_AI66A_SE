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
  await page.route('**/api/documents/*/summary*', route => route.fulfill({ json: { document: null } }));
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
  await expect(page.locator('.reader-text-layer')).toHaveCount(0);
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
  await expect(page.getByText('Trang chiếu 2/3', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Trang chiếu 2')).toHaveAttribute('src', `/api/documents/77/reader.pdf?version=${version}#page=2`);
  await page.getByRole('combobox', { name: 'Chọn trang nguồn' }).selectOption('3');
  await expect(page.getByTitle('Bản đọc PDF — Trang chiếu 3')).toHaveAttribute('src', `/api/documents/77/reader.pdf?version=${version}#page=3`);
});

test('conversion failure is shown explicitly without fabricated reader pages', async ({ page }) => {
  await page.route('**/api/documents/77/pages', route => route.fulfill({ status: 409,
    json: { detail: { code: 'reader_not_ready', message: 'A stable reader PDF has not been prepared yet.' } } }));
  await page.route('**/api/documents/77/reader', route => route.fulfill({ status: 422,
    json: { detail: { code: 'conversion_failed', message: 'Office to PDF conversion failed.' } } }));
  await page.goto('/documents/77');
  await page.getByRole('button', { name: 'Chuẩn bị bản đọc' }).click();
  await expect(page.locator('.reader-page').getByRole('alert')).toContainText('Không thể tạo bản đọc PDF cho tài liệu Office.');
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.getByRole('combobox', { name: 'Chọn trang nguồn' })).toHaveCount(0);
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

  await expect(page.locator('.reader-text-layer')).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Bản tóm tắt đã lưu', exact: true })).toBeVisible();

  // Both Previous and Next buttons are enabled on page 12
  await expect(page.getByRole('button', { name: 'Trước', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Sau', exact: true })).toBeEnabled();

  // 2. Click Next -> Page 13
  await page.getByRole('button', { name: 'Sau', exact: true }).click();
  await expect(page).toHaveURL('/documents/99?page=13');
  await expect(page.getByText('Trang 13/24', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Trang 13')).toBeVisible();

  // Page 13 has no text layer in our mock
  await expect(page.locator('.reader-text-layer')).toHaveCount(0);

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
  await expect(page.locator('.reader-page .error-box')).toContainText('Bạn không có quyền truy cập tài liệu này');
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

test('precise highlighting resolves evidence passage using stored positions and avoids earlier repeated text occurrence', async ({ page }) => {
  const version = 'e'.repeat(64);
  const repeatedPhrase = 'Phí dịch vụ 0.05% mỗi ngày';
  // Occurrence 1 starts at index 18; Occurrence 2 starts at index 72
  const textWithDuplicates = `Khoản 1 quy định: ${repeatedPhrase} nếu trễ hạn đợt 1. Khoản 2 quy định: ${repeatedPhrase} nếu trễ hạn đợt 2.`;
  const occ1Start = textWithDuplicates.indexOf(repeatedPhrase);
  const occ2Start = textWithDuplicates.lastIndexOf(repeatedPhrase);
  const occ2End = occ2Start + repeatedPhrase.length;

  expect(occ1Start).toBe(18);
  expect(occ2Start).toBe(82);

  // Stored glyph/token positions
  const positions = [
    { text: repeatedPhrase, start: occ1Start, end: occ1Start + repeatedPhrase.length, bbox: [72, 100, 250, 115] },
    { text: repeatedPhrase, start: occ2Start, end: occ2End, bbox: [72, 180, 250, 195] },
  ];

  const docData = {
    page_count: 5,
    page_kind: 'page',
    reader_version: version,
    reader_url: `/documents/55/reader.pdf?version=${version}`,
    pages: [
      { page: 1, text: 'Trang 1 nội dung' },
      { page: 2, text: '' }, // scanned page
      { page: 3, text: textWithDuplicates, positions },
      { page: 4, text: 'Trang 4 nội dung' },
      { page: 5, text: 'Trang 5 nội dung' },
    ],
  };

  await page.route('**/api/documents/55/pages', route => route.fulfill({ json: docData }));
  await page.route('**/api/documents/55/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: pdfFixture() }));

  // Direct navigation to occurrence 2 via citation query params
  await page.goto(`/documents/55?page=3&start=${occ2Start}&end=${occ2End}&evidence=55-3-${occ2Start}-${occ2End}`);

  // Page 3 is loaded correctly
  await expect(page.getByText('Trang 3/5', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Trang 3')).toHaveAttribute('src', `/api${docData.reader_url}&highlight_page=3&start=${occ2Start}&end=${occ2End}#page=3`);

  await expect(page.locator('.reader-highlight-note')).toBeVisible();
  await expect(page.locator('.reader-text-layer')).toHaveCount(0);
  await expect(page.locator('.reader-pdf')).toHaveAttribute('src', new RegExp(`highlight_page=3&start=${occ2Start}&end=${occ2End}#page=3$`));

  // Fallback notice should NOT be present for precise matches
  await expect(page.locator('.highlight-fallback-notice')).toHaveCount(0);
});

test('scanned page fallback still opens the correct page and displays exact highlight not available message', async ({ page }) => {
  const version = 'f'.repeat(64);
  const docData = {
    page_count: 3,
    page_kind: 'page',
    reader_version: version,
    reader_url: `/documents/66/reader.pdf?version=${version}`,
    pages: [
      { page: 1, text: 'Trang văn bản 1' },
      { page: 2, text: '', positions: [] }, // Scanned page without OCR / text layer
      { page: 3, text: 'Trang văn bản 3' },
    ],
  };

  await page.route('**/api/documents/66/pages', route => route.fulfill({ json: docData }));
  await page.route('**/api/documents/66/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: pdfFixture() }));

  // Citation link pointing to page 2 (scanned page)
  await page.goto('/documents/66?page=2&evidence=66-2-0-30&start=0&end=30');

  // Reader still opens the correct page (page 2)
  await expect(page.getByText('Trang 2/3', { exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Chọn trang nguồn' })).toHaveValue('2');
  await expect(page.getByTitle('Bản đọc PDF — Trang 2')).toHaveAttribute('src', `/api${docData.reader_url}#page=2`);

  // Fallback notice is displayed with exact required text
  const fallbackNotice = page.locator('.highlight-fallback-notice');
  await expect(fallbackNotice).toBeVisible();
  await expect(fallbackNotice).toContainText('Không có điểm nổi bật chính xác cho đoạn văn này.');

  // Text layer informs that no text layer is available
  await expect(page.locator('.reader-text-layer')).toHaveCount(0);

  // Navigation controls still work normally
  await expect(page.getByRole('button', { name: 'Trước', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Sau', exact: true })).toBeEnabled();
});

test('unresolved span fallback still opens the correct page and displays exact highlight not available message', async ({ page }) => {
  const version = 'f'.repeat(64);
  const docData = {
    page_count: 3,
    page_kind: 'page',
    reader_version: version,
    reader_url: `/documents/66/reader.pdf?version=${version}`,
    pages: [
      { page: 1, text: 'Đoạn văn bản mẫu trang 1 ngắn gọn.' },
      { page: 2, text: 'Đoạn văn bản mẫu trang 2.' },
      { page: 3, text: 'Đoạn văn bản mẫu trang 3.' },
    ],
  };

  await page.route('**/api/documents/66/pages', route => route.fulfill({ json: docData }));
  await page.route('**/api/documents/66/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: pdfFixture() }));

  // Citation link with out-of-bounds start & end offsets (start=5000 > text length)
  await page.goto('/documents/66?page=1&evidence=unresolved-span-evidence&start=5000&end=5050');

  // Reader still opens the correct page (page 1)
  await expect(page.getByText('Trang 1/3', { exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Chọn trang nguồn' })).toHaveValue('1');
  await expect(page.getByTitle('Bản đọc PDF — Trang 1')).toHaveAttribute('src', `/api${docData.reader_url}#page=1`);

  // Fallback notice is displayed with exact required text
  const fallbackNotice = page.locator('.highlight-fallback-notice');
  await expect(fallbackNotice).toBeVisible();
  await expect(fallbackNotice).toContainText('Không có điểm nổi bật chính xác cho đoạn văn này.');

  // No <mark> element is rendered
  await expect(page.locator('mark.citation-highlight')).toHaveCount(0);

  // Text layer snippet is rendered normally as plain text
  await expect(page.locator('.reader-text-layer')).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Bản tóm tắt đã lưu', exact: true })).toBeVisible();
});

test('originating job ID displays Về kết quả, survives reader refresh and page navigation, and returns to /results/:jobId with saved results', async ({ page }) => {
  const version = '7'.repeat(64); // Persisted reader versions are hexadecimal SHA-256 digests.
  const jobId = 105;
  const docId = 88;

  // Mock job endpoint returning completed job with saved analysis results
  const jobPayload = {
    id: jobId,
    status: 'completed',
    file_count: 1,
    completed_count: 1,
    job_files: [
      { id: 1, document_id: docId, original_filename: 'HopDongKinhTe.pdf', status: 'completed', attempt_count: 1 },
    ],
    result_data: {
      schema_version: 1,
      documents: {
        [docId]: {
          schema_version: 1,
          document_id: docId,
          original_filename: 'HopDongKinhTe.pdf',
          mode: 'table',
          analysis_status: 'completed',
          reader: { page_count: 3, page_kind: 'page' },
          label: { ai_label: 'Hợp đồng', ai_confidence: 0.95, confidence_level: 'high' },
          warnings: [],
          output: {
            type: 'table',
            value: { text: '1.500.000.000 VNĐ', unverified: false, evidence: [
              { document_id: docId, page: 2, start: 0, end: 17, quote: '1.500.000.000 VNĐ', reader_version: version },
            ] },
            payment_term: { text: null, unverified: true, evidence: [] },
            penalty: { text: null, unverified: true, evidence: [] },
          },
        },
      },
    },
  };

  await page.route(`**/jobs/${jobId}`, route => route.fulfill({ json: jobPayload }));

  // Mock reader pages and pdf
  await page.route(`**/api/documents/${docId}/pages`, route => route.fulfill({ json: {
    page_count: 3,
    page_kind: 'page',
    reader_version: version,
    reader_url: `/documents/${docId}/reader.pdf?version=${version}`,
    pages: [
      { page: 1, text: 'Trang 1 nội dung' },
      { page: 2, text: '1.500.000.000 VNĐ là giá trị hợp đồng', positions: [] },
      { page: 3, text: 'Trang 3 điều khoản bổ sung' },
    ],
  } }));
  await page.route(`**/api/documents/${docId}/reader.pdf?*`, route => route.fulfill({
    contentType: 'application/pdf',
    body: pdfFixture(),
  }));

  // Step 1: Start at /results/:jobId and verify saved results are rendered
  await page.goto(`/results/${jobId}`);
  await expect(page.getByText('TÁC VỤ #105')).toBeVisible();
  await expect(page.getByText('1.500.000.000 VNĐ')).toBeVisible();

  // Step 2: Click citation link which contains ?page=2&...&job=105
  const citationBadge = page.locator('.citation-badge').first();
  await expect(citationBadge).toBeVisible();
  await citationBadge.click();

  // Reader opens at page 2
  await expect(page).toHaveURL(new RegExp(`/documents/${docId}.*job=${jobId}`));
  await expect(page.getByText('Trang 2/3', { exact: true })).toBeVisible();

  // "Về kết quả" link is displayed and points to /results/105
  const backToResults = page.getByRole('link', { name: 'Về kết quả' });
  await expect(backToResults).toBeVisible();
  await expect(backToResults).toHaveAttribute('href', `/results/${jobId}`);

  // Page navigation preserves the job parameter
  await page.getByRole('button', { name: 'Sau', exact: true }).click();
  await expect(page.getByText('Trang 3/3', { exact: true })).toBeVisible();
  await expect(backToResults).toBeVisible();
  await expect(backToResults).toHaveAttribute('href', `/results/${jobId}`);

  // Step 3: Reader refresh retains Về kết quả button and return job ID
  await page.reload();
  await expect(page.getByText('Trang 3/3', { exact: true })).toBeVisible();
  const backAfterReload = page.getByRole('link', { name: 'Về kết quả' });
  await expect(backAfterReload).toBeVisible();
  await expect(backAfterReload).toHaveAttribute('href', `/results/${jobId}`);

  // Step 4: Click Về kết quả and return to the same /results/:jobId with saved results
  await backAfterReload.click();
  await expect(page).toHaveURL(`/results/${jobId}`);
  await expect(page.getByText('TÁC VỤ #105')).toBeVisible();
  await expect(page.getByText('1.500.000.000 VNĐ')).toBeVisible();
  await expect(page.getByRole('status', { name: 'Trạng thái tác vụ' })).toHaveText('Hoàn tất');
});

test('document opened from workspace provides workspace return path and preserves it across refresh', async ({ page }) => {
  const version = 'h'.repeat(64);
  const docId = 72;

  await page.route(`**/api/documents/${docId}/pages`, route => route.fulfill({ json: {
    page_count: 2,
    page_kind: 'page',
    reader_version: version,
    reader_url: `/documents/${docId}/reader.pdf?version=${version}`,
    pages: [
      { page: 1, text: 'Tài liệu không gian làm việc' },
      { page: 2, text: 'Trang 2 tài liệu' },
    ],
  } }));
  await page.route(`**/api/documents/${docId}/reader.pdf?*`, route => route.fulfill({
    contentType: 'application/pdf',
    body: pdfFixture(),
  }));

  // Step 1: Open document directly without originating job ID (workspace entry path)
  await page.goto(`/documents/${docId}`);

  // "Về kết quả" is NOT displayed
  await expect(page.locator('.return-job-link')).toHaveCount(0);

  // "Về thư viện" return link is displayed and points to /workspace
  const workspaceReturn = page.locator('.return-workspace-link');
  await expect(workspaceReturn).toBeVisible();
  await expect(workspaceReturn).toHaveAttribute('href', '/workspace');

  // Step 2: Reader refresh retains workspace return path without inventing Về kết quả
  await page.reload();
  await expect(page.locator('.return-job-link')).toHaveCount(0);
  const workspaceReturnAfterReload = page.locator('.return-workspace-link');
  await expect(workspaceReturnAfterReload).toBeVisible();
  await expect(workspaceReturnAfterReload).toHaveAttribute('href', '/workspace');

  // Step 3: Clicking workspace return path returns to /workspace
  await workspaceReturnAfterReload.click();
  await expect(page).toHaveURL('/workspace');
  await expect(page.getByText('Không gian tài liệu')).toBeVisible();
});



test('saved summary replaces the text preview below the PDF and stays while paging', async ({ page }) => {
  const version = 'a'.repeat(64);
  const reader = { page_count: 2, page_kind: 'page', reader_version: version,
    reader_url: `/documents/55/reader.pdf?version=${version}`, pages: [{ page: 1, text: 'Original text.' }, { page: 2, text: 'Second page.' }] };
  await page.route('**/api/documents/55/pages', route => route.fulfill({ json: reader }));
  await page.route('**/api/documents/55/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: pdfFixture() }));
  let loads = 0;
  await page.route('**/api/documents/55/summary*', route => {
    loads++;
    return route.fulfill({ json: { job_id: 99, mode: 'bullet', document: {
      schema_version: 1, document_id: 55, original_filename: 'Saved.pdf', analysis_status: 'completed',
      reader: { version, page_kind: 'page' }, warnings: [], output: { type: 'bullet',
        bullets: [{ text: 'Previously saved key finding.', unverified: true, evidence: [] }], actions: [] },
    } } });
  });
  await page.goto('/documents/55?page=1');
  const summary = page.getByRole('region', { name: 'Bản tóm tắt đã lưu', exact: true });
  await expect(summary).toContainText('Previously saved key finding.');
  await expect(page.locator('.reader-text-layer')).toHaveCount(0);
  expect(await summary.evaluate(element => element.getBoundingClientRect().top > document.querySelector('.reader-pdf').getBoundingClientRect().bottom)).toBe(true);
  await page.getByRole('button', { name: 'Sau', exact: true }).click();
  await expect(page.getByText('Trang 2/2', { exact: true })).toBeVisible();
  await expect(summary).toContainText('Previously saved key finding.');
  await expect(summary.getByRole('link', { name: 'Xem tác vụ #99', exact: true })).toHaveAttribute('href', '/results/99');
  expect(loads).toBe(1);
});

test('saved summary failure retries separately and empty summary keeps the reader usable', async ({ page }) => {
  const version = 'b'.repeat(64);
  await page.route('**/api/documents/55/pages', route => route.fulfill({ json: {
    page_count: 1, page_kind: 'page', reader_version: version,
    reader_url: `/documents/55/reader.pdf?version=${version}`, pages: [{ page: 1, text: 'Source text.' }],
  } }));
  await page.route('**/api/documents/55/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: pdfFixture() }));
  let attempt = 0;
  await page.route('**/api/documents/55/summary*', route => ++attempt === 1
    ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } }) : route.fulfill({ json: { document: null } }));
  await page.goto('/documents/55?page=1');
  const summary = page.getByRole('region', { name: 'Bản tóm tắt đã lưu', exact: true });
  await expect(summary.getByRole('alert')).toContainText('Không thể tải bản tóm tắt');
  await expect(page.locator('.reader-pdf')).toBeVisible();
  await summary.getByRole('button', { name: 'Thử lại bản tóm tắt', exact: true }).click();
  await expect(summary).toContainText('Tài liệu chưa có bản tóm tắt đã lưu.');
});
