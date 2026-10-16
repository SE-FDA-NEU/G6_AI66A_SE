import { test, expect } from '@playwright/test';
import { user } from './helpers';

test.beforeEach(async ({ page }) => {
  const login = await page.request.post('/auth/login', {
    form: { username: user.email, password: user.password },
  });
  expect(login.status()).toBe(200);
  await page.clock.install();
});

test('file timeout and retry exhaustion never show false completion', async ({ page }) => {
  let polls = 0;
  await page.route('**/jobs/77', route => {
    const step = Math.min(polls++, 2);
    const fileStatus = ['processing', 'timed_out', 'failed'][step];
    return route.fulfill({ json: {
      id: 77, status: step === 2 ? 'failed' : 'processing',
      file_count: 1, completed_count: 0, result_data: null,
      job_files: [{ id: 1, document_id: 1, original_filename: 'slow.pdf',
        status: fileStatus, attempt_count: step === 2 ? 3 : 1,
        timeout_seconds: 75,
        error_message: step === 0 ? null : step === 1
          ? 'Processing exceeded 75 seconds (attempt 1/3).'
          : 'Processing timed out after 3 attempts (75 seconds per attempt).',
      }],
    } });
  });

  await page.goto('/results/77');
  const badge = page.getByLabel('Trạng thái job');
  const row = page.getByRole('list', { name: 'Trạng thái từng tệp' }).getByRole('listitem');
  const progress = page.getByRole('progressbar', { name: 'Tiến độ xử lý', exact: true });
  await expect(badge).toHaveText('Processing');
  await page.clock.fastForward(3000);
  await expect(row).toContainText('Timed out');
  await expect(row).toContainText('Processing exceeded 75 seconds');
  await expect(badge).toHaveText('Processing');
  await expect(progress).toHaveJSProperty('value', 0);
  await expect(page.getByText('0/1 tệp đã xử lý thành công')).toBeVisible();
  await expect(page.getByText('Completed', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Tất cả tài liệu đã được xử lý xong.')).toHaveCount(0);

  await page.clock.fastForward(3000);
  await expect(badge).toHaveText('Failed');
  await expect(row).toContainText('Lần thử 3/3');
  await expect(row).toContainText('Processing timed out after 3 attempts');
  await expect(progress).toHaveJSProperty('value', 0);
  await expect(page.getByText('Completed', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Tất cả tài liệu đã được xử lý xong.')).toHaveCount(0);
  await page.clock.fastForward(15000);
  expect(polls).toBe(3);
});

test('revisit and reload a completed job URL preserve its real server status and files', async ({ page }) => {
  // This fixture is persisted in the isolated backend DB, not a browser route mock.
  const url = '/results/9001';
  const initialResponse = await page.request.get('/jobs/9001');
  expect(initialResponse.status()).toBe(200);
  const saved = await initialResponse.json();
  expect(saved.status).toBe('completed');
  let polls = 0;
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/jobs/9001') polls++;
  });
  async function expectPersistedResults() {
    await expect(page).toHaveURL(url);
    await expect(page.getByLabel('Trạng thái job')).toHaveText('Completed');
    await expect(page.getByText(`${saved.completed_count}/${saved.file_count} tệp đã xử lý thành công`)).toBeVisible();
    const rows = page.getByRole('list', { name: 'Trạng thái từng tệp' }).getByRole('listitem');
    await expect(rows).toHaveCount(saved.job_files.length);
    for (const file of saved.job_files) {
      const row = rows.filter({ hasText: file.original_filename });
      await expect(row).toContainText('Completed');
      await expect(row).toContainText(`Lần thử ${file.attempt_count}/3`);
    }
    const previous = polls;
    await page.clock.fastForward(15000);
    expect(polls).toBe(previous); // Terminal jobs never restart polling.
  }
  await page.goto(url);
  await expectPersistedResults();
  await page.getByRole('link', { name: 'Về không gian tài liệu' }).click();
  await expect(page).toHaveURL('/workspace');
  await page.goto(url);
  await expectPersistedResults();
  await page.reload();
  await expectPersistedResults();
  expect(polls).toBe(3); // One initial fetch for each visit/reload.
  const revisited = await page.request.get('/jobs/9001');
  expect(revisited.status()).toBe(200);
  expect(await revisited.json()).toEqual(saved);
});
