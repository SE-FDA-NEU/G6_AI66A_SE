import { test, expect } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { user } from './helpers';

const exportUser = { email: 'export@example.com', password: user.password };
let saved;

test.beforeEach(async ({ page }) => {
  const login = await page.request.post('/auth/login', { form: { username: exportUser.email, password: exportUser.password } });
  expect(login.status()).toBe(200);
  const response = await page.request.get('/jobs/9002');
  expect(response.status()).toBe(200);
  saved = await response.json();
});

function readPdf(file) {
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const localPython = path.join(root, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const result = spawnSync(process.env.E2E_PYTHON || (existsSync(localPython) ? localPython : 'python'), ['-c',
    'import json,sys,pdfplumber; p=pdfplumber.open(sys.argv[1]); print(json.dumps([t for page in p.pages for t in page.extract_tables()], ensure_ascii=False)); p.close()', file],
  { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  expect(result.status, result.stderr).toBe(0);
  return JSON.parse(result.stdout).flatMap(table => table.slice(1));
}

test('real authenticated PDF download matches all five displayed saved rows, units and field sources after reload', async ({ page }) => {
  await page.goto('/results/9002');
  await page.reload();
  const button = page.getByRole('button', { name: 'Xuất bảng', exact: true });
  await expect(button).toBeEnabled();
  const downloadEvent = page.waitForEvent('download');
  await button.click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe('comparison-9002.pdf');
  expect(await download.failure()).toBeNull();
  const pdfRows = readPdf(await download.path());
  expect(pdfRows).toHaveLength(5);
  const rows = page.locator('.financial-comparison-table tbody tr');
  await expect(rows).toHaveCount(5);
  for (const [index, file] of saved.job_files.entries()) {
    const output = saved.result_data.documents[file.document_id].output;
    const pdfRow = pdfRows[index].map(cell => cell.replace(/\s+/g, ' ').trim());
    await expect(rows.nth(index).getByRole('rowheader')).toContainText(file.original_filename);
    expect(pdfRow[0]).toBe(file.original_filename);
    for (const [column, field] of ['value', 'payment_term', 'penalty'].entries()) {
      const claim = output[field];
      const cell = rows.nth(index).locator(`.table-field-${field}`);
      expect(pdfRow[column + 1]).toContain(claim.text || 'Không có thông tin');
      if (claim.text) await expect(cell.locator('.claim-text')).toHaveText(claim.text);
      if (claim.unverified) {
        await expect(cell).toContainText('Chưa xác thực');
        expect(pdfRow[column + 1]).toContain('Chưa xác thực');
      }
      const links = rows.nth(index).locator(`.table-source-${field}`).getByRole('link');
      await expect(links).toHaveCount(claim.evidence.length);
      for (const [sourceIndex, source] of claim.evidence.entries()) {
        await expect(links.nth(sourceIndex)).toHaveAttribute('href', new RegExp(`page=${source.page}&`));
        expect(pdfRow[4]).toContain(`${file.original_filename} — trang ${source.page}`);
      }
      if (!claim.evidence.length) expect(pdfRow[4]).toContain('Chưa có nguồn xác thực');
    }
  }
  await expect(page.getByRole('status').filter({ hasText: 'Đã gửi PDF để tải xuống.' })).toBeVisible();
  await expect(button).toBeEnabled();
});

const incompleteCases = {
  pending: job => { job.status = 'pending'; },
  processing: job => { job.status = 'processing'; },
  failed: job => { job.status = 'failed'; },
  timeout: job => { job.status = 'timed_out'; },
  count: job => { job.completed_count = 4; },
  file: job => { job.job_files[0].status = 'processing'; },
  row: job => { delete job.result_data.documents[job.job_files[0].document_id]; },
  field: job => { delete job.result_data.documents[job.job_files[0].document_id].output.value; },
  analysis: job => { job.result_data.documents[job.job_files[0].document_id].analysis_status = 'not_configured'; },
};
for (const [name, modify] of Object.entries(incompleteCases)) {
  test(`export stays disabled for incomplete ${name}`, async ({ page }) => {
    modify(saved);
    let requests = 0;
    await page.route('**/jobs/9002', route => route.fulfill({ json: saved }));
    await page.route('**/jobs/9002/export.pdf', route => { requests++; return route.abort(); });
    await page.goto('/results/9002');
    const button = page.getByRole('button', { name: 'Xuất bảng', exact: true });
    await expect(button).toBeDisabled();
    await button.dispatchEvent('click');
    expect(requests).toBe(0);
    await expect(page.getByText('Chỉ xuất PDF khi tác vụ hoàn tất và có đủ tất cả dòng trong bảng.')).toBeVisible();
  });
}

test('existing polling enables export only after all saved rows finish', async ({ page }) => {
  await page.clock.install();
  const complete = structuredClone(saved);
  saved.status = 'processing'; saved.completed_count = 4;
  saved.job_files[0].status = 'processing';
  delete saved.result_data.documents[saved.job_files[0].document_id];
  let finished = false;
  await page.route('**/jobs/9002', route => route.fulfill({ json: finished ? complete : saved }));
  await page.goto('/results/9002');
  const button = page.getByRole('button', { name: 'Xuất bảng', exact: true });
  await expect(button).toBeDisabled();
  finished = true;
  await page.clock.fastForward(3100);
  await expect(button).toBeEnabled();
});

test('pending download disables repeated clicks and reports status without hiding the table', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  let requests = 0;
  await page.route('**/jobs/9002/export.pdf', async route => { requests++; await gate; await route.continue(); });
  await page.goto('/results/9002');
  const button = page.getByRole('button', { name: 'Xuất bảng', exact: true });
  await button.click();
  await expect(button).toBeDisabled();
  await expect(button).toHaveAttribute('aria-busy', 'true');
  await expect(page.getByText('Đang tạo và tải PDF…')).toBeVisible();
  await button.dispatchEvent('click');
  await expect(page.locator('.financial-comparison-table tbody tr')).toHaveCount(5);
  const download = page.waitForEvent('download');
  release();
  await download;
  expect(requests).toBe(1);
  await expect(button).toBeEnabled();
});

for (const failure of ['network', '401', '404', '409', '500', 'html', 'invalid-pdf']) {
  test(`export ${failure} failure shows an error and allows a real retry`, async ({ page }) => {
    let fail = true;
    await page.route('**/jobs/9002/export.pdf', route => {
      if (!fail) return route.continue();
      if (failure === 'network') return route.abort();
      if (failure === 'html') return route.fulfill({ contentType: 'text/html', body: '<html>Sign in</html>' });
      if (failure === 'invalid-pdf') return route.fulfill({ contentType: 'application/pdf', body: 'not a PDF' });
      return route.fulfill({ status: Number(failure), json: { detail: 'Do not show server internals' } });
    });
    await page.goto('/results/9002');
    const button = page.getByRole('button', { name: 'Xuất bảng', exact: true });
    const error = page.getByRole('region', { name: 'Xuất bảng so sánh', exact: true }).getByRole('alert');
    await button.click();
    await expect(error).toBeVisible();
    await expect(error).not.toContainText('server internals');
    await expect(button).toBeEnabled();
    await expect(page.locator('.financial-comparison-table tbody tr')).toHaveCount(5);
    fail = false;
    const download = page.waitForEvent('download');
    await button.click();
    await download;
    await expect(error).toHaveCount(0);
  });
}

test('real server rejects incomplete and foreign exports even when the button is bypassed', async ({ page }) => {
  expect((await page.request.get('/jobs/9003/export.pdf')).status()).toBe(409);
  const login = await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(login.status()).toBe(200);
  expect((await page.request.get('/jobs/9002/export.pdf')).status()).toBe(404);
});

test('bullet results do not offer table export', async ({ page }) => {
  saved.mode = 'bullet';
  await page.route('**/jobs/9002', route => route.fulfill({ json: saved }));
  await page.goto('/results/9002');
  await expect(page.getByRole('heading', { name: 'Trạng thái xử lý' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Xuất bảng', exact: true })).toHaveCount(0);
});
