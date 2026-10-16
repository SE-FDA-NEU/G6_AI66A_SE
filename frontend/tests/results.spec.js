import { test, expect } from '@playwright/test';
import { user } from './helpers';

function job(status = 'processing', completed = 3) {
  return {
    id: 77, status, file_count: 5, completed_count: completed,
    job_files: Array.from({ length: 5 }, (_, i) => ({
      id: i + 1, document_id: i + 1, original_filename: `document-${i + 1}.pdf`,
      status: i < completed ? 'completed' : i === completed ? 'processing' : 'pending',
      attempt_count: i <= completed ? 1 : 0, timeout_seconds: 75, error_message: null,
    })),
  };
}

test.beforeEach(async ({ page }) => {
  const response = await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(response.status()).toBe(200);
  await page.clock.install();
});

test('polls at 3 seconds, updates 3/5 progress and stops on completion', async ({ page }) => {
  let requests = 0;
  await page.route('**/jobs/77', route => route.fulfill({ json: requests++ === 0 ? job() : job('completed', 5) }));
  await page.goto('/results/77');
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Processing');
  await expect(page.getByText('3/5 tệp đã xử lý thành công')).toBeVisible();
  const progress = page.getByRole('progressbar', { name: 'Tiến độ xử lý', exact: true });
  await expect(progress).toHaveJSProperty('value', 3);
  await expect(progress).toHaveJSProperty('max', 5);
  const files = page.getByRole('list', { name: 'Trạng thái từng tệp' }).getByRole('listitem');
  await expect(files).toHaveCount(5);
  await expect(files.nth(3)).toContainText('Processing');
  await expect(files.nth(4)).toContainText('Pending');
  await page.clock.fastForward(2000);
  expect(requests).toBe(1);
  await page.clock.fastForward(1000);
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Completed');
  await expect(progress).toHaveJSProperty('value', 5);
  await page.clock.runFor(15000);
  expect(requests).toBe(2);
});

for (const [status, label] of [['completed', 'Completed'], ['failed', 'Failed'], ['timed_out', 'Timed out']]) {
  test(`opening an already ${status} job fetches once and does not poll`, async ({ page }) => {
    let requests = 0;
    const snapshot = job(status, status === 'completed' ? 5 : 2);
    snapshot.job_files[4].status = status;
    snapshot.job_files[4].error_message = status === 'completed' ? null : 'Processing could not finish.';
    await page.route('**/jobs/77', route => { requests++; return route.fulfill({ json: snapshot }); });
    await page.goto('/results/77');
    await expect(page.getByLabel('Trạng thái job')).toHaveText(label);
    if (status !== 'completed') await expect(page.getByText('Processing could not finish.')).toBeVisible();
    await page.clock.runFor(15000);
    expect(requests).toBe(1);
  });
}

test('pending job starts polling and shows per-file timeout and retry details', async ({ page }) => {
  let requests = 0;
  const pending = job('pending', 0);
  pending.job_files.forEach(file => { file.status = 'pending'; });
  const retrying = job('processing', 0);
  retrying.job_files[0] = { ...retrying.job_files[0], status: 'timed_out', attempt_count: 2, error_message: 'Retrying after timeout.' };
  await page.route('**/jobs/77', route => route.fulfill({ json: requests++ === 0 ? pending : retrying }));
  await page.goto('/results/77');
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Pending');
  await page.clock.runFor(3000);
  const first = page.getByRole('list', { name: 'Trạng thái từng tệp' }).getByRole('listitem').first();
  await expect(first).toContainText('Timed out');
  await expect(first).toContainText('Lần thử 2/3');
  await expect(first).toContainText('Retrying after timeout.');
  await page.clock.runFor(3000);
  await expect.poll(() => requests).toBe(3); // File timeout is not a terminal job.
});

