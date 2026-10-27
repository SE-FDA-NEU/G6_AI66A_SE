import { test, expect } from '@playwright/test';
import { login, user, searchHit } from './helpers';
import { openWorkspaceControls } from './helpers';

const longName = `${'long-contract-name-'.repeat(10)}.pdf`;

function resultJob(mode = 'bullet') {
  const documents = {};
  const files = Array.from({ length: 5 }, (_, index) => {
    const id = 51 + index;
    const name = `${index}-${longName}`;
    const claim = (text, page) => ({ text, unverified: false, evidence: [{
      document_id: id, page, start: 0, end: text.length, quote: text, reader_version: 'a'.repeat(64),
    }] });
    documents[id] = { schema_version: 1, document_id: id, original_filename: name, mode,
      analysis_status: 'completed', warnings: [], reader: { page_count: 15, page_kind: 'page' },
      label: { ai_label: 'Báo cáo hợp đồng', ai_confidence: .9, confidence_level: 'high' },
      output: mode === 'table' ? { type: mode, value: claim('1,200,000,000 VND', 1),
        payment_term: claim('Within 30 days', 2), penalty: claim('0.05% per day', 3) }
        : { type: mode, bullets: [claim(`Revenue is 1,200,000,000 VND. ${'long-source-text-'.repeat(20)}`, 1)],
          actions: [claim('Review the budget within 30 days.', 2), claim('Compare 2 supplier quotations.', 3)], limitation: null },
    };
    return { id: index + 1, document_id: id, original_filename: name, status: 'completed',
      attempt_count: 1, timeout_seconds: 75 };
  });
  return { id: 129, mode, status: 'completed', completed_count: 5, file_count: 5,
    job_files: files, result_data: { schema_version: 1, documents } };
}

async function expectNoOverflow(page) {
  const layout = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const outside = [...document.querySelectorAll('main input, main select, main button, main .citation-badge, main .analysis-card, main .upload-file, main .job-file')]
      .filter(element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && getComputedStyle(element).visibility !== 'hidden' &&
          (rect.left < -1 || rect.right > width + 1);
      }).map(element => `${element.tagName}.${element.className}`);
    return { overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > width, outside };
  });
  expect(layout).toEqual({ overflow: false, outside: [] });
}

