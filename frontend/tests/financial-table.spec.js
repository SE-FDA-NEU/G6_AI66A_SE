import { test, expect } from '@playwright/test';
import { user } from './helpers';

const amounts = ['1,200,000,000 VND', '2,500,000,000 VND', '999,999.99 USD', '0.00 VND', '750,000,000 VND'];

function tableJob() {
  const documents = {};
  const files = amounts.map((amount, index) => {
    const id = 51 + index;
    const claim = (text, page) => ({
      text, unverified: false, evidence: [{
        document_id: id, page, start: 0, end: text.length, quote: text, reader_version: 'a'.repeat(64),
      }],
    });
    documents[id] = {
      schema_version: 1, document_id: id, original_filename: `contract-${index + 1}.pdf`, mode: 'table',
      analysis_status: 'completed', warnings: [],
      label: { ai_label: 'Hợp đồng', ai_confidence: 0.9, confidence_level: 'high' },
      reader: { page_count: 3, page_kind: 'page' },
      output: { type: 'table', value: claim(amount, 1), payment_term: claim('Within 30 days', 2),
        penalty: claim('0.05% per day', 3) },
    };
    return { id: index + 1, document_id: id, original_filename: documents[id].original_filename,
      status: 'completed', attempt_count: 1, timeout_seconds: 39, error_message: null };
  });
  return { id: 125, mode: 'table', status: 'completed', file_count: 5, completed_count: 5, job_files: files,
    result_data: { schema_version: 1, documents } };
}

test.beforeEach(async ({ page }) => {
  const response = await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(response.status()).toBe(200);
});

test('five saved contracts render as five comparison rows with exact numbers, units and field evidence after reload', async ({ page }) => {
  const saved = tableJob();
  // File order, rather than JSON object key order, defines the comparison order.
  saved.job_files.reverse();
  await page.route('**/jobs/125', route => route.fulfill({ json: saved }));
  const table = page.getByRole('table', { name: 'So sánh điều khoản tài chính' });
  async function checkRows() {
    await expect(table.getByRole('columnheader')).toHaveText(['Tài liệu', 'Giá trị', 'Thanh toán', 'Phạt', 'Nguồn']);
    await expect(table.locator('tbody tr')).toHaveCount(5);
    for (const [index, file] of saved.job_files.entries()) {
      const row = table.locator('tbody tr').nth(index);
      const output = saved.result_data.documents[file.document_id].output;
      await expect(row.getByRole('rowheader')).toContainText(file.original_filename);
      await expect(row.getByTestId('document-ai-label')).toHaveAttribute('data-original-label', 'Hợp đồng');
      await expect(row.getByTestId('document-ai-confidence')).toContainText('90%');
      for (const [field, pageNumber] of [['value', 1], ['payment_term', 2], ['penalty', 3]]) {
        const cell = row.locator(`.table-field-${field}`);
        await expect(cell.locator('.claim-text')).toHaveText(output[field].text);
        const sources = row.getByRole('group', { name: `Nguồn: ${{ value: 'Giá trị', payment_term: 'Thanh toán', penalty: 'Phạt' }[field]}`, exact: true });
        await expect(sources.getByRole('link')).toHaveAttribute('href',
          `/documents/${file.document_id}?page=${pageNumber}&start=0&end=${output[field].text.length}&evidence=${file.document_id}-${pageNumber}-0-${output[field].text.length}&job=125`);
        await expect(sources.getByRole('link')).toHaveAttribute('title', output[field].text);
      }
    }
    await expect(table.getByText('Chưa xác thực · Cần kiểm tra', { exact: true })).toHaveCount(0);
  }
  await page.goto('/results/125');
  await checkRows();
  await page.reload();
  await checkRows();
  await page.goto('/workspace');
  await page.goto('/results/125');
  await checkRows();
});

