import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { user, searchHit } from './helpers';

test.beforeEach(async ({ page }) => {
  const login = await page.request.post('/auth/login', {
    form: { username: user.email, password: user.password },
  });
  expect(login.status()).toBe(200);
});

test.describe('Citation and Evidence Shared Components (US08 / BR05)', () => {
  test('renders valid evidence as "Document name — trang X" and carries evidence ID and optional return job ID', async ({ page }) => {
    const jobData = {
      id: 99,
      status: 'completed',
      file_count: 1,
      completed_count: 1,
      job_files: [
        { id: 1, document_id: 25, original_filename: 'nda_agreement.pdf', status: 'completed', attempt_count: 1 },
      ],
      result_data: {
        schema_version: 1,
        documents: {
          '25': {
            schema_version: 1,
            document_id: 25,
            original_filename: 'nda_agreement.pdf',
            mode: 'bullet',
            analysis_status: 'completed',
            reader: { page_count: 5, page_kind: 'page' },
            label: { ai_label: 'NDA', ai_confidence: 0.95, confidence_level: 'high' },
            warnings: [],
            output: {
              type: 'bullet',
              bullets: [
                {
                  text: 'Thời hạn bảo mật là 5 năm.',
                  unverified: false,
                  evidence: [
                    {
                      document_id: 25,
                      page: 3,
                      start: 120,
                      end: 146,
                      quote: 'Thời hạn bảo mật là 5 năm.',
                      reader_version: 'b'.repeat(64),
                    },
                  ],
                },
              ],
              actions: [
                {
                  text: 'Ký phụ lục bổ sung.',
                  unverified: false,
                  evidence: [
                    {
                      document_id: 25,
                      page: 4,
                      start: 50,
                      end: 70,
                      quote: 'Ký phụ lục bổ sung.',
                      reader_version: 'b'.repeat(64),
                    },
                  ],
                },
              ],
            },
          },
        },
      },
    };

    await page.route('**/jobs/99', route => route.fulfill({ json: jobData }));
    await page.goto('/results/99');

    const analysisRegion = page.getByRole('region', { name: 'Kết quả phân tích AI' });

    // 1. Verify badge text format: "Document name — trang X"
    const citationLink = analysisRegion.getByRole('link', { name: 'nda_agreement.pdf — trang 3', exact: true });
    await expect(citationLink).toBeVisible();

    // 2. Verify citation link carries document ID, page, offsets, evidence ID, and return job ID
    const href = await citationLink.getAttribute('href');
    expect(href).toContain('/documents/25');
    const parsedUrl = new URL(href, 'http://127.0.0.1');
    expect(parsedUrl.searchParams.get('page')).toBe('3');
    expect(parsedUrl.searchParams.get('start')).toBe('120');
    expect(parsedUrl.searchParams.get('end')).toBe('146');
    expect(parsedUrl.searchParams.get('evidence')).toBe('25-3-120-146');
    expect(parsedUrl.searchParams.get('job')).toBe('99');

    // Action citation link
    const actionLink = analysisRegion.getByRole('link', { name: 'nda_agreement.pdf — trang 4', exact: true });
    await expect(actionLink).toBeVisible();
    const actionHref = await actionLink.getAttribute('href');
    expect(actionHref).toContain('evidence=25-4-50-70');
    expect(actionHref).toContain('job=99');
  });

  test('unsupported claims show Chưa xác thực badge without any fake link', async ({ page }) => {
    const jobData = {
      id: 101,
      status: 'completed',
      file_count: 1,
      completed_count: 1,
      job_files: [
        { id: 1, document_id: 30, original_filename: 'spec.pdf', status: 'completed', attempt_count: 1 },
      ],
      result_data: {
        schema_version: 1,
        documents: {
          '30': {
            schema_version: 1,
            document_id: 30,
            original_filename: 'spec.pdf',
            mode: 'bullet',
            analysis_status: 'completed',
            reader: { page_count: 3, page_kind: 'page' },
            label: { ai_label: 'Spec', ai_confidence: 0.9, confidence_level: 'high' },
            warnings: [],
            output: {
              type: 'bullet',
              bullets: [
                {
                  text: 'Hệ thống hỗ trợ 100.000 người dùng đồng thời.',
                  unverified: true,
                  evidence: [],
                },
              ],
              actions: [
                {
                  text: 'Thực hiện stress test.',
                  unverified: true,
                  evidence: [],
                },
              ],
            },
          },
        },
      },
    };

    await page.route('**/jobs/101', route => route.fulfill({ json: jobData }));
    await page.goto('/results/101');

    const analysisRegion = page.getByRole('region', { name: 'Kết quả phân tích AI' });

    // Verify Chưa xác thực text is displayed
    const unverifiedBadges = analysisRegion.locator('.unverified-badge');
    await expect(unverifiedBadges).toHaveCount(2);
    await expect(unverifiedBadges.first()).toContainText('Chưa xác thực');

    // Crucial requirement: Unsupported claims show Chưa xác thực without a fake link
    // Ensure that unverified badges are NOT <a> tags and do not contain links
    for (const badge of await unverifiedBadges.all()) {
      const tagName = await badge.evaluate(el => el.tagName.toLowerCase());
      expect(tagName).toBe('span');
      const hasAnchorParent = await badge.evaluate(el => Boolean(el.closest('a')));
      expect(hasAnchorParent).toBe(false);
    }

    // Ensure no citation links were rendered in the claim citations area
    const claimCitations = analysisRegion.locator('.evidence-badges a');
    await expect(claimCitations).toHaveCount(0);
  });

  test('separate multi-source badges when two documents support one claim', async ({ page }) => {
    const jobData = {
      id: 102,
      status: 'completed',
      file_count: 1,
      completed_count: 1,
      job_files: [
        { id: 1, document_id: 41, original_filename: 'merger_terms.pdf', status: 'completed', attempt_count: 1 },
      ],
      result_data: {
        schema_version: 1,
        documents: {
          '41': {
            schema_version: 1,
            document_id: 41,
            original_filename: 'merger_terms.pdf',
            mode: 'table',
            analysis_status: 'completed',
            reader: { page_count: 8, page_kind: 'page' },
            label: { ai_label: 'Hợp đồng', ai_confidence: 0.9, confidence_level: 'high' },
            warnings: [],
            output: {
              type: 'table',
              value: {
                text: 'Giá trị chuyển nhượng là 10 tỷ VNĐ.',
                unverified: false,
                evidence: [
                  {
                    document_id: 41,
                    page: 1,
                    start: 10,
                    end: 46,
                    quote: 'Giá trị chuyển nhượng là 10 tỷ VNĐ.',
                    reader_version: 'c'.repeat(64),
                  },
                  {
                    document_id: 42,
                    page: 5,
                    start: 80,
                    end: 116,
                    quote: 'Giá trị chuyển nhượng là 10 tỷ VNĐ.',
                    reader_version: 'd'.repeat(64),
                  },
                ],
              },
              payment_term: {
                text: 'Thanh toán thành 3 đợt.',
                unverified: false,
                evidence: [
                  {
                    document_id: 41,
                    page: 2,
                    start: 5,
                    end: 28,
                    quote: 'Thanh toán thành 3 đợt.',
                    reader_version: 'c'.repeat(64),
                  },
                ],
              },
              penalty: { text: null, evidence: [], unverified: true },
            },
          },
        },
      },
    };

    await page.route('**/jobs/102', route => route.fulfill({ json: jobData }));
    await page.goto('/results/102');

    const analysisRegion = page.getByRole('region', { name: 'Kết quả phân tích AI' });

    // Claim with 2 evidence sources renders 2 separate badges
    const badgeDoc1 = analysisRegion.getByRole('link', { name: 'merger_terms.pdf — trang 1', exact: true });
    const badgeDoc2 = analysisRegion.getByRole('link', { name: 'Tài liệu #42 — trang 5', exact: true });

    await expect(badgeDoc1).toBeVisible();
    await expect(badgeDoc2).toBeVisible();

    // Verify distinct links and targets
    const href1 = await badgeDoc1.getAttribute('href');
    const href2 = await badgeDoc2.getAttribute('href');
    expect(href1).toContain('/documents/41?page=1');
    expect(href1).toContain('evidence=41-1-10-46');
    expect(href1).toContain('job=102');

    expect(href2).toContain('/documents/42?page=5');
    expect(href2).toContain('evidence=42-5-80-116');
    expect(href2).toContain('job=102');

    // Missing penalty cell shows unverified without fake link
    await expect(analysisRegion.getByText('Không có thông tin · Chưa xác thực')).toBeVisible();
  });

  test('slide kind renders as "Document name — trang chiếu X"', async ({ page }) => {
    const jobData = {
      id: 103,
      status: 'completed',
      file_count: 1,
      completed_count: 1,
      job_files: [
        { id: 1, document_id: 50, original_filename: 'presentation.pptx', status: 'completed', attempt_count: 1 },
      ],
      result_data: {
        schema_version: 1,
        documents: {
          '50': {
            schema_version: 1,
            document_id: 50,
            original_filename: 'presentation.pptx',
            mode: 'concept',
            analysis_status: 'completed',
            reader: { page_count: 12, page_kind: 'slide' },
            label: { ai_label: 'Bài thuyết trình', ai_confidence: 0.88, confidence_level: 'high' },
            warnings: [],
            output: {
              type: 'concept',
              concepts: [
                {
                  name: 'Mục tiêu tăng trưởng',
                  description: {
                    text: 'Tăng trưởng 25% năm 2027.',
                    unverified: false,
                    evidence: [
                      {
                        document_id: 50,
                        page: 4,
                        start: 15,
                        end: 41,
                        quote: 'Tăng trưởng 25% năm 2027.',
                        reader_version: 'e'.repeat(64),
                      },
                    ],
                  },
                },
              ],
            },
          },
        },
      },
    };

    await page.route('**/jobs/103', route => route.fulfill({ json: jobData }));
    await page.goto('/results/103');

    const analysisRegion = page.getByRole('region', { name: 'Kết quả phân tích AI' });
    const slideBadge = analysisRegion.getByRole('link', { name: 'presentation.pptx — trang chiếu 4', exact: true });
    await expect(slideBadge).toBeVisible();
    await expect(slideBadge).toHaveAttribute(
      'href',
      '/documents/50?page=4&start=15&end=41&evidence=50-4-15-41&job=103'
    );
  });

  test('workspace history does not run global content search or display fabricated source citations', async ({ page }) => {
    let calls = 0;
    await page.route('**/api/search?*', route => { calls++; return route.abort(); });
    await page.goto('/workspace');
    await expect(page.locator('.workspace-search')).toHaveCount(0);
    await expect(page.locator('main .citation-badge')).toHaveCount(0);
    expect(calls).toBe(0);
  });

  test('citation link with return job ID displays return button in document reader', async ({ page }) => {
    const version = 'f'.repeat(64);
    await page.route('**/api/documents/88/pages', route => route.fulfill({
      json: {
        page_count: 5,
        page_kind: 'page',
        reader_version: version,
        reader_url: `/documents/88/reader.pdf?version=${version}`,
        pages: [{ page: 1, text: 'Sample page' }, { page: 2, text: 'Evidence text' }],
      },
    }));
    await page.route('**/api/documents/88/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf',
      body: Buffer.from('%PDF-1.4\n%EOF\n'),
    }));

    // Navigate to document reader with return job ID param
    await page.goto('/documents/88?page=2&evidence=88-2-0-10&job=105');

    // Verify return button is visible and points to /results/105
    const returnLink = page.getByRole('link', { name: 'Về kết quả · Quay lại tác vụ #105', exact: true });
    await expect(returnLink).toBeVisible();
    await expect(returnLink).toHaveAttribute('href', '/results/105');
  });
});

