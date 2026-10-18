import { test, expect } from '@playwright/test';
import { user } from './helpers';

const amount = '1,200,000,000 VND';
const evidence = (documentId = 51) => ({ document_id: documentId, page: 6, start: 0,
  end: amount.length, quote: amount, reader_version: 'a'.repeat(64) });
const claim = (overrides = {}) => ({ text: amount, unverified: false, evidence: [evidence()], ...overrides });

function savedJob(mode, output, label = {}) {
  const document = { schema_version: 1, document_id: 51, original_filename: 'source.pdf', mode,
    analysis_status: 'completed', reader: { page_count: 6, page_kind: 'page' }, warnings: [],
    label: { ai_label: 'Contract', ai_confidence: .99, confidence_level: 'high',
      user_label: 'Human reviewed category', review_state: 'confirmed', ...label }, output: { type: mode, ...output } };
  return { id: 138, mode, status: 'completed', file_count: 1, completed_count: 1,
    job_files: [{ id: 1, document_id: 51, original_filename: 'source.pdf', status: 'completed', attempt_count: 1 }],
    result_data: { schema_version: 1, documents: { 51: document } } };
}

test.beforeEach(async ({ page }) => {
  expect((await page.request.post('/auth/login', { form: { username: user.email, password: user.password } })).status()).toBe(200);
});

for (const [name, sources] of [
  ['absent', undefined], ['empty', []], ['null', [null]], ['missing page', [{ ...evidence(), page: undefined }]],
  ['invalid page', [{ ...evidence(), page: 0 }]], ['missing offsets', [{ document_id: 51, page: 6, quote: amount }]],
  ['invalid offsets', [{ ...evidence(), start: 10, end: 10 }]], ['invalid document', [{ ...evidence(), document_id: -1 }]],
  ['blank quote', [{ ...evidence(), quote: '  ' }]], ['missing version', [{ ...evidence(), reader_version: undefined }]],
]) {
  test(`summary ${name} evidence is Unverified with no fabricated source link despite a confirmed high-confidence label`, async ({ page }) => {
    const saved = savedJob('bullet', { bullets: [claim({ evidence: sources })], actions: [] });
    await page.route('**/jobs/138', route => route.fulfill({ json: saved }));
    async function check() {
      const summary = page.getByRole('region', { name: 'Tóm tắt điểm chính', exact: true });
      await expect(summary.locator('.claim-text')).toHaveText(amount);
      await expect(summary.locator('.unverified-badge')).toHaveCount(1);
      await expect(summary.getByRole('link')).toHaveCount(0);
      await expect(summary.locator('.unverified-badge')).toHaveAttribute('aria-label', 'Khẳng định chưa được xác thực');
      const metadata = page.locator('.analysis-label');
      await expect(metadata.getByTestId('document-ai-confidence')).toContainText('99%');
      await expect(metadata.getByTestId('document-review-state')).toContainText('Đã xác nhận');
      await expect(metadata.locator('.unverified-badge')).toHaveCount(0);
      await expect(metadata.getByTestId('document-folder-placement')).toHaveCount(0); // Result snapshots do not carry folder membership.
    }
    await page.goto('/results/138');
    await check();
    await page.reload();
    await check();
  });
}

test('unsupported table fields and source groups share Unverified while preserving numbers and genuine review passages', async ({ page }) => {
  const saved = savedJob('table', { value: claim({ evidence: [] }), payment_term: null,
    penalty: claim({ text: '0.05% per day', evidence: [{ ...evidence(), page: null }] }) });
  await page.route('**/jobs/138', route => route.fulfill({ json: saved }));
  async function check() {
    const row = page.getByRole('table', { name: 'So sánh điều khoản tài chính' }).locator('tbody tr');
    await expect(row.locator('.table-field-value .claim-text')).toHaveText(amount);
    await expect(row.locator('.table-field-penalty .claim-text')).toHaveText('0.05% per day');
    for (const field of ['value', 'payment_term', 'penalty']) {
      await expect(row.locator(`.table-field-${field} .unverified-badge`)).toHaveCount(1);
      await expect(row.locator(`.table-source-${field} .unverified-badge`)).toHaveCount(1);
      await expect(row.locator(`.table-source-${field}`).getByRole('link')).toHaveCount(0);
    }
  }
  await page.goto('/results/138');
  await check();
  await page.reload();
  await check();
});

test('mixed sources retain only real source references, and verification issues cannot be overridden by label confidence', async ({ page }) => {
  const saved = savedJob('bullet', { bullets: [claim({ evidence: [null, evidence()] })],
    actions: [claim({ verification_issues: ['unsupported_fact'] })] });
  await page.route('**/jobs/138', route => route.fulfill({ json: saved }));
  await page.goto('/results/138');
  for (const region of [page.getByRole('region', { name: 'Tóm tắt điểm chính', exact: true }),
    page.getByRole('region', { name: 'Recommended actions', exact: true })]) {
    await expect(region.locator('.unverified-badge')).toHaveCount(1);
    await expect(region.getByRole('link')).toHaveCount(1);
    await expect(region.getByRole('link')).toHaveAttribute('href', `/documents/51?page=6&start=0&end=${amount.length}&evidence=51-6-0-${amount.length}&job=138`);
  }
});

test('missing concept descriptions use the same Unverified state; low label confidence does not invalidate grounded facts', async ({ page }) => {
  const saved = savedJob('concept', { concepts: [
    { name: 'Unsupported concept', description: null },
    { name: 'Grounded concept', description: claim() },
  ] }, { ai_confidence: .79, confidence_level: 'low', review_state: 'needs_review', user_label: null });
  await page.route('**/jobs/138', route => route.fulfill({ json: saved }));
  await page.goto('/results/138');
  const missing = page.getByTestId('concept-card-0');
  await expect(missing.locator('.unverified-badge')).toHaveCount(1);
  await expect(missing.getByRole('link')).toHaveCount(0);
  const grounded = page.getByTestId('concept-card-1');
  await expect(grounded.getByRole('link')).toHaveCount(1);
  await expect(grounded.locator('.unverified-badge')).toHaveCount(0);
  await expect(page.locator('.analysis-label').getByTestId('document-review-state')).toContainText('Needs review');
});