test('missing and unsupported fields are explicit without replacing numeric text or borrowing another contract evidence', async ({ page }) => {
  const saved = tableJob();
  saved.result_data.documents[51].output.payment_term = { text: null, evidence: [], unverified: true };
  delete saved.result_data.documents[52].output.penalty;
  saved.result_data.documents[53].output.value = { text: '1,200,000,000 USD', evidence: [], unverified: true,
    verification_issues: ['unsupported_fact', 'missing_evidence'] };
  saved.result_data.documents[54].output.penalty.unverified = true;
  saved.result_data.documents[54].output.penalty.verification_issues = ['unsupported_fact'];
  await page.route('**/jobs/125', route => route.fulfill({ json: saved }));
  await page.goto('/results/125');
  const table = page.getByRole('table', { name: 'So sánh điều khoản tài chính' });
  const rows = table.locator('tbody tr');
  for (const [index, field] of [[0, 'payment_term'], [1, 'penalty']]) {
    const cell = rows.nth(index).locator(`.table-field-${field}`);
    await expect(cell.locator('.analysis-claim')).toHaveText('Không có thông tin · Chưa xác thực');
    await expect(rows.nth(index).locator(`.table-source-${field}`).getByRole('link')).toHaveCount(0);
    await expect(rows.nth(index).locator(`.table-source-${field}`)).toContainText('Chưa có nguồn xác thực');
  }
  const unsupported = rows.nth(2).locator('.table-field-value');
  await expect(unsupported.locator('.claim-text')).toHaveText('1,200,000,000 USD');
  await expect(unsupported).toContainText('Chưa xác thực · Cần kiểm tra');
  await expect(unsupported).toContainText('Nguồn không hỗ trợ nội dung này.');
  await expect(rows.nth(2).locator('.table-source-value').getByRole('link')).toHaveCount(0);
  // A valid passage remains available for review even when it does not substantiate the claim.
  await expect(rows.nth(3).locator('.table-field-penalty')).toContainText('Chưa xác thực · Cần kiểm tra');
  await expect(rows.nth(3).locator('.table-source-penalty').getByRole('link')).toHaveCount(1);
  await expect(rows.nth(4).locator('.table-field-value .claim-text')).toHaveText(amounts[4]);
});

for (const terminal of ['completed', 'failed', 'timed_out']) {
  test(`US07 polling retains all five contract rows and ends with ${terminal} inside the five-minute budget`, async ({ page }) => {
    await page.clock.install();
    const running = tableJob();
    running.status = 'processing';
    running.completed_count = 3;
    for (const file of running.job_files.slice(3)) {
      file.status = 'processing';
      delete running.result_data.documents[file.document_id];
    }
    let polls = 0;
    let finish = false;
    const done = tableJob();
    done.status = terminal;
    if (terminal !== 'completed') {
      done.completed_count = 3;
      for (const file of done.job_files.slice(3)) {
        file.status = terminal;
        file.attempt_count = 3;
        file.error_message = 'Processing timed out after 3 attempts (39 seconds per attempt).';
        delete done.result_data.documents[file.document_id];
      }
    }
    await page.route('**/jobs/125', route => { polls++; return route.fulfill({ json: finish ? done : running }); });
    await page.goto('/results/125');
    const table = page.getByRole('table', { name: 'So sánh điều khoản tài chính' });
    await expect(table.locator('tbody tr')).toHaveCount(5);
    await expect(table.getByText('Đang phân tích', { exact: true })).toHaveCount(2);
    await expect(table.locator('.table-field-value .claim-text')).toHaveCount(3);
    await expect(page.getByText('3/5 tệp đã xử lý thành công')).toBeVisible();
    finish = true;
    await page.clock.fastForward(297000);
    await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText({ completed: 'Hoàn tất', failed: 'Thất bại', timed_out: 'Quá thời gian' }[terminal]);
    await expect(table.locator('tbody tr')).toHaveCount(5);
    await expect(table.locator('.table-field-value .claim-text')).toHaveCount(terminal === 'completed' ? 5 : 3);
    if (terminal !== 'completed') {
      await expect(table.getByText(terminal === 'failed' ? 'Phân tích thất bại · Chưa xác thực' : 'Đã hết thời gian xử lý · Chưa xác thực', { exact: true })).toHaveCount(2);
      await expect(page.getByText('Tất cả tài liệu đã được xử lý xong.')).toHaveCount(0);
    }
    const finalPolls = polls;
    await page.clock.fastForward(15000);
    expect(polls).toBe(finalPolls);
  });
}