test('TC-US09-14 citation jumps to the real evidence page, highlights it and returns to its originating job', async ({ page }) => {
  const source = readFileSync(new URL('../../backend/test/fixtures/acceptance/report-15-pages.pdf', import.meta.url));
  const uploaded = await page.request.post('/api/upload', {
    multipart: { files: { name: 'citation-report.pdf', mimeType: 'application/pdf', buffer: source }, mode: 'bullet' },
  });
  expect(uploaded.status()).toBe(202);
  const { jobId } = await uploaded.json();
  let saved;
  await expect.poll(async () => {
    saved = await (await page.request.get(`/jobs/${jobId}`)).json();
    return saved.status;
  }).toBe('completed');
  const documentId = saved.job_files[0].document_id;
  const metadata = await (await page.request.get(`/api/documents/${documentId}/pages`)).json();
  const sourcePage = metadata.pages[1];
  expect(sourcePage.page).toBe(2);
  expect(sourcePage.positions.length).toBeGreaterThan(0);
  const start = sourcePage.positions[0].start;
  const end = sourcePage.positions[Math.min(14, sourcePage.positions.length - 1)].end;
  const quote = Array.from(sourcePage.text).slice(start, end).join('');
  const evidence = { document_id: documentId, page: 2, start, end, quote, reader_version: metadata.reader_version };
  const claimText = 'Fixed claim supported by the report on page 2.';
  const job = { ...saved, result_data: { schema_version: 1, documents: {
    [documentId]: { ...saved.result_data.documents[String(documentId)], analysis_status: 'completed',
      output: { type: 'bullet', bullets: [{ text: claimText, unverified: false, evidence: [evidence] }], actions: [] } },
  } } };
  // Pin the actual highlighted response before browser navigation so the
  // in-memory E2E database is not accessed by concurrent PDF download tasks.
  const highlightedUrl = `/api${metadata.reader_url}&highlight_page=2&start=${start}&end=${end}`;
  const highlighted = await page.request.get(highlightedUrl);
  expect(highlighted.status()).toBe(200);
  expect(highlighted.headers()['content-type']).toBe('application/pdf');
  expect(highlighted.headers()['x-reader-version']).toBe(metadata.reader_version);
  const highlightedBytes = await highlighted.body();
  expect(highlightedBytes).not.toEqual(source);
  const original = await page.request.get(`/api${metadata.reader_url}`);
  expect(await original.body()).toEqual(source);
  await page.route(`**/api/documents/${documentId}/reader.pdf?*`, route => route.fulfill({
    contentType: 'application/pdf', body: highlightedBytes,
  }));
  await page.route(`**/api/documents/${documentId}/summary*`, route => route.fulfill({ json: { document: null } }));
  await page.route(`**/jobs/${jobId}`, route => route.fulfill({ json: job }));
  await page.goto(`/results/${jobId}`);
  await expect(page.getByText(claimText, { exact: true })).toBeVisible();
  const citation = page.locator(`.citation-badge[data-document-id="${documentId}"][data-page="2"]`).first();
  await expect(citation).toBeVisible();
  await expect(citation).toHaveAttribute('title', quote);
  await expect(citation).toHaveAttribute('data-evidence-id', `${documentId}-2-${start}-${end}`);
  await citation.click();
  await expect(page).toHaveURL(new RegExp(`/documents/${documentId}\\?page=2&start=${start}&end=${end}&evidence=.*&job=${jobId}$`));
  await expect(page.getByRole('combobox', { name: 'Chọn trang nguồn' })).toHaveValue('2');
  const frame = page.getByTitle('Bản đọc PDF — Trang 2');
  await expect(frame).toBeVisible();
  await expect(frame).toHaveAttribute('src', `/api${metadata.reader_url}&highlight_page=2&start=${start}&end=${end}#page=2`);
  await expect(page.locator('.reader-highlight-note')).toBeVisible();
  await expect(page.locator('.highlight-fallback-notice')).toHaveCount(0);
  const back = page.getByRole('link', { name: `Về kết quả · Quay lại tác vụ #${jobId}`, exact: true });
  await expect(back).toHaveAttribute('href', `/results/${jobId}`);
  await back.click();
  await expect(page).toHaveURL(`/results/${jobId}`);
  await expect(page.getByText(claimText, { exact: true })).toBeVisible();
});

