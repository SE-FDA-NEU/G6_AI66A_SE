import { test, expect } from '@playwright/test';
import { user, searchHit } from './helpers';

test.beforeEach(async ({ page }) => {
  expect((await page.request.post('/auth/login', { form: { username: user.email, password: user.password } })).status()).toBe(200);
});

function documents(count = 12) {
  return Array.from({ length: count }, (_, index) => ({ id: index + 1, original_filename: `contract-${index + 1}.pdf`,
    ai_label: 'Contract', ai_confidence: .9, review_state: 'needs_review', folder_id: null }));
}

test('list pagination requests server pages, retains badges and provides document/upload navigation', async ({ page }) => {
  const docs = documents();
  await page.route('**/api/documents?*', route => {
    const params = new URL(route.request().url()).searchParams;
    const skip = Number(params.get('skip'));
    return route.fulfill({ json: docs.slice(skip, skip + Number(params.get('limit'))) });
  });
  await page.goto('/workspace');
  const rows = page.getByTestId('workspace-document-row');
  await expect(rows).toHaveCount(10);
  await expect(rows.first().getByTestId('document-ai-label')).toContainText('Contract');
  await expect(rows.first().getByTestId('document-ai-confidence')).toContainText('90%');
  const pagination = page.getByRole('navigation', { name: 'Phân trang tài liệu' });
  await expect(pagination.getByRole('button', { name: 'Trang trước' })).toBeDisabled();
  await pagination.getByRole('button', { name: 'Trang sau' }).click();
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText('contract-11.pdf');
  await expect(pagination.getByRole('button', { name: 'Trang sau' })).toBeDisabled();
  await expect(rows.first().getByRole('link')).toHaveAttribute('href', '/documents/11?page=1');
  await pagination.getByRole('button', { name: 'Trang trước' }).click();
  await expect(rows).toHaveCount(10);
  await page.getByRole('link', { name: 'Tải tài liệu', exact: true }).click();
  await expect(page).toHaveURL('/upload');
  await expect(page.getByLabel('Chọn tệp tài liệu')).toBeEnabled();
});

