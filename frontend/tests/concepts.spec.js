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

function conceptJob(concepts, limitation = null, warnings = [], extraDocFields = {}) {
  const document = {
    schema_version: 1,
    document_id: 88,
    original_filename: 'macroeconomics.pdf',
    mode: 'concept',
    analysis_status: 'completed',
    reader: { page_count: 5, page_kind: 'page' },
    label: { ai_label: 'Macroeconomics', ai_confidence: 0.88, confidence_level: 'high' },
    warnings,
    output: {
      type: 'concept',
      concepts,
      limitation,
    },
    ...extraDocFields,
  };

  return {
    id: 99,
    status: 'completed',
    file_count: 1,
    completed_count: 1,
    job_files: [
      { id: 1, document_id: 88, original_filename: 'macroeconomics.pdf', status: 'completed', attempt_count: 1 },
    ],
    result_data: {
      schema_version: 1,
      documents: { 88: document },
    },
  };
}

test.beforeEach(async ({ page }) => {
  const login = await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(login.status()).toBe(200);
});

test.describe('Shared Upload Selector and Concept Submission (US04, BR04, BR05)', () => {
  test('shared upload selector exposes Tóm tắt điểm chính, Bảng điều khoản tài chính and Tổng quan khái niệm mapped to modes', async ({ page }) => {
    await page.goto('/upload');

    const selector = page.getByLabel('Kiểu phân tích');
    await expect(selector).toBeVisible();

    const options = await selector.locator('option').all();
    expect(options.length).toBe(3);

    expect(await options[0].getAttribute('value')).toBe('bullet');
    expect(await options[0].textContent()).toContain('Tóm tắt điểm chính');

    expect(await options[1].getAttribute('value')).toBe('table');
    expect(await options[1].textContent()).toContain('Bảng điều khoản tài chính');

    expect(await options[2].getAttribute('value')).toBe('concept');
    expect(await options[2].textContent()).toContain('Tổng quan khái niệm');
  });

  test('preserves concept selection when files are added, changed, or removed', async ({ page }) => {
    await page.goto('/upload');

    const selector = page.getByLabel('Kiểu phân tích');
    // Select Tổng quan khái niệm
    await selector.selectOption('concept');
    await expect(selector).toHaveValue('concept');

    // Add first file
    const fileInput = page.getByLabel('Chọn tệp tài liệu');
    await fileInput.setInputFiles([
      { name: 'paper1.pdf', mimeType: 'application/pdf', buffer: pdfFixture() },
    ]);
    await expect(page.getByText('paper1.pdf')).toBeVisible();

    // Mode is preserved after adding file
    await expect(selector).toHaveValue('concept');

    // Add second file
    await fileInput.setInputFiles([
      { name: 'paper2.pdf', mimeType: 'application/pdf', buffer: pdfFixture() },
    ]);
    await expect(page.getByText('paper2.pdf')).toBeVisible();

    // Mode is preserved after adding more files
    await expect(selector).toHaveValue('concept');

    // Remove first file
    await page.getByRole('button', { name: 'Xóa paper1.pdf' }).click();
    await expect(page.getByText('paper1.pdf')).toHaveCount(0);

    // Mode is preserved after removing file
    await expect(selector).toHaveValue('concept');
  });

  test('connects concept submission, sends mode: concept, and opens results page', async ({ page }) => {
    let capturedMode = null;
    await page.route('**/api/upload', async route => {
      const postData = route.request().postData();
      // Inspect multipart body for mode field
      if (postData && postData.includes('name="mode"')) {
        const match = postData.match(/name="mode"\r\n\r\n([^\r\n]+)/);
        if (match) capturedMode = match[1];
      }
      return route.fulfill({
        status: 202,
        json: { jobId: 123 },
      });
    });

    await page.goto('/upload');
    const selector = page.getByLabel('Kiểu phân tích');
    await selector.selectOption('concept');

    await page.getByLabel('Chọn tệp tài liệu').setInputFiles([
      { name: 'macroeconomics.pdf', mimeType: 'application/pdf', buffer: pdfFixture() },
    ]);

    await page.getByRole('button', { name: 'Tải lên và phân tích', exact: true }).click();
    await expect(page).toHaveURL('/results/123');
    expect(capturedMode).toBe('concept');
  });
});