for (const [caseId, overrides] of [
  ['TC-US09-15', { page: 0 }],
  ['TC-US09-16', { start: 20, end: 10 }],
  ['TC-US09-17', { reader_version: 'invalid' }],
]) {
  test(`${caseId} invalid citation is Unverified and has no navigation link`, async ({ page }) => {
    const evidence = { document_id: 25, page: 2, start: 0, end: 12,
      quote: '0.05 per day', reader_version: 'a'.repeat(64), ...overrides };
    const text = 'Claim with an invalid citation.';
    await page.route('**/jobs/109', route => route.fulfill({ json: {
      id: 109, status: 'completed', file_count: 1, completed_count: 1,
      job_files: [{ id: 1, document_id: 25, original_filename: 'invalid.pdf', status: 'completed' }],
      result_data: { schema_version: 1, documents: { '25': { schema_version: 1, document_id: 25, original_filename: 'invalid.pdf', mode: 'bullet',
        analysis_status: 'completed', reader: { page_count: 3, page_kind: 'page' },
        output: { type: 'bullet', bullets: [{ text, unverified: false, evidence: [evidence] }], actions: [] } } } },
    } }));
    await page.goto('/results/109');
    const region = page.getByRole('region', { name: 'Kết quả phân tích AI' });
    await expect(region.getByText(text, { exact: true })).toBeVisible();
    await expect(region.locator('.unverified-badge')).toBeVisible();
    await expect(region.locator('.citation-badge')).toHaveCount(0);
  });
}
