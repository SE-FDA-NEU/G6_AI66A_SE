import { test, expect } from '@playwright/test';
import { user } from './helpers';

function savedJob(actionCount = 2) {
  const claim = (text, page) => ({ text, unverified: false, evidence: [{
    document_id: 31, page, start: 0, end: text.length, quote: text, reader_version: 'a'.repeat(64),
  }] });
  const document = {
    schema_version: 1, document_id: 31, original_filename: 'market-report.pdf', mode: 'bullet',
    analysis_status: 'completed', reader: { page_count: 15, page_kind: 'page' },
    label: { ai_label: 'Báo cáo thị trường', ai_confidence: .9, confidence_level: 'high' },
    warnings: actionCount < 2 ? ['insufficient_actions'] : [],
    output: { type: 'bullet', bullets: [claim('Revenue is 1,200,000,000 VND.', 2)],
      actions: [claim('Review the budget within 30 days.', 5), claim('Compare 2 supplier quotations before renewal.', 9)].slice(0, actionCount),
      limitation: actionCount < 2 ? 'Nguồn chỉ hỗ trợ một phần đề xuất, không đủ căn cứ cho hai hành động.' : null },
  };
  return { id: 128, mode: 'bullet', status: 'completed', file_count: 1, completed_count: 1,
    job_files: [{ id: 1, document_id: 31, original_filename: document.original_filename,
      status: 'completed', attempt_count: 1, timeout_seconds: 75 }],
    result_data: { schema_version: 1, documents: { 31: document } } };
}

test.beforeEach(async ({ page }) => {
  const response = await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(response.status()).toBe(200);
});

test('saved bullet summary and two recommendations retain their own citations on refresh and revisit without resubmission', async ({ page }) => {
  await page.clock.install();
  const saved = savedJob();
  const requests = [];
  let polls = 0;
  page.on('request', request => { if (request.method() === 'POST') requests.push(request.url()); });
  await page.route('**/jobs/128', route => { polls++; return route.fulfill({ json: saved }); });
  const bullets = page.getByRole('region', { name: 'Tóm tắt điểm chính', exact: true });
  const actions = page.getByRole('region', { name: 'Hành động đề xuất', exact: true });
  async function checkSavedOutput() {
    await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText('Hoàn tất');
    await expect(bullets.getByRole('listitem')).toHaveCount(1);
    await expect(bullets.locator('.claim-text')).toHaveText('Revenue is 1,200,000,000 VND.');
    await expect(bullets.getByRole('link')).toHaveAttribute('href', '/documents/31?page=2&start=0&end=29&evidence=31-2-0-29&job=128');
    await expect(actions.getByRole('heading', { name: 'Hành động đề xuất', exact: true })).toBeVisible();
    await expect(actions.getByRole('listitem')).toHaveCount(2);
    await expect(actions.locator('.claim-text')).toHaveText(saved.result_data.documents[31].output.actions.map(action => action.text));
    for (const [index, action] of saved.result_data.documents[31].output.actions.entries()) {
      const evidence = action.evidence[0];
      await expect(actions.getByRole('listitem').nth(index).getByRole('link')).toHaveAttribute('href',
        `/documents/31?page=${evidence.page}&start=0&end=${action.text.length}&evidence=31-${evidence.page}-0-${action.text.length}&job=128`);
    }
    await expect(actions.getByTestId('action-limitation')).toHaveCount(0);
    await expect(actions.getByText('Chưa xác thực · Cần kiểm tra', { exact: true })).toHaveCount(0);
  }
  await page.goto('/results/128');
  await checkSavedOutput();
  await page.clock.fastForward(15000);
  expect(polls).toBe(1);
  await page.reload();
  await checkSavedOutput();
  await page.goto('/workspace');
  await page.goto('/results/128');
  await checkSavedOutput();
  expect(polls).toBe(3);
  expect(requests).toEqual([]);
});

for (const count of [0, 1]) {
  test(`${count} supported action displays the exact persisted source limitation in Hành động đề xuất after refresh`, async ({ page }) => {
    const saved = savedJob(count);
    const limitation = saved.result_data.documents[31].output.limitation;
    await page.route('**/jobs/128', route => route.fulfill({ json: saved }));
    await page.goto('/results/128');
    const actions = page.getByRole('region', { name: 'Hành động đề xuất', exact: true });
    async function checkLimitation() {
      await expect(actions).toBeVisible();
      await expect(actions.getByRole('listitem')).toHaveCount(count);
      await expect(actions.getByTestId('action-limitation')).toHaveText(limitation);
      await expect(page.getByText(limitation, { exact: true })).toHaveCount(1);
      await expect(page.getByText('insufficient_actions', { exact: true })).toHaveCount(0);
      await expect(actions.getByRole('link')).toHaveCount(count);
      await expect(page.getByRole('region', { name: 'Tóm tắt điểm chính' })).toBeVisible();
    }
    await checkLimitation();
    await page.reload();
    await checkLimitation();
  });
}

test('legacy results without a limitation still explain missing recommendations', async ({ page }) => {
  const saved = savedJob(0);
  delete saved.result_data.documents[31].output.limitation;
  await page.route('**/jobs/128', route => route.fulfill({ json: saved }));
  await page.goto('/results/128');
  await expect(page.getByRole('region', { name: 'Hành động đề xuất' }).getByTestId('action-limitation'))
    .toHaveText('Tài liệu không đủ căn cứ nguồn để hỗ trợ hai hành động đề xuất.');
  await expect(page.getByText('Tài liệu không đủ căn cứ nguồn để hỗ trợ hai hành động đề xuất.', { exact: true })).toHaveCount(1);
});

