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
    await expect(table.getByRole('columnheader')).toHaveText(['Tài liệu', 'Giá trị', 'Thanh toán', 'Phạt']);
    await expect(table.locator('tbody tr')).toHaveCount(5);
    for (const [index, file] of saved.job_files.entries()) {
      const row = table.locator('tbody tr').nth(index);
      const output = saved.result_data.documents[file.document_id].output;
      await expect(row.getByRole('rowheader')).toContainText(file.original_filename);
      await expect(row.getByRole('rowheader')).toContainText('Nhãn AI: Hợp đồng · 90%');
      for (const [field, pageNumber] of [['value', 1], ['payment_term', 2], ['penalty', 3]]) {
        const cell = row.locator(`.table-field-${field}`);
        await expect(cell.locator('.claim-text')).toHaveText(output[field].text);
        await expect(cell.getByRole('link')).toHaveAttribute('href',
          `/documents/${file.document_id}?page=${pageNumber}&start=0&end=${output[field].text.length}&evidence=${file.document_id}-${pageNumber}-0-${output[field].text.length}&job=125`);
        await expect(cell.getByRole('link')).toHaveAttribute('title', output[field].text);
      }
    }
    await expect(table.getByText('Unverified · Cần kiểm tra', { exact: true })).toHaveCount(0);
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
    await expect(cell).toHaveText('Không có thông tin · Unverified');
    await expect(cell.getByRole('link')).toHaveCount(0);
  }
  const unsupported = rows.nth(2).locator('.table-field-value');
  await expect(unsupported.locator('.claim-text')).toHaveText('1,200,000,000 USD');
  await expect(unsupported).toContainText('Unverified · Cần kiểm tra');
  await expect(unsupported).toContainText('Nguồn không hỗ trợ nội dung này.');
  await expect(unsupported.getByRole('link')).toHaveCount(0);
  // A valid passage remains available for review even when it does not substantiate the claim.
  await expect(rows.nth(3).locator('.table-field-penalty')).toContainText('Unverified · Cần kiểm tra');
  await expect(rows.nth(3).locator('.table-field-penalty').getByRole('link')).toHaveCount(1);
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
    await expect(page.getByLabel('Trạng thái job')).toHaveText({ completed: 'Completed', failed: 'Failed', timed_out: 'Timed out' }[terminal]);
    await expect(table.locator('tbody tr')).toHaveCount(5);
    await expect(table.locator('.table-field-value .claim-text')).toHaveCount(terminal === 'completed' ? 5 : 3);
    if (terminal !== 'completed') {
      await expect(table.getByText(terminal === 'failed' ? 'Phân tích thất bại · Unverified' : 'Đã hết thời gian xử lý · Unverified', { exact: true })).toHaveCount(2);
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

test('mobile comparison scrolls locally, keeps duplicate filenames distinct and displays AI text safely', async ({ page }) => {
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
  expect(await region.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
  await region.focus();
  await expect(region).toBeFocused();
});