test('temporary fetch failure preserves progress and polling recovers', async ({ page }) => {
  let requests = 0;
  await page.route('**/jobs/77', route => {
    requests++;
    if (requests === 2) return route.abort('failed');
    return route.fulfill({ json: requests >= 3 ? job('completed', 5) : job() });
  });
  await page.goto('/results/77');
  await expect(page.getByText('3/5 tệp đã xử lý thành công')).toBeVisible();
  await page.clock.runFor(3000);
  await expect(page.locator('.results-content').getByRole('alert')).toContainText('Không thể cập nhật');
  await expect(page.getByText('3/5 tệp đã xử lý thành công')).toBeVisible();
  await page.clock.runFor(3000);
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Completed');
  await expect(page.locator('.results-content').getByRole('alert')).toHaveCount(0);
});

for (const code of [403, 404]) {
  test(`${code} job shows a generic message and stops polling`, async ({ page }) => {
    let requests = 0;
    await page.route('**/jobs/77', route => { requests++; return route.fulfill({ status: code, json: {} }); });
    await page.goto('/results/77');
    await expect(page.locator('.results-content').getByRole('alert')).toContainText('Không tìm thấy tác vụ');
    await page.clock.runFor(15000);
    expect(requests).toBe(1);
  });
}

test('expired session during polling returns to sign-in', async ({ page, context }) => {
  await page.route('**/jobs/77', async route => {
    await context.clearCookies();
    await route.fulfill({ status: 401, json: {} });
  });
  await page.goto('/results/77');
  await expect(page).toHaveURL('/');
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
});

test('leaving results cancels polling', async ({ page }) => {
  let requests = 0;
  await page.route('**/jobs/77', route => { requests++; return route.fulfill({ json: job() }); });
  await page.goto('/results/77');
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Processing');
  await page.getByRole('link', { name: 'Về không gian tài liệu' }).click();
  await expect(page).toHaveURL('/workspace');
  await page.clock.runFor(15000);
  expect(requests).toBe(1);
});

test('results layout fits mobile with long filenames and errors', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const snapshot = job('failed', 3);
  snapshot.job_files[3].original_filename = `${'long-document-name-'.repeat(10)}.pdf`;
  snapshot.job_files[3].status = 'failed';
  snapshot.job_files[3].error_message = 'Processing timed out after 3 attempts (75 seconds per attempt).';
  await page.route('**/jobs/77', route => route.fulfill({ json: snapshot }));
  await page.goto('/results/77');
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Failed');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/results-mobile.png', fullPage: true });
});

for (const [status, label] of [['failed', 'Failed'], ['timed_out', 'Timed out']]) {
  test(`polling stops when a running job becomes ${status}`, async ({ page }) => {
    let requests = 0;
    await page.route('**/jobs/77', route => route.fulfill({ json: requests++ === 0 ? job() : job(status, 3) }));
    await page.goto('/results/77');
    await expect(page.getByLabel('Trạng thái job')).toHaveText('Processing');
    await page.clock.fastForward(3000);
    await expect(page.getByLabel('Trạng thái job')).toHaveText(label);
    await page.clock.fastForward(15000);
    expect(requests).toBe(2);
  });
}

test('slow requests do not create overlapping polling calls', async ({ page }) => {
  let requests = 0;
  let heldRoute;
  await page.route('**/jobs/77', route => { requests++; heldRoute = route; });
  await page.goto('/results/77');
  await expect.poll(() => requests).toBe(1);
  await page.clock.fastForward(9000);
  expect(requests).toBe(1);
  await heldRoute.fulfill({ json: job('completed', 5) });
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Completed');
});

test('loads completed job and filenames through the real backend proxy', async ({ page }) => {
  await page.goto('/results/9001');
  await expect(page.getByLabel('Trạng thái job')).toHaveText('Completed');
  await expect(page.getByText('1/1 tệp đã xử lý thành công')).toBeVisible();
  await expect(page.getByText('private-playwright_user.pdf', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/results-desktop.png', fullPage: true });
});