test('shared Chưa xác thực states keep review evidence and never invent citation links for unsupported saved claims', async ({ page }) => {
  const saved = savedJob(1);
  const output = saved.result_data.documents[31].output;
  output.bullets[0].unverified = true;
  output.actions[0] = { text: 'An unsupported recommendation', evidence: [], unverified: true };
  await page.route('**/jobs/128', route => route.fulfill({ json: saved }));
  await page.goto('/results/128');
  const bullets = page.getByRole('region', { name: 'Tóm tắt điểm chính' });
  const actions = page.getByRole('region', { name: 'Hành động đề xuất' });
  await expect(bullets.getByText('Chưa xác thực · Cần kiểm tra', { exact: true })).toBeVisible();
  await expect(bullets.getByRole('link')).toHaveCount(1);
  await expect(actions.getByText('Chưa xác thực · Cần kiểm tra', { exact: true })).toBeVisible();
  await expect(actions.getByRole('link')).toHaveCount(0);
  await expect(actions.getByTestId('action-limitation')).toHaveText(output.limitation);
});

for (const terminal of ['completed', 'failed', 'timed_out']) {
  test(`existing processing view transitions to ${terminal} without inventing bullet or action output`, async ({ page }) => {
    await page.clock.install();
    const ready = savedJob();
    const running = { ...ready, status: 'processing', completed_count: 0, result_data: null,
      job_files: [{ ...ready.job_files[0], status: 'processing' }] };
    const done = terminal === 'completed' ? ready : { ...running, status: terminal,
      job_files: [{ ...running.job_files[0], status: terminal, error_message: 'Bullet processing exceeded the 180-second target.' }] };
    let polls = 0;
    await page.route('**/jobs/128', route => route.fulfill({ json: polls++ === 0 ? running : done }));
    await page.goto('/results/128');
    const actions = page.getByRole('region', { name: 'Hành động đề xuất' });
    await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText('Đang xử lý');
    await expect(actions).toHaveCount(0);
    await expect(page.getByRole('region', { name: 'Tóm tắt điểm chính' })).toHaveCount(0);
    await page.clock.fastForward(3000);
    await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText({ completed: 'Hoàn tất', failed: 'Thất bại', timed_out: 'Quá thời gian' }[terminal]);
    if (terminal === 'completed') {
      await expect(actions.getByRole('listitem')).toHaveCount(2);
    } else {
      await expect(actions).toHaveCount(0);
      await expect(page.getByText('Tóm tắt vượt quá giới hạn 180 giây.', { exact: true })).toBeVisible();
    }
    const terminalPolls = polls;
    await page.clock.fastForward(15000);
    expect(polls).toBe(terminalPolls);
    await page.reload();
    await expect(page.getByLabel('Trạng thái tác vụ')).toHaveText({ completed: 'Hoàn tất', failed: 'Thất bại', timed_out: 'Quá thời gian' }[terminal]);
  });
}

for (const width of [375, 390]) {
  test(`saved summary, limitation and action text remain readable and safe at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    const saved = savedJob(1);
    const doc = saved.result_data.documents[31];
    doc.original_filename = `${'long-market-report-'.repeat(10)}.pdf`;
    doc.output.actions[0].text = '<script>window.unsafeAction = true</script>';
    doc.output.limitation = '<img src=x onerror="window.unsafeLimitation=true"> Source cannot support two actions.';
    await page.route('**/jobs/128', route => route.fulfill({ json: saved }));
    await page.goto('/results/128');
    const actions = page.getByRole('region', { name: 'Hành động đề xuất' });
    await expect(actions.locator('.claim-text')).toHaveText(doc.output.actions[0].text);
    await expect(actions.getByTestId('action-limitation')).toHaveText(doc.output.limitation);
    expect(await page.evaluate(() => window.unsafeAction || window.unsafeLimitation)).toBeUndefined();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(actions.getByRole('link')).toBeVisible();
  });
}

test('an action citation opens its saved source page and returns to the completed summary', async ({ page }) => {
  const saved = savedJob();
  const output = saved.result_data.documents[31].output;
  const version = 'a'.repeat(64);
  await page.route('**/jobs/128', route => route.fulfill({ json: saved }));
  await page.route('**/api/documents/31/pages', route => route.fulfill({ json: {
    page_count: 15, page_kind: 'page', reader_version: version,
    reader_url: `/documents/31/reader.pdf?version=${version}`,
    pages: Array.from({ length: 15 }, (_, index) => ({ page: index + 1,
      text: index === 8 ? output.actions[1].text : `Report page ${index + 1}`, positions: [] })),
  } }));
  await page.route('**/api/documents/31/reader.pdf?*', route => route.fulfill({
    contentType: 'application/pdf', body: Buffer.from('%PDF-1.4\n%EOF\n'),
  }));
  await page.goto('/results/128');
  const actions = page.getByRole('region', { name: 'Hành động đề xuất' });
  await actions.getByRole('link', { name: 'market-report.pdf — trang 9', exact: true }).click();
  await expect(page).toHaveURL(`/documents/31?page=9&start=0&end=${output.actions[1].text.length}&evidence=31-9-0-${output.actions[1].text.length}&job=128`);
  await expect(page.getByText('Trang 9/15', { exact: true })).toBeVisible();
  await expect(page.getByTitle('Bản đọc PDF — Trang 9')).toHaveAttribute('src', `/api/documents/31/reader.pdf?version=${version}&highlight_page=9&start=0&end=${output.actions[1].text.length}#page=9`);
  await page.getByRole('link', { name: /^Về kết quả/ }).click();
  await expect(page).toHaveURL('/results/128');
  await expect(actions.getByRole('listitem')).toHaveCount(2);
  await expect(page.getByRole('region', { name: 'Tóm tắt điểm chính' }).locator('.claim-text')).toHaveText(output.bullets[0].text);
});
