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

function mockMacroeconomicsDocument() {
  const version = 'e'.repeat(64);
  const pages = Array.from({ length: 24 }, (_, i) => {
    const pageNum = i + 1;
    if (pageNum === 2) {
      return {
        page: 2,
        text: 'Nghiên cứu kinh tế vĩ mô: lạm phát tiền tệ và lạm phát chi phí đẩy trong nền kinh tế.',
      };
    }
    if (pageNum === 12) {
      return {
        page: 12,
        text: 'Phân tích nguyên nhân: inflation causes include demand-pull pressures and supply shock. Tác động của lạm phát tới lãi suất.',
      };
    }
    return {
      page: pageNum,
      text: `Nội dung tổng quát bài nghiên cứu trang ${pageNum}.`,
    };
  });

  return {
    page_count: 24,
    page_kind: 'page',
    reader_version: version,
    reader_url: `/documents/99/reader.pdf?version=${version}`,
    pages,
    ai_label: 'Macroeconomics',
    ai_confidence: 0.87,
    review_state: 'needs_review',
    folder_id: null,
    original_filename: 'macroeconomics_paper.pdf',
  };
}

test.beforeEach(async ({ page }) => {
  const login = await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(login.status()).toBe(200);
});

test.describe('In-Document Reader Search (US04)', () => {
  test('searching "inflation causes" jumps to page 12 and highlights the matching passage', async ({ page }) => {
    const docData = mockMacroeconomicsDocument();
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfFixture(),
    }));

    // Start on page 1
    await page.goto('/documents/99?page=1');
    await expect(page.getByText('Trang 1/24', { exact: true })).toBeVisible();

    // Find and use the search bar
    const searchInput = page.getByTestId('reader-search-input');
    await expect(searchInput).toBeVisible();
    await searchInput.fill('inflation causes');
    await page.getByTestId('reader-search-button').click();

    // 1. Acceptance Criterion: The reader immediately moves to page 12
    await expect(page).toHaveURL(/page=12/);
    await expect(page.getByText('Trang 12/24', { exact: true })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Chọn trang nguồn' })).toHaveValue('12');

    // 2. Match counter shows 1/1
    const matchCount = page.getByTestId('search-match-count');
    await expect(matchCount).toBeVisible();
    await expect(matchCount).toContainText('1/1 kết quả');

    // 3. Highlighted passage card on page 12
    const matchCard = page.locator('.search-match-card');
    await expect(matchCard).toBeVisible();
    await expect(matchCard).toContainText('Kết quả tìm kiếm (1/1) — Trang 12');
    await expect(matchCard).toContainText('inflation causes');

    // 4. Passage highlight in text layer
    const highlightedSpan = page.locator('.reader-text-layer mark.search-highlight.active-match');
    await expect(highlightedSpan).toBeVisible();
    await expect(highlightedSpan).toHaveText('inflation causes');
  });

  test('repeated matches support moving between occurrences across pages with active highlight', async ({ page }) => {
    const docData = mockMacroeconomicsDocument();
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfFixture(),
    }));

    // Start on page 1
    await page.goto('/documents/99?page=1');

    // Search for repeated term "lạm phát" (occurs 2 times on page 2, 1 time on page 12 -> 3 total matches)
    const searchInput = page.getByTestId('reader-search-input');
    await searchInput.fill('lạm phát');
    await page.getByTestId('reader-search-button').click();

    // Match 1: Automatically jumps to first match on page 2
    await expect(page).toHaveURL(/page=2/);
    await expect(page.getByText('Trang 2/24', { exact: true })).toBeVisible();
    const countBadge = page.getByTestId('search-match-count');
    await expect(countBadge).toContainText('1/3 kết quả');

    // Page 2 text layer has 2 search-highlight marks, with the first one active
    const page2Highlights = page.locator('.reader-text-layer mark.search-highlight');
    await expect(page2Highlights).toHaveCount(2);
    await expect(page2Highlights.first()).toHaveClass(/active-match/);
    await expect(page2Highlights.nth(1)).toHaveClass(/other-match/);

    // Click Next (Sau) -> Match 2: Still on page 2, active highlight shifts to second occurrence
    await page.getByTestId('next-match-btn').click();
    await expect(countBadge).toContainText('2/3 kết quả');
    await expect(page.getByText('Trang 2/24', { exact: true })).toBeVisible();
    await expect(page2Highlights.first()).toHaveClass(/other-match/);
    await expect(page2Highlights.nth(1)).toHaveClass(/active-match/);

    // Click Next (Sau) -> Match 3: Jumps across pages to page 12!
    await page.getByTestId('next-match-btn').click();
    await expect(countBadge).toContainText('3/3 kết quả');
    await expect(page).toHaveURL(/page=12/);
    await expect(page.getByText('Trang 12/24', { exact: true })).toBeVisible();
    const page12Highlight = page.locator('.reader-text-layer mark.search-highlight.active-match');
    await expect(page12Highlight).toBeVisible();
    await expect(page12Highlight).toHaveText('lạm phát');

    // Click Prev (Trước) -> Moves back to Match 2 on page 2
    await page.getByTestId('prev-match-btn').click();
    await expect(countBadge).toContainText('2/3 kết quả');
    await expect(page).toHaveURL(/page=2/);
    await expect(page.getByText('Trang 2/24', { exact: true })).toBeVisible();

    // Click Prev (Trước) -> Moves back to Match 1 on page 2
    await page.getByTestId('prev-match-btn').click();
    await expect(countBadge).toContainText('1/3 kết quả');
    await expect(page2Highlights.first()).toHaveClass(/active-match/);
  });

  test('empty query and clearing search reset search state and highlights', async ({ page }) => {
    const docData = mockMacroeconomicsDocument();
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfFixture(),
    }));

    await page.goto('/documents/99?page=1');
    const searchInput = page.getByTestId('reader-search-input');

    // Search and verify matches exist
    await searchInput.fill('inflation causes');
    await page.getByTestId('reader-search-button').click();
    await expect(page.getByTestId('search-match-count')).toBeVisible();

    // Click clear button
    const clearBtn = page.getByTestId('reader-search-clear');
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();

    // Verify search input is cleared and search state is reset
    await expect(searchInput).toHaveValue('');
    await expect(page.getByTestId('search-match-count')).toHaveCount(0);
    await expect(page.locator('.search-match-card')).toHaveCount(0);
    await expect(page.locator('.reader-text-layer mark.search-highlight')).toHaveCount(0);
  });

  test('no-results state displays clear message without breaking reader', async ({ page }) => {
    const docData = mockMacroeconomicsDocument();
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfFixture(),
    }));

    await page.goto('/documents/99?page=1');
    const searchInput = page.getByTestId('reader-search-input');

    // Search for non-existent term
    await searchInput.fill('nonexistent_economic_term_xyz');
    await page.getByTestId('reader-search-button').click();

    // Verify no-results state
    const noResultsMsg = page.getByTestId('search-no-results');
    await expect(noResultsMsg).toBeVisible();
    await expect(noResultsMsg).toContainText('Không tìm thấy kết quả phù hợp');
    await expect(page.getByTestId('search-match-count')).toHaveCount(0);
    await expect(page.locator('.reader-text-layer mark.search-highlight')).toHaveCount(0);

    // Verify reader remains functional on current page
    await expect(page.getByText('Trang 1/24', { exact: true })).toBeVisible();
  });

  test('direct URL search parameter auto-triggers search and jumps to matching page', async ({ page }) => {
    const docData = mockMacroeconomicsDocument();
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfFixture(),
    }));

    // Navigate with ?search=inflation%20causes
    await page.goto('/documents/99?search=inflation%20causes');

    // Automatically jumps to page 12
    await expect(page).toHaveURL(/page=12/);
    await expect(page.getByText('Trang 12/24', { exact: true })).toBeVisible();
    await expect(page.getByTestId('search-match-count')).toContainText('1/1 kết quả');
    await expect(page.locator('.reader-text-layer mark.search-highlight.active-match')).toHaveText('inflation causes');
  });

  test('documented page text endpoint provides authorized text layer for reader search', async ({ page }) => {
    const docData = mockMacroeconomicsDocument();
    await page.route('**/api/documents/99/pages', route => route.fulfill({ json: docData }));
    await page.route('**/api/documents/99/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: pdfFixture(),
    }));
    await page.route('**/api/documents/99/pages/12/text', route => route.fulfill({
      json: {
        document_id: 99,
        page: 12,
        text: 'Phân tích nguyên nhân: inflation causes include demand-pull pressures.',
        positions: [{ start: 24, end: 40, x: 72, y: 720 }],
      },
    }));

    await page.goto('/documents/99?page=12');
    const result = await page.evaluate(async () => {
      const res = await fetch('/api/documents/99/pages/12/text');
      return { status: res.status, data: await res.json() };
    });

    expect(result.status).toBe(200);
    expect(result.data.document_id).toBe(99);
    expect(result.data.page).toBe(12);
    expect(result.data.text).toContain('inflation causes');
  });
});