test('table appears before results exist and keeps five pending rows', async ({ page }) => {
  const saved = tableJob();
  saved.status = 'pending';
  saved.completed_count = 0;
  saved.result_data = null;
  saved.job_files.forEach(file => { file.status = 'pending'; });
  await page.route('**/jobs/125', route => route.fulfill({ json: saved }));
  await page.goto('/results/125');
  const table = page.getByRole('table', { name: 'So sánh điều khoản tài chính' });
  await expect(table.locator('tbody tr')).toHaveCount(5);
  await expect(table.getByText('Đang chờ xử lý', { exact: true })).toHaveCount(5);
  await expect(table.locator('.claim-text')).toHaveCount(0);
});

test('mobile comparison renders five cards without horizontal scrolling, keeps duplicate filenames distinct and displays AI text safely', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const saved = tableJob();
  saved.job_files[0].original_filename = saved.job_files[1].original_filename = `${'long-contract-'.repeat(12)}.pdf`;
  saved.result_data.documents[51].output.value.text = '<script>window.unsafeAI = true</script>';
  await page.route('**/jobs/125', route => route.fulfill({ json: saved }));
  await page.goto('/results/125');
  const region = page.getByRole('region', { name: 'Bảng điều khoản hợp đồng' });
  await expect(region.locator('tbody tr')).toHaveCount(5);
  await expect(region.locator('tbody tr').nth(0).getByRole('rowheader').getByRole('link')).toHaveAttribute('href', '/documents/51?page=1');
  await expect(region.locator('tbody tr').nth(1).getByRole('rowheader').getByRole('link')).toHaveAttribute('href', '/documents/52?page=1');
  await expect(region.getByText('<script>window.unsafeAI = true</script>', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.unsafeAI)).toBeUndefined();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await region.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await region.locator('tbody tr').first().evaluate(element => getComputedStyle(element).display)).toBe('block');
  for (const label of ['Giá trị', 'Thanh toán', 'Phạt', 'Nguồn']) {
    await expect(region.locator('tbody tr').first().locator('.financial-field-label').filter({ hasText: new RegExp(`^${label}$`) })).toBeVisible();
  }
  await region.focus();
  await expect(region).toBeFocused();
});