test.describe('Concept Result Rendering and Source Navigation (BR04, BR05)', () => {
  test('renders three to five concepts with titles, structured descriptions and verified citation links', async ({ page }) => {
    const concepts = [
      {
        name: 'Demand-pull Inflation',
        description: {
          text: 'Demand-pull inflation occurs when aggregate demand outpaces supply.',
          unverified: false,
          evidence: [
            { document_id: 88, page: 1, start: 0, end: 68, quote: 'Demand-pull inflation occurs when aggregate demand outpaces supply.', reader_version: 'a'.repeat(64) },
          ],
        },
      },
      {
        name: 'Cost-push Inflation',
        description: {
          text: 'Cost-push inflation is driven by aggregate supply decreases.',
          unverified: false,
          evidence: [
            { document_id: 88, page: 2, start: 0, end: 60, quote: 'Cost-push inflation is driven by aggregate supply decreases.', reader_version: 'a'.repeat(64) },
          ],
        },
      },
      {
        name: 'Monetary Policy',
        description: {
          text: 'Monetary policy adjusts interest rates to stabilize price levels.',
          unverified: false,
          evidence: [
            { document_id: 88, page: 3, start: 0, end: 65, quote: 'Monetary policy adjusts interest rates to stabilize price levels.', reader_version: 'a'.repeat(64) },
          ],
        },
      },
      {
        name: 'Fiscal Policy',
        description: {
          text: 'Fiscal policy uses government spending and taxation to influence demand.',
          unverified: false,
          evidence: [
            { document_id: 88, page: 4, start: 0, end: 72, quote: 'Fiscal policy uses government spending and taxation to influence demand.', reader_version: 'a'.repeat(64) },
          ],
        },
      },
    ];

    await page.route('**/jobs/99', route => route.fulfill({ json: conceptJob(concepts) }));
    await page.goto('/results/99');

    const region = page.getByRole('region', { name: 'Kết quả phân tích AI' });
    await expect(region).toBeVisible();

    // Verify concept section header
    const conceptsSection = page.getByRole('region', { name: 'Khái niệm chính' });
    await expect(conceptsSection).toBeVisible();

    // Verify all 4 concepts are rendered
    await expect(page.getByRole('heading', { name: 'Demand-pull Inflation' })).toBeVisible();
    await expect(page.getByText('Demand-pull inflation occurs when aggregate demand outpaces supply.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'macroeconomics.pdf — trang 1' })).toBeVisible();

    await expect(page.getByRole('heading', { name: 'Cost-push Inflation' })).toBeVisible();
    await expect(page.getByText('Cost-push inflation is driven by aggregate supply decreases.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'macroeconomics.pdf — trang 2' })).toBeVisible();

    await expect(page.getByRole('heading', { name: 'Monetary Policy' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Fiscal Policy' })).toBeVisible();

    // Verify citation link format carries page, start, end, evidence and job id
    const link = page.getByRole('link', { name: 'macroeconomics.pdf — trang 1' });
    await expect(link).toHaveAttribute('href', '/documents/88?page=1&start=0&end=68&evidence=88-1-0-68&job=99');
  });

  test('clicking concept citation navigates to document reader with page, offsets and return path', async ({ page }) => {
    const concepts = [
      {
        name: 'Demand-pull Inflation',
        description: {
          text: 'Demand-pull inflation occurs when aggregate demand outpaces supply.',
          unverified: false,
          evidence: [
            { document_id: 88, page: 2, start: 10, end: 78, quote: 'Demand-pull inflation occurs when aggregate demand outpaces supply.', reader_version: 'a'.repeat(64) },
          ],
        },
      },
    ];

    await page.route('**/jobs/99', route => route.fulfill({ json: conceptJob(concepts) }));

    const mockDoc = {
      page_count: 5,
      page_kind: 'page',
      reader_version: 'a'.repeat(64),
      reader_url: `/documents/88/reader.pdf?version=${'a'.repeat(64)}`,
      pages: [
        { page: 1, text: 'Page 1 intro.' },
        { page: 2, text: 'Intro text Demand-pull inflation occurs when aggregate demand outpaces supply. Extra.' },
      ],
      ai_label: 'Macroeconomics',
      ai_confidence: 0.88,
      review_state: 'needs_review',
      folder_id: null,
      original_filename: 'macroeconomics.pdf',
    };

    await page.route('**/api/documents/88/pages', route => route.fulfill({ json: mockDoc }));
    await page.route('**/api/documents/88/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfFixture(),
    }));

    await page.goto('/results/99');

    // Click citation link
    const citationLink = page.getByRole('link', { name: 'macroeconomics.pdf — trang 2' });
    await expect(citationLink).toBeVisible();
    await citationLink.click();

    // Verify navigation to reader on page 2 with evidence and return job
    await expect(page).toHaveURL(/\/documents\/88\?page=2&start=10&end=78&evidence=88-2-10-78&job=99/);
    await expect(page.getByText('Trang 2/5')).toBeVisible();

    // Verify Về kết quả link is displayed and points to /results/99
    const backBtn = page.getByRole('link', { name: 'Về kết quả' });
    await expect(backBtn).toBeVisible();
    await expect(backBtn).toHaveAttribute('href', '/results/99');
  });

  test('displays clear limitation and warning when source cannot support full 3-5 concept overview', async ({ page }) => {
    const singleConcept = [
      {
        name: 'Demand-pull Inflation',
        description: {
          text: 'Demand-pull inflation occurs when aggregate demand outpaces supply.',
          unverified: false,
          evidence: [
            { document_id: 88, page: 1, start: 0, end: 68, quote: 'Demand-pull inflation occurs when aggregate demand outpaces supply.', reader_version: 'a'.repeat(64) },
          ],
        },
      },
    ];

    const limitation = 'Tài liệu nguồn quá ngắn, chỉ hỗ trợ xác thực 1 khái niệm chính duy nhất.';
    const warnings = ['insufficient_concepts'];

    await page.route('**/jobs/99', route => route.fulfill({ json: conceptJob(singleConcept, limitation, warnings) }));
    await page.goto('/results/99');

    // Concept card for supported concept is shown
    await expect(page.getByRole('heading', { name: 'Demand-pull Inflation' })).toBeVisible();

    // Clear limitation text is rendered
    const limitationEl = page.getByTestId('concept-limitation');
    await expect(limitationEl).toBeVisible();
    await expect(limitationEl).toContainText('Tài liệu nguồn quá ngắn, chỉ hỗ trợ xác thực 1 khái niệm chính duy nhất.');

    // Warning is rendered in Vietnamese explanation
    await expect(page.getByText(/Tài liệu nguồn không đủ để hỗ trợ tổng quan 3-5 khái niệm cốt lõi/)).toBeVisible();
  });

  test('handles zero concepts with clear limitation and preserves UI stability', async ({ page }) => {
    const limitation = 'Không có đủ thông tin nền tảng để tạo lập các khái niệm cốt lõi.';
    const warnings = ['insufficient_concepts'];

    await page.route('**/jobs/99', route => route.fulfill({ json: conceptJob([], limitation, warnings) }));
    await page.goto('/results/99');

    const limitationEl = page.getByTestId('concept-limitation');
    await expect(limitationEl).toBeVisible();
    await expect(limitationEl).toContainText('Không có đủ thông tin nền tảng để tạo lập các khái niệm cốt lõi.');
    await expect(page.locator('.concept-card')).toHaveCount(0);
  });

  test('renders error state when document analysis status is failed', async ({ page }) => {
    const failedJob = conceptJob([], null, [], {
      analysis_status: 'failed',
      error_message: 'Không thể phân tích tài liệu do định dạng không tương thích.',
    });

    await page.route('**/jobs/99', route => route.fulfill({ json: failedJob }));
    await page.goto('/results/99');

    const errorEl = page.getByTestId('document-analysis-error');
    await expect(errorEl).toBeVisible();
    await expect(errorEl).toContainText('Không thể phân tích tài liệu do định dạng không tương thích.');
  });
});