test('search preserves server ranking, sends filters and paginates independently of the document list', async ({ page }) => {
  await page.route('**/api/documents?*', route => route.fulfill({ json: documents(1) }));
  const requests = [];
  await page.route('**/api/search?*', route => {
    const params = new URL(route.request().url()).searchParams;
    requests.push(Object.fromEntries(params));
    const hits = Number(params.get('offset')) === 10 ? [searchHit({ document_id: 99, doc_name: 'last.pdf' })]
      : Array.from({ length: 10 }, (_, index) => searchHit({ document_id: 61 + index,
        doc_name: `rank-${index + 1}.pdf`, page: 6, score: 10 - index }));
    return route.fulfill({ json: { query: params.get('q'), total_hits: 11, hits } });
  });
  await page.goto('/workspace');
  await page.getByLabel('Tìm kiếm trong tài liệu', { exact: true }).fill('payment penalty');
  await page.getByLabel('Kiểu tìm kiếm').selectOption('semantic');
  await page.getByLabel('Lọc theo nhãn').fill('Contract');
  await page.getByLabel('Thư mục (#)', { exact: true }).fill('7');
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect(page.locator('.search-hit-card')).toHaveCount(10);
  await expect(page.locator('.search-hit-card').first()).toContainText('rank-1.pdf');
  await expect(page.locator('.search-hit-card').last()).toContainText('rank-10.pdf');
  expect(requests[0]).toEqual({ q: 'payment penalty', mode: 'semantic', label: 'Contract', folder_id: '7', limit: '10', offset: '0' });
  await expect(page.getByText('Tìm thấy 11 kết quả', { exact: false })).toBeVisible();
  await page.getByRole('navigation', { name: 'Phân trang tìm kiếm' }).getByRole('button', { name: 'Trang sau' }).click();
  await expect(page.locator('.search-hit-card')).toHaveCount(1);
  await expect(page.locator('.search-hit-heading')).toContainText('11. last.pdf');
  expect(requests[1].offset).toBe('10');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(1);
  await page.getByRole('button', { name: 'Xóa tìm kiếm' }).click();
  await expect(page.locator('.search-hit-card')).toHaveCount(0);
  await expect(page.getByLabel('Tìm kiếm trong tài liệu', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Kiểu tìm kiếm')).toHaveValue('content');
});

test('list and search distinguish loading, failures, retry and empty responses', async ({ page }) => {
  let listAttempts = 0;
  let releaseList;
  await page.route('**/api/documents?*', async route => {
    if (++listAttempts === 1) {
      await new Promise(resolve => { releaseList = resolve; });
      return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto('/workspace');
  await expect(page.getByText('Đang tải danh sách tài liệu…')).toBeVisible();
  await expect.poll(() => typeof releaseList).toBe('function');
  releaseList();
  await expect(page.locator('.workspace-documents').getByRole('alert')).toContainText('Không thể tải danh sách');
  await expect(page.getByText('Chưa có tài liệu nào', { exact: false })).toHaveCount(0);
  await page.getByRole('button', { name: 'Thử lại danh sách' }).click();
  await expect(page.getByText('Chưa có tài liệu nào', { exact: false })).toBeVisible();

  let searchAttempts = 0;
  let releaseSearch;
  await page.route('**/api/search?*', async route => {
    if (++searchAttempts === 1) {
      await new Promise(resolve => { releaseSearch = resolve; });
      return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    }
    return route.fulfill({ json: { query: 'absent', total_hits: 0, hits: [] } });
  });
  await page.getByLabel('Tìm kiếm trong tài liệu', { exact: true }).fill('absent');
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect(page.getByText('Đang tìm kiếm trong tài liệu…')).toBeVisible();
  await expect.poll(() => typeof releaseSearch).toBe('function');
  releaseSearch();
  await expect(page.locator('.workspace-search').getByRole('alert')).toContainText('Không thể tìm kiếm');
  await expect(page.getByText('Không tìm thấy kết quả phù hợp', { exact: false })).toHaveCount(0);
  await expect(page.getByLabel('Tìm kiếm trong tài liệu', { exact: true })).toHaveValue('absent');
  await page.getByRole('button', { name: 'Thử lại tìm kiếm' }).click();
  await expect(page.getByText('Không tìm thấy kết quả phù hợp', { exact: false })).toBeVisible();
  await expect(page.locator('.citation-badge')).toHaveCount(0);
});

test('invalid search response is actionable and a cleared pending search cannot restore stale hits', async ({ page }) => {
  await page.route('**/api/documents?*', route => route.fulfill({ json: [] }));
  let release;
  await page.route('**/api/search?*', async route => {
    const query = new URL(route.request().url()).searchParams.get('q');
    if (query === '!!!') return route.fulfill({ status: 422, json: { detail: 'Invalid' } });
    if (query === 'old') await new Promise(resolve => { release = resolve; });
    return route.fulfill({ json: { query, total_hits: 1, hits: [searchHit({ snippet: query })] } });
  });
  await page.goto('/workspace');
  const input = page.getByLabel('Tìm kiếm trong tài liệu', { exact: true });
  await input.fill('!!!');
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect(page.locator('.workspace-search').getByRole('alert')).toContainText('Nhập từ khóa có chữ hoặc số');
  await input.fill('old');
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect.poll(() => typeof release).toBe('function');
  await page.getByRole('button', { name: 'Xóa tìm kiếm' }).click();
  await input.fill('new');
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect(page.locator('.search-snippet')).toHaveText('new');
  release();
  await expect(page.locator('.search-snippet')).toHaveText('new');
});

function pdfFixture(texts) {
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>',
    `<< /Type /Pages /Count ${texts.length} /Kids [${texts.map((_, index) => `${4 + index * 2} 0 R`).join(' ')}] >>`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'];
  for (const text of texts) {
    const stream = `BT /F1 12 Tf 72 720 Td (${text}) Tj ET`;
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${objects.length + 2} 0 R >>`);
    objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
  }
  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 ${offsets.length}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) pdf += `${String(offset).padStart(10, '0')} 00000 n \n`;
  return Buffer.from(`${pdf}trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
}

for (const endpoint of ['documents', 'search']) {
  test(`${endpoint} session expiry returns to sign-in instead of an empty state`, async ({ page, context }) => {
    await page.route('**/api/documents?*', async route => {
      if (endpoint !== 'documents') return route.fulfill({ json: [] });
      await context.clearCookies();
      return route.fulfill({ status: 401, json: { detail: 'Expired' } });
    });
    if (endpoint === 'search') await page.route('**/api/search?*', async route => {
      await context.clearCookies();
      return route.fulfill({ status: 401, json: { detail: 'Expired' } });
    });
    await page.goto('/workspace');
    if (endpoint === 'search') {
      await expect(page.getByRole('button', { name: 'Tìm kiếm', exact: true })).toBeDisabled();
      await page.getByLabel('Tìm kiếm trong tài liệu', { exact: true }).fill('contract');
      await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
    }
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('button', { name: 'Đăng nhập', exact: true })).toBeVisible();
  });
}

test('real APIs find a document outside the visible list and open its page 6 with exact source highlighting', async ({ page }) => {
  test.setTimeout(90000);
  await page.request.post('/auth/login', { form: { username: 'workspace@example.com', password: user.password } });
  const clause = 'Workspace unique overdue penalty 0.05% per day. Value 1,200,000,000 VND.';
  let target;
  for (let index = 0; index < 12; index++) {
    const texts = index === 0 ? ['Introduction', 'Scope', 'Duration', 'Delivery', 'Appendix', clause] : ['Unrelated weather observations.'];
    const uploaded = await page.request.post('/api/upload', { multipart: {
      files: { name: `workspace-${index}.pdf`, mimeType: 'application/pdf', buffer: pdfFixture(texts) },
    } });
    expect(uploaded.status()).toBe(202);
    const { jobId } = await uploaded.json();
    let job;
    await expect.poll(async () => {
      job = await (await page.request.get(`/jobs/${jobId}`)).json();
      return job.status;
    }).toBe('completed');
    if (index === 0) target = job.job_files[0].document_id;
  }
  await page.goto('/workspace');
  await expect(page.getByTestId('workspace-document-row')).toHaveCount(10);
  await expect(page.locator(`[data-testid="workspace-document-row"][data-document-id="${target}"]`)).toHaveCount(0);
  await page.getByLabel('Tìm kiếm trong tài liệu', { exact: true }).fill('workspace unique overdue penalty');
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect(page.locator('.search-hit-card')).toHaveCount(1);
  await expect(page.locator('.search-snippet')).toHaveText(clause);
  await page.getByRole('link', { name: 'workspace-0.pdf — page 6', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/documents/${target}\\?page=6&`));
  await expect(page.getByText('Trang 6/6', { exact: true })).toBeVisible();
  await expect(page.locator('.citation-highlight')).toHaveText(clause);
  await expect(page.getByTitle('Bản đọc PDF — Trang 6')).toHaveAttribute('src', /#page=6$/);
  await page.reload();
  await expect(page.getByText('Trang 6/6', { exact: true })).toBeVisible();
  await expect(page.locator('.citation-highlight')).toHaveText(clause);
});