test('US05 login leads through workspace, upload retry and completed bullet results without overflow', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Tiếp tục công việc của bạn' })).toBeVisible();
  await expectNoOverflow(page);
  await page.route('**/api/documents*', route => new URL(route.request().url()).pathname === '/api/documents'
    ? route.fulfill({ json: [{ id: 51, original_filename: longName, ai_label: 'long-label-'.repeat(15),
      ai_confidence: .9, review_state: 'needs_review', folder_id: 1 }] }) : route.continue());
  await page.route('**/api/folders?*', route => route.fulfill({ json: [
    { id: 1, name: 'Economics 101' }, { id: 2, name: 'Research-'.repeat(20) },
  ] }));
  await page.route('**/api/search?*', route => route.fulfill({ json: { query: 'contract', total_hits: 1,
    hits: [searchHit({ doc_name: longName, snippet: 'long-source-text-'.repeat(30), ai_label: 'long-label-'.repeat(15) })] } }));
  await login(page);
  await expect(page).toHaveURL('/workspace');
  await openWorkspaceControls(page);
  await expectNoOverflow(page);
  const workspaceLabelEditor = page.getByTestId('workspace-document-row').getByTestId('document-label-editor');
  await workspaceLabelEditor.getByRole('button', { name: 'Chỉnh sửa nhãn', exact: true }).tap();
  await workspaceLabelEditor.getByLabel('Nhãn người dùng', { exact: true }).fill('long-user-label-'.repeat(6));
  await expectNoOverflow(page);
  await workspaceLabelEditor.getByRole('button', { name: 'Hủy chỉnh sửa', exact: true }).tap();
  const toggle = page.getByRole('button', { name: 'Mở menu điều hướng', exact: true });
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('button', { name: 'Đăng xuất', exact: true })).toBeHidden();
  await toggle.tap();
  await expect(page.getByRole('button', { name: 'Đăng xuất', exact: true })).toBeVisible();
  await expectNoOverflow(page);
  await page.locator('#new-document-heading').tap();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await toggle.tap();
  await page.keyboard.press('Escape');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(toggle).toBeFocused();
  await expect(page.locator('.workspace-search')).toHaveCount(0);
  await page.goto('/upload');
  await expect(page).toHaveURL('/upload');
  const picker = page.getByLabel('Chọn tệp tài liệu');
  await expect(picker).toBeEnabled();
  await picker.setInputFiles(Array.from({ length: 5 }, (_, index) => ({
    name: `${index}-${longName}`, mimeType: 'application/pdf', buffer: Buffer.from('layout fixture'),
  })));
  const selector = page.getByLabel('Kiểu phân tích');
  for (const mode of ['table', 'concept', 'bullet']) {
    await selector.selectOption(mode);
    await expect(selector).toHaveValue(mode);
    await expectNoOverflow(page);
  }
  expect((await selector.boundingBox()).height).toBeGreaterThanOrEqual(44);
  const saved = resultJob();
  await page.route('**/jobs/129', route => route.fulfill({ json: saved }));
  let release;
  let uploads = 0;
  await page.route('**/api/upload', async route => {
    if (++uploads === 1) {
      await new Promise(resolve => { release = resolve; });
      return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    }
    return route.fulfill({ status: 202, json: { jobId: 129 } });
  });
  await page.getByRole('button', { name: 'Tải lên và phân tích', exact: true }).tap();
  await expect.poll(() => uploads).toBe(1);
  try {
    await expect(selector).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Đang gửi…', exact: true })).toBeDisabled();
    await expectNoOverflow(page);
  } finally { release(); }
  await expect(page.locator('.upload-page').getByRole('alert')).toContainText('Không thể gửi tài liệu');
  await expect(page.locator('.upload-files').getByRole('listitem')).toHaveCount(5);
  await expect(selector).toHaveValue('bullet');
  await expectNoOverflow(page);
  await page.getByRole('button', { name: 'Tải lên và phân tích', exact: true }).tap();
  await expect(page).toHaveURL('/results/129');
  await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText('Hoàn tất');
  await expect(page.getByRole('region', { name: 'Hành động đề xuất', exact: true })).toHaveCount(5);
  await expectNoOverflow(page);
  const citation = page.locator('.citation-badge').first();
  expect((await citation.boundingBox()).height).toBeGreaterThanOrEqual(44);
  await page.reload();
  await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText('Hoàn tất');
  await expectNoOverflow(page);
  await page.screenshot({ path: `test-results/${testInfo.project.name}-bullet-375.png`, fullPage: true });
});

test('five comparison cards and source-reader controls fit 375px and menu expands only on small screens', async ({ page }, testInfo) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  const saved = resultJob('table');
  await page.route('**/jobs/129', route => route.fulfill({ json: saved }));
  await page.goto('/results/129');
  const cards = page.getByRole('table', { name: 'So sánh điều khoản tài chính' }).locator('tbody tr');
  await expect(cards).toHaveCount(5);
  await expect(cards.first().locator('.table-field-value .claim-text')).toHaveText('1,200,000,000 VND');
  await expect(cards.first().locator('.table-field-penalty .claim-text')).toHaveText('0.05% per day');
  await expectNoOverflow(page);
  await page.getByRole('button', { name: 'Mở menu điều hướng', exact: true }).tap();
  await expect(page.getByRole('link', { name: 'Về không gian tài liệu', exact: true })).toBeVisible();
  await expectNoOverflow(page);
  await page.keyboard.press('Escape');
  await page.setViewportSize({ width: 1100, height: 900 });
  await expect(page.getByRole('button', { name: 'Mở menu điều hướng', exact: true })).toBeHidden();
  await expect(page.getByRole('link', { name: 'Về không gian tài liệu', exact: true })).toBeVisible();
  await page.setViewportSize(testInfo.project.use.viewport);
  await expect(page.getByRole('link', { name: 'Về không gian tài liệu', exact: true })).toBeHidden();
  const version = 'a'.repeat(64);
  await page.route('**/api/documents/51/pages', route => route.fulfill({ json: {
    page_count: 15, page_kind: 'page', reader_version: version, ai_label: 'long-label-'.repeat(15),
    reader_url: `/documents/51/reader.pdf?version=${version}`,
    pages: Array.from({ length: 15 }, (_, index) => ({ page: index + 1, text: '0.05% per day', positions: [] })),
  } }));
  await page.route('**/api/documents/51/reader.pdf?*', route => route.fulfill({
    contentType: 'application/pdf', body: Buffer.from('%PDF-1.4\n%EOF\n'),
  }));
  await cards.first().getByRole('group', { name: 'Nguồn: Phạt', exact: true }).getByRole('link').tap();
  await expect(page.getByText('Trang 3/15', { exact: true })).toBeVisible();
  await expectNoOverflow(page);
  await page.getByRole('combobox', { name: 'Chọn trang nguồn' }).selectOption('4');
  await expect(page.getByText('Trang 4/15', { exact: true })).toBeVisible();
  await expectNoOverflow(page);
  await page.getByRole('link', { name: /^Về kết quả/ }).tap();
  await expect(cards).toHaveCount(5);
  await expectNoOverflow(page);
  await page.screenshot({ path: `test-results/${testInfo.project.name}-comparison-375.png`, fullPage: true });
});