for (const width of [375, 640]) {
  test(`mobile cards at ${width}px preserve numeric units, field sources and saved results across reload and resize`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    const saved = tableJob();
    await page.route('**/jobs/125', route => route.fulfill({ json: saved }));
    await page.goto('/results/125');
    const table = page.getByRole('table', { name: 'So sánh điều khoản tài chính' });
    const cards = table.locator('tbody tr');
    async function checkCards() {
      await expect(cards).toHaveCount(5);
      for (let index = 0; index < 5; index++) {
        const card = cards.nth(index);
        await expect(card.locator('.table-field-value .claim-text')).toHaveText(amounts[index]);
        await expect(card.locator('.table-field-penalty .claim-text')).toHaveText('0.05% per day');
        await expect(card.locator('.table-field-payment_term .claim-text')).toHaveText('Within 30 days');
        await expect(card.getByRole('link', { name: `contract-${index + 1}.pdf — trang 3`, exact: true }))
          .toHaveAttribute('href', `/documents/${51 + index}?page=3&start=0&end=13&evidence=${51 + index}-3-0-13&job=125`);
        expect(await card.evaluate(element => getComputedStyle(element).display)).toBe('block');
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
    await checkCards();
    await page.reload();
    await checkCards();
    await page.setViewportSize({ width: 1100, height: 900 });
    expect(await cards.first().evaluate(element => getComputedStyle(element).display)).toBe('table-row');
    await expect(table.getByRole('columnheader')).toHaveText(['Tài liệu', 'Giá trị', 'Thanh toán', 'Phạt', 'Nguồn']);
    await page.setViewportSize({ width, height: 812 });
    await checkCards();
    if (width === 375) await page.screenshot({ path: 'test-results/financial-cards-mobile.png', fullPage: true });
  });
}

for (const width of [375, 1100]) {
  test(`field citation at ${width}px opens its exact source page and returns to the saved comparison`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const saved = tableJob();
    const doc = saved.result_data.documents[53];
    const version = 'a'.repeat(64);
    await page.route('**/jobs/125', route => route.fulfill({ json: saved }));
    await page.route('**/api/documents/53/pages', route => route.fulfill({ json: {
      page_count: 3, page_kind: 'page', reader_version: version,
      reader_url: `/documents/53/reader.pdf?version=${version}`,
      pages: [doc.output.value.text, doc.output.payment_term.text, doc.output.penalty.text]
        .map((text, index) => ({ page: index + 1, text, positions: [] })),
    } }));
    await page.route('**/api/documents/53/reader.pdf?*', route => route.fulfill({
      contentType: 'application/pdf', body: Buffer.from('%PDF-1.4\n%EOF\n'),
    }));
    await page.goto('/results/125');
    const table = page.getByRole('table', { name: 'So sánh điều khoản tài chính' });
    const row = table.locator('tbody tr').nth(2);
    await row.getByRole('group', { name: 'Nguồn: Phạt', exact: true }).getByRole('link').click();
    await expect(page).toHaveURL('/documents/53?page=3&start=0&end=13&evidence=53-3-0-13&job=125');
    await expect(page.getByText('Trang 3/3', { exact: true })).toBeVisible();
    await expect(page.getByTitle('Bản đọc PDF — Trang 3')).toHaveAttribute('src', `/api/documents/53/reader.pdf?version=${version}&highlight_page=3&start=0&end=13#page=3`);
    await page.reload();
    await expect(page.getByText('Trang 3/3', { exact: true })).toBeVisible();
    await page.getByRole('link', { name: /^Về kết quả/ }).click();
    await expect(page).toHaveURL('/results/125');
    await expect(table.locator('tbody tr')).toHaveCount(5);
    await expect(row.locator('.table-field-value .claim-text')).toHaveText(amounts[2]);
    await expect(row.locator('.table-field-penalty .claim-text')).toHaveText('0.05% per day');
  });
}

test('mobile cards retain pending and failed contracts beside US07 progress and failure details', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const saved = tableJob();
  saved.status = 'failed';
  saved.completed_count = 3;
  saved.result_data.documents[51].output.payment_term = { text: null, evidence: [], unverified: true };
  saved.result_data.documents[52].output.penalty = { text: '0.5% per day', evidence: [], unverified: true,
    verification_issues: ['unsupported_fact'] };
  const failed = saved.job_files[3];
  failed.status = 'failed';
  failed.error_message = 'Processing timed out after 3 attempts.';
  delete saved.result_data.documents[failed.document_id];
  const pending = saved.job_files[4];
  pending.status = 'pending';
  delete saved.result_data.documents[pending.document_id];
  await page.route('**/jobs/125', route => route.fulfill({ json: saved }));
  await page.goto('/results/125');
  await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText('Thất bại');
  await expect(page.getByText('3/5 tệp đã xử lý thành công')).toBeVisible();
  await expect(page.getByText('Xử lý hết thời gian sau 3 lần thử.', { exact: true })).toBeVisible();
  const cards = page.getByRole('table', { name: 'So sánh điều khoản tài chính' }).locator('tbody tr');
  await expect(cards).toHaveCount(5);
  await expect(cards.nth(0).locator('.table-field-payment_term')).toContainText('Không có thông tin · Chưa xác thực');
  await expect(cards.nth(0).locator('.table-source-payment_term').getByRole('link')).toHaveCount(0);
  await expect(cards.nth(1).locator('.table-field-penalty .claim-text')).toHaveText('0.5% per day');
  await expect(cards.nth(1).locator('.table-field-penalty')).toContainText('Chưa xác thực · Cần kiểm tra');
  await expect(cards.nth(1).locator('.table-source-penalty').getByRole('link')).toHaveCount(0);
  await expect(cards.nth(3)).toContainText('Phân tích thất bại · Chưa xác thực');
  await expect(cards.nth(4)).toContainText('Đang chờ xử lý');
  await expect(cards.nth(3).locator('.citation-badge')).toHaveCount(0);
  await expect(cards.nth(4).locator('.citation-badge')).toHaveCount(0);
});
