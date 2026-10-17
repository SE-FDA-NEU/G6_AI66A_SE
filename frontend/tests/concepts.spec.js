import { test, expect } from '@playwright/test';
import { user } from './helpers';

function conceptJob(concepts, limitation = null, warnings = []) {
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

test.describe('Concept Processing and Presentation (BR04, BR05)', () => {
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
    await expect(page.getByRole('link', { name: 'macroeconomics.pdf — page 1' })).toBeVisible();

    await expect(page.getByRole('heading', { name: 'Cost-push Inflation' })).toBeVisible();
    await expect(page.getByText('Cost-push inflation is driven by aggregate supply decreases.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'macroeconomics.pdf — page 2' })).toBeVisible();

    await expect(page.getByRole('heading', { name: 'Monetary Policy' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Fiscal Policy' })).toBeVisible();

    // Verify citation link format carries page, start, end, evidence and job id
    const link = page.getByRole('link', { name: 'macroeconomics.pdf — page 1' });
    await expect(link).toHaveAttribute('href', '/documents/88?page=1&start=0&end=68&evidence=88-1-0-68&job=99');
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
});
