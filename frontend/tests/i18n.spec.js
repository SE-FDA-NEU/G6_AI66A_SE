import { test, expect } from '@playwright/test';
import { openWorkspaceControls, user } from './helpers';

const vietnamese = /[ăâđêôơưĂÂĐÊÔƠƯàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]/;

async function mockLibrary(page) {
  await page.route('**/api/documents?*', route => route.fulfill({ json: [] }));
  await page.route('**/api/folders?*', route => route.fulfill({ json: [{ id: 1, name: 'Research' }] }));
}

test('English applies to sign-in, persisted workspace, upload validation and analysis options; Vietnamese restores fully', async ({ page }) => {
  await mockLibrary(page);
  await page.goto('/');
  await page.locator('#app-language').selectOption('en');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  expect(await page.locator('main').innerText()).not.toMatch(vietnamese);
  await page.locator('#email').fill(user.email);
  await page.locator('#password').fill(user.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL('/workspace');
  await expect(page.getByRole('heading', { name: 'What would you like to explore?', exact: true })).toBeVisible();
  expect(await page.locator('main').innerText()).not.toMatch(vietnamese);
  await page.reload();
  await openWorkspaceControls(page);
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await page.goto('/upload');
  await expect(page.getByRole('heading', { name: 'Upload document', exact: true })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({ name: 'bad.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('bad') });
  await expect(page.getByRole('alert').filter({ hasText: 'PDF' })).toBeVisible();
  expect(await page.locator('main').innerText()).not.toMatch(vietnamese);
  await page.locator('#app-language').selectOption('vi');
  await expect(page.getByRole('heading', { name: 'Tải tài liệu', exact: true })).toBeVisible();
  await expect(page.getByTestId('analysis-mode-selector')).toContainText('Tóm tắt điểm chính');
  await expect(page.getByRole('alert').filter({ hasText: 'Chỉ chấp nhận PDF' })).toBeVisible();
  await page.reload();
  await openWorkspaceControls(page);
  await expect(page.locator('html')).toHaveAttribute('lang', 'vi');
});


test('saved summary and AI labels stay unchanged when the interface language changes', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  const version = 'a'.repeat(64);
  await page.route('**/api/documents/51/pages', route => route.fulfill({ json: {
    page_count: 1, page_kind: 'page', reader_version: version, reader_url: `/documents/51/reader.pdf?version=${version}`,
    pages: [{ page: 1, text: 'Revenue 100 VND.' }], review_state: 'confirmed', original_filename: 'Source.pdf',
  } }));
  await page.route('**/api/documents/51/reader.pdf?*', route => route.fulfill({ contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF' }));
  let summaryCalls = 0;
  let translationCalls = 0;
  await page.route('**/api/localization/**', route => { translationCalls++; return route.abort(); });
  await page.route('**/api/documents/51/summary*', route => {
    summaryCalls++;
    return route.fulfill({ json: { job_id: 12, mode: 'bullet', document: {
      schema_version: 1, language: 'vi', document_id: 51, analysis_status: 'completed', original_filename: 'Source.pdf',
      reader: { version, page_kind: 'page' }, output: { type: 'bullet',
        bullets: [{ text: 'Doanh thu là 100 VND.', unverified: false,
          evidence: [{ document_id: 51, page: 1, start: 0, end: 16, quote: 'Revenue 100 VND.', reader_version: version }] }],
        actions: [], limitation: 'Không đủ căn cứ đề xuất hành động.' }, warnings: [],
    } } });
  });
  await page.goto('/documents/51?page=1');
  await expect(page.getByText('Doanh thu là 100 VND.', { exact: true })).toBeVisible();
  await page.locator('#app-language').selectOption('en');
  await expect(page.getByRole('heading', { name: 'Saved Summary', exact: true })).toBeVisible();
  await expect(page.getByText('Doanh thu là 100 VND.', { exact: true })).toBeVisible();
  await expect(page.locator('.citation-badge')).toContainText('page 1');
  await page.locator('#app-language').selectOption('vi');
  await expect(page.locator('.citation-badge')).toContainText('trang 1');
  expect(summaryCalls).toBe(1);
  expect(translationCalls).toBe(0);
});

test('saved summary loading errors follow the interface language', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  const version = 'b'.repeat(64);
  await page.route('**/api/documents/51/pages', route => route.fulfill({ json: { page_count: 1, page_kind: 'page', reader_version: version,
    reader_url: `/documents/51/reader.pdf?version=${version}`, pages: [{ page: 1, text: 'Original.' }] } }));
  await page.route('**/api/documents/51/summary*', route => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }));
  await page.goto('/documents/51?page=1');
  await page.locator('#app-language').selectOption('en');
  await expect(page.locator('main').getByRole('alert')).toContainText('Unable to load the saved summary.');
  await expect(page.getByRole('button', { name: /Retry.*summary/i })).toBeVisible();
  expect(await page.locator('main').innerText()).not.toMatch(vietnamese);
});

test('AI labels are preserved without translation requests', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.route('**/api/folders?*', route => route.fulfill({ json: [] }));
  await page.route('**/api/documents?*', route => route.fulfill({ json: [1, 2].map(id => ({ id,
    original_filename: `Source-${id}.pdf`, ai_label: 'Education', ai_confidence: .9, review_state: 'needs_review', folder_id: null })) }));
  let calls = 0;
  await page.route('**/api/localization/**', route => { calls++; return route.abort(); });
  await page.goto('/workspace');
  await openWorkspaceControls(page);
  await expect(page.getByTestId('document-ai-label').first()).toContainText('Education');
  await page.locator('#app-language').selectOption('en');
  await expect(page.getByTestId('document-ai-label').first()).toContainText('Education');
  await page.locator('#app-language').selectOption('vi');
  await expect(page.getByTestId('document-ai-label').first()).toContainText('Education');
  expect(calls).toBe(0);
});

test('upload captures the selected language in the submitted job', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
  await page.goto('/upload');
  await page.locator('#app-language').selectOption('en');
  await page.locator('input[type="file"]').setInputFiles({ name: 'source.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n%%EOF') });
  let body;
  await page.route('**/api/upload', route => { body = route.request().postData(); return route.fulfill({ status: 503, json: { detail: 'Unavailable' } }); });
  await page.getByRole('button', { name: /Upload.*analy/i }).click();
  await expect.poll(() => body).toContain('name="language"\r\n\r\nen');
});
