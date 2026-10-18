import { test, expect } from '@playwright/test';
import { user, searchHit } from './helpers';

function makePageData(overrides = {}) {
  const version = 'b'.repeat(64);
  return {
    page_count: 3,
    page_kind: 'page',
    reader_version: version,
    reader_url: `/documents/99/reader.pdf?version=${version}`,
    pages: [
      { page: 1, text: 'Nội dung trang 1 hợp đồng kinh tế.' },
      { page: 2, text: 'Điều khoản thanh toán trang 2.' },
      { page: 3, text: 'Chữ ký các bên trang 3.' },
    ],
    ai_label: 'Hợp đồng kinh tế',
    ai_confidence: 0.87,
    review_state: 'needs_review',
    user_label: null,
    folder_id: null,
    original_filename: 'hop_dong_kinh_te.pdf',
    ...overrides,
  };
}

function pdfBuffer() {
  const text = 'BT /F1 12 Tf 72 720 Td (Sample PDF Content) Tj ET';
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 1 /Kids [4 0 R] >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>',
    `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
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

test.beforeEach(async ({ page }) => {
  const login = await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(login.status()).toBe(200);
});

test.describe('Document Metadata UI - Threshold Display & Boundary (US10)', () => {
  const scenarios = [
    { score: 0.87, expectedText: '87%', isHigh: true, expectNeedsReview: false },
    { score: 0.80, expectedText: '80%', isHigh: true, expectNeedsReview: false },
    { score: 0.79, expectedText: '79%', isHigh: false, expectNeedsReview: true },
    { score: 0.72, expectedText: '72%', isHigh: false, expectNeedsReview: true },
  ];

  for (const { score, expectedText, isHigh, expectNeedsReview } of scenarios) {
    test(`renders confidence threshold ${expectedText} in reader (score: ${score})`, async ({ page }) => {
      const docData = makePageData({
        ai_confidence: score,
        ai_label: 'Hợp đồng mua bán',
      });

      await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
      await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
        contentType: 'application/pdf',
        body: pdfBuffer(),
      }));

      await page.goto('/documents/99');

      // Verify metadata component is present in reader
      const metadata = page.locator('.reader-document-metadata');
      await expect(metadata).toBeVisible();

      // Check AI label
      const labelBadge = metadata.locator('[data-testid="document-ai-label"]');
      await expect(labelBadge).toContainText('Hợp đồng mua bán');

      // Check confidence badge and threshold classification
      const confBadge = metadata.locator('[data-testid="document-ai-confidence"]');
      await expect(confBadge).toContainText(`Độ tin cậy: ${expectedText}`);
      if (isHigh) {
        await expect(confBadge).toHaveClass(/confidence-high/);
        await expect(confBadge).toHaveAttribute('data-confidence-level', 'high');
      } else {
        await expect(confBadge).toHaveClass(/confidence-low/);
        await expect(confBadge).toHaveAttribute('data-confidence-level', 'low');
      }

      // Check Needs review state
      const reviewBadge = metadata.locator('[data-testid="document-review-state"]');
      if (expectNeedsReview) {
        await expect(reviewBadge).toContainText('Needs review');
        await expect(reviewBadge).toHaveClass(/review-needs-review/);
      } else {
        await expect(reviewBadge).not.toContainText('Needs review');
        await expect(reviewBadge).toContainText('Gợi ý độ tin cậy cao');
      }
    });
  }
});

test.describe('Document Metadata UI - Unchanged Folder Placement (US10)', () => {
  test('unassigned folder remains unchanged and displays Unassigned state', async ({ page }) => {
    const docData = makePageData({ folder_id: null });
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfBuffer(),
    }));

    await page.goto('/documents/99');
    const folderBadge = page.locator('.reader-document-metadata [data-testid="document-folder-placement"]');
    await expect(folderBadge).toBeVisible();
    await expect(folderBadge).toContainText('Chưa phân thư mục (Unassigned)');
    await expect(folderBadge).toHaveAttribute('data-folder-id', 'unassigned');
  });

  test('pre-assigned folder remains unchanged and displays folder identifier', async ({ page }) => {
    const docData = makePageData({ folder_id: 42 });
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfBuffer(),
    }));

    await page.goto('/documents/99');
    const folderBadge = page.locator('.reader-document-metadata [data-testid="document-folder-placement"]');
    await expect(folderBadge).toBeVisible();
    await expect(folderBadge).toContainText('#42');
    await expect(folderBadge).toHaveAttribute('data-folder-id', '42');
  });
});

test.describe('Document Metadata UI - Integration & Verification Distinctness', () => {
  test('workspace document rows integrate metadata UI alongside document links', async ({ page }) => {
    const mockDocs = [
      {
        id: 101,
        original_filename: 'hop_dong_thue_nha.pdf',
        ai_label: 'Hợp đồng thuê',
        ai_confidence: 0.88,
        review_state: 'needs_review',
        folder_id: null,
        user_label: null,
      },
      {
        id: 102,
        original_filename: 'hoa_don_vat.pdf',
        ai_label: 'Hóa đơn',
        ai_confidence: 0.74,
        review_state: 'needs_review',
        folder_id: 15,
        user_label: 'Chi phí Q3',
      },
    ];

    await page.route('**/api/documents?*', route => route.fulfill({ json: mockDocs }));
    await page.goto('/workspace');

    const rows = page.locator('.workspace-document-row');
    await expect(rows).toHaveCount(2);

    // Row 1: High confidence suggestion, unassigned folder
    const row1 = rows.first();
    await expect(row1.locator('.document-row-title')).toContainText('hop_dong_thue_nha.pdf');
    await expect(row1.locator('[data-testid="document-ai-label"]')).toContainText('Hợp đồng thuê');
    await expect(row1.locator('[data-testid="document-ai-confidence"]')).toContainText('88%');
    await expect(row1.locator('[data-testid="document-folder-placement"]')).toContainText('Chưa phân thư mục');

    // Row 2: Low confidence suggestion (Needs review), assigned folder, user label
    const row2 = rows.nth(1);
    await expect(row2.locator('.document-row-title')).toContainText('hoa_don_vat.pdf');
    await expect(row2.locator('[data-testid="document-ai-confidence"]')).toContainText('74%');
    await expect(row2.locator('[data-testid="document-review-state"]')).toContainText('Needs review');
    await expect(row2.locator('[data-testid="document-folder-placement"]')).toContainText('#15');
    await expect(row2.locator('[data-testid="document-user-label"]')).toContainText('Chi phí Q3');
  });

  test('workspace search hits display metadata distinct from claim verification citations', async ({ page }) => {
    await page.route('**/api/search?*', route => route.fulfill({
      json: { query: 'tài chính', total_hits: 1, hits: [searchHit()] },
    }));

    await page.goto('/workspace');
    await page.getByLabel('Tìm kiếm trong tài liệu').fill('tài chính');
    await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();

    const hitCard = page.locator('.search-hit-card').first();
    await expect(hitCard).toBeVisible();

    // Check DocumentMetadata inside search hit
    const hitMetadata = hitCard.locator('[data-testid="document-metadata"]');
    await expect(hitMetadata).toBeVisible();
    await expect(hitMetadata.locator('[data-testid="document-ai-label"]')).toContainText('Báo cáo');
    await expect(hitMetadata.locator('[data-testid="document-ai-confidence"]')).toHaveCount(0);
    await expect(hitMetadata.locator('[data-testid="document-review-state"]')).toContainText('Chưa có điểm tin cậy');

    // Check CitationBadge is distinct and separate
    const citationBadge = hitCard.locator('.citation-badge');
    await expect(citationBadge).toBeVisible();
    await expect(citationBadge).toContainText('bao_cao_tai_chinh.pdf — page 1');

    // Crucial requirement: AI confidence is NOT a claim citation badge
    const labelBadge = hitMetadata.locator('[data-testid="document-ai-label"]');
    const isCitationBadge = await labelBadge.evaluate(el => el.classList.contains('citation-badge'));
    expect(isCitationBadge).toBe(false);
  });

  test('confirmation and edit controls are not duplicated in metadata UI (reserved for US12)', async ({ page }) => {
    const docData = makePageData({
      ai_label: 'Hợp đồng',
      ai_confidence: 0.85,
    });
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfBuffer(),
    }));

    await page.goto('/documents/99');
    const metadata = page.locator('.reader-document-metadata');
    await expect(metadata).toBeVisible();

    // Ensure no form inputs or confirmation buttons exist in DocumentMetadata
    await expect(metadata.locator('button')).toHaveCount(0);
    await expect(metadata.locator('input')).toHaveCount(0);
    await expect(metadata.locator('select')).toHaveCount(0);
  });
});