test('Xuất bảng pending, error and real PDF download work at 375px without overflow', async ({ page }) => {
  const login = await page.request.post('/auth/login', { form: { username: 'export@example.com', password: user.password } });
  expect(login.status()).toBe(200);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  let attempts = 0;
  await page.route('**/jobs/9002/export.pdf', async route => {
    if (++attempts > 1) return route.continue();
    await gate;
    return route.fulfill({ status: 500, json: { detail: 'Unavailable' } });
  });
  await page.goto('/results/9002');
  const button = page.getByRole('button', { name: 'Xuất bảng', exact: true });
  await expect(button).toBeEnabled();
  expect((await button.boundingBox()).height).toBeGreaterThanOrEqual(44);
  await button.tap();
  try {
    await expect(button).toBeDisabled();
    await expect(page.getByText('Đang tạo và tải PDF…')).toBeVisible();
    await expectNoOverflow(page);
  } finally { release(); }
  const error = page.getByRole('region', { name: 'Xuất bảng so sánh', exact: true }).getByRole('alert');
  await expect(error).toContainText('Không thể xuất PDF');
  await expectNoOverflow(page);
  const downloading = page.waitForEvent('download');
  await button.tap();
  const downloaded = await downloading;
  expect(downloaded.suggestedFilename()).toBe('comparison-9002.pdf');
  expect(await downloaded.failure()).toBeNull();
  await expect(error).toHaveCount(0);
  await expect(button).toBeEnabled();
  await expectNoOverflow(page);
});

test('seven-day expiry warnings and expired reader messages fit 375px', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.clock.install({ time: new Date('2026-03-24T12:00:00Z') });
  await page.route('**/api/documents?*', route => route.fulfill({ json: [{
    id: 61, original_filename: longName, ai_label: 'Contract', ai_confidence: .9, folder_id: null,
    last_accessed_at: '2026-03-01T00:00:00', expires_at: '2026-03-31T00:00:00',
  }] }));
  await page.goto('/workspace');
  await openWorkspaceControls(page);
  await expect(page.getByTestId('expiry-warning')).toBeVisible();
  await expect(page.getByTestId('document-expiry')).toContainText('31/03/2026');
  await expectNoOverflow(page);
  await page.route('**/api/documents/61/pages', route => route.fulfill({ status: 410,
    json: { detail: { code: 'source_expired', message: 'Source expired.' } } }));
  await page.getByRole('link', { name: longName, exact: true }).tap();
  await expect(page.locator('main').getByRole('alert')).toContainText('Nguồn đã hết hạn');
  await expect(page.locator('iframe')).toHaveCount(0);
  await expectNoOverflow(page);
});

test('progress, timeout errors, limitations and Chưa xác thực citations wrap at 375px', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  const saved = resultJob();
  saved.status = 'failed';
  saved.completed_count = 4;
  saved.job_files[4].status = 'failed';
  saved.job_files[4].error_message = `Processing exceeded the 180-second target. ${'long-error-detail-'.repeat(20)}`;
  delete saved.result_data.documents[55];
  const first = saved.result_data.documents[51];
  first.output.actions = [];
  first.output.limitation = `Nguồn không hỗ trợ hai đề xuất. ${'long-source-limitation-'.repeat(20)}`;
  first.output.bullets[0].unverified = true;
  await page.route('**/jobs/129', route => route.fulfill({ json: saved }));
  await page.goto('/results/129');
  await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText('Thất bại');
  await expect(page.getByText('4/5 tệp đã xử lý thành công')).toBeVisible();
  await expect(page.getByTestId('action-limitation')).toHaveText(first.output.limitation);
  await expect(page.getByText('Chưa xác thực · Cần kiểm tra', { exact: true })).toBeVisible();
  await expectNoOverflow(page);
});
