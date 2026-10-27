import { test, expect } from '@playwright/test';
import { openWorkspaceControls, user, searchHit } from './helpers';

const folders = [{ id: 1, name: 'Economics 101' }, { id: 2, name: 'Research' }];
const document = { id: 41, original_filename: 'economics-notes.pdf', folder_id: 1,
  ai_label: 'Economics', ai_confidence: .91, user_label: 'Semester 1', review_state: 'confirmed' };

test.beforeEach(async ({ page }) => {
  expect((await page.request.post('/auth/login', { form: { username: user.email, password: user.password } })).status()).toBe(200);
});

test('history requires a saved folder before offering a move destination', async ({ page }) => {
  let saved = { ...document, folder_id: null };
  const writes = [];
  await page.route('**/api/folders?*', route => route.fulfill({ json: [] }));
  await page.route('**/api/documents?*', route => route.fulfill({ json: [saved] }));
  await page.route('**/api/folders', route => {
    writes.push('create');
    expect(route.request().postDataJSON()).toEqual({ name: 'Research' });
    return route.fulfill({ status: 201, json: { id: 2, name: 'Research' } });
  });
  await page.route('**/api/documents/41/folder', route => {
    writes.push('move');
    expect(route.request().postDataJSON()).toEqual({ folder_id: 2 });
    saved = { ...saved, folder_id: 2 };
    return route.fulfill({ json: saved });
  });
  await page.goto('/workspace');
  const row = page.getByTestId('workspace-document-row');
  await row.locator('summary').click();
  await expect(row.getByLabel('Chuyển tài liệu tới', { exact: true })).toHaveCount(0);
  await row.getByRole('button', { name: 'Tạo thư mục', exact: true }).click();
  await expect(page.getByLabel('Tên thư mục mới')).toBeFocused();
  await page.getByLabel('Tên thư mục mới').fill('Research');
  await page.getByRole('region', { name: 'Tạo thư mục' }).getByRole('button', { name: 'Tạo thư mục', exact: true }).click();
  await row.getByLabel('Chuyển tài liệu tới', { exact: true }).selectOption('2');
  await row.getByRole('button', { name: 'Chuyển', exact: true }).click();
  await expect(row.getByTestId('document-folder-placement')).toContainText('Research');
  expect(writes).toEqual(['create', 'move']);
});

test('real APIs persist a move from Economics 101 to Research and unfile without changing labels', async ({ page }) => {
  await page.request.post('/auth/login', { form: { username: 'folder@example.com', password: user.password } });
  const before = (await (await page.request.get('/api/documents')).json())[0];
  await page.goto('/workspace');
  await openWorkspaceControls(page);
  for (const summary of await page.locator('.library-disclosure > summary').all()) await summary.click();
  const panel = page.getByRole('region', { name: 'Tạo thư mục' });
  for (const name of ['Economics 101', 'Research']) {
    await panel.getByLabel('Tên thư mục mới').fill(name);
    await panel.getByRole('button', { name: 'Tạo thư mục', exact: true }).click();
    await expect(panel.getByRole('status')).toContainText(`Đã tạo thư mục “${name}”`);
  }
  const savedFolders = await (await page.request.get('/api/folders')).json();
  const economics = savedFolders.find(folder => folder.name === 'Economics 101');
  const research = savedFolders.find(folder => folder.name === 'Research');
  const row = page.getByTestId('workspace-document-row');
  await row.getByLabel('Chuyển tài liệu tới', { exact: true }).selectOption(String(economics.id));
  await row.getByRole('button', { name: 'Chuyển', exact: true }).click();
  await expect(row.getByTestId('document-folder-placement')).toContainText('Economics 101');
  await page.getByRole('button', { name: 'Mở thư mục Economics 101', exact: true }).click();
  await openWorkspaceControls(page);
  await expect(row).toHaveCount(1);
  await row.getByLabel('Chuyển tài liệu tới', { exact: true }).selectOption(String(research.id));
  await row.getByRole('button', { name: 'Chuyển', exact: true }).click();
  await expect(page.locator(`section[data-folder-id="${new URL(page.url()).searchParams.get('folder')}"]`).getByText('Thư mục này chưa có tài liệu.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Mở thư mục Research', exact: true }).click();
  await openWorkspaceControls(page);
  await expect(row.getByTestId('document-folder-placement')).toContainText('Research');
  await page.reload();
  await openWorkspaceControls(page);
  await expect(row.getByTestId('document-folder-placement')).toContainText('Research');
  await expect(row.getByTestId('document-ai-label')).toHaveAttribute('data-original-label', 'Economics');
  await expect(row.getByTestId('document-ai-confidence')).toContainText('91%');
  await expect(row.getByTestId('document-user-label')).toContainText('Semester 1');
  await expect(row.getByTestId('document-review-state')).toContainText('Đã xác nhận');
  const moved = (await (await page.request.get('/api/documents')).json())[0];
  expect(moved).toEqual({ ...before, folder_id: research.id,
    last_accessed_at: moved.last_accessed_at, expires_at: moved.expires_at });
  expect(new Date(moved.expires_at + 'Z') - new Date(moved.last_accessed_at + 'Z')).toBe(30 * 86400000);
  expect(new Date(moved.last_accessed_at + 'Z').getTime()).toBeGreaterThanOrEqual(new Date(before.last_accessed_at + 'Z').getTime());
  await row.getByRole('button', { name: 'Bỏ thư mục', exact: true }).click();
  await expect(page.locator(`section[data-folder-id="${new URL(page.url()).searchParams.get('folder')}"]`).getByText('Thư mục này chưa có tài liệu.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Recents', exact: true }).click();
  await openWorkspaceControls(page);
  await expect(row.getByTestId('document-folder-placement')).toContainText('Chưa phân thư mục');
  await page.reload();
  await openWorkspaceControls(page);
  const unfiled = (await (await page.request.get('/api/documents')).json())[0];
  expect(unfiled).toEqual({ ...before, folder_id: null,
    last_accessed_at: unfiled.last_accessed_at, expires_at: unfiled.expires_at });
  expect(new Date(unfiled.expires_at + 'Z') - new Date(unfiled.last_accessed_at + 'Z')).toBe(30 * 86400000);
  expect(new Date(unfiled.last_accessed_at + 'Z').getTime()).toBeGreaterThanOrEqual(new Date(moved.last_accessed_at + 'Z').getTime());
  await expect(row.getByTestId('document-ai-confidence')).toContainText('91%');
});

test('create shows pending/error, preserves the name and selected folder, and adds the saved folder', async ({ page }) => {
  await page.route('**/api/folders?*', route => route.fulfill({ json: [folders[0]] }));
  await page.route('**/api/documents?*', route => route.fulfill({ json: [] }));
  let attempts = 0;
  let release;
  await page.route('**/api/folders', async route => {
    expect(route.request().method()).toBe('POST');
    expect(route.request().postDataJSON()).toEqual({ name: 'Research' });
    if (++attempts === 1) {
      await new Promise(resolve => { release = resolve; });
      return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    }
    return route.fulfill({ status: 201, json: folders[1] });
  });
  await page.goto('/workspace');
  await openWorkspaceControls(page);
  for (const summary of await page.locator('.library-disclosure > summary').all()) await summary.click();
  await page.getByRole('button', { name: 'Mở thư mục Economics 101', exact: true }).click();
  await openWorkspaceControls(page);
  const panel = page.getByRole('region', { name: 'Tạo thư mục' });
  const name = panel.getByLabel('Tên thư mục mới');
  await name.fill('   ');
  await expect(panel.getByRole('button', { name: 'Tạo thư mục', exact: true })).toBeDisabled();
  await name.fill(' Research ');
  await panel.getByRole('button', { name: 'Tạo thư mục', exact: true }).click();
  await expect.poll(() => typeof release).toBe('function');
  await expect(panel.getByRole('button', { name: 'Đang tạo…', exact: true })).toBeDisabled();
  await expect(name).toBeDisabled();
  release();
  await expect(panel.getByRole('alert')).toContainText('Không thể tạo thư mục');
  await expect(name).toHaveValue(' Research ');
  await panel.getByRole('button', { name: 'Tạo thư mục', exact: true }).click();
  await expect(name).toHaveValue('');
  await expect(page).toHaveURL('/workspace?folder=1');
  await expect(page.getByRole('button', { name: 'Mở thư mục Research', exact: true })).toBeVisible();
  expect(attempts).toBe(2);
});

test('move preserves metadata and destination through failure, then refreshes history without global content search', async ({ page }) => {
  let saved = { ...document };
  let searches = 0;
  let lists = 0;
  await page.route('**/api/folders?*', route => route.fulfill({ json: folders }));
  await page.route('**/api/documents?*', route => { lists++; return route.fulfill({ json: [saved] }); });
  await page.route('**/api/search?*', route => {
    searches++;
    return route.fulfill({ json: { query: 'payment', total_hits: saved.folder_id === 1 ? 1 : 0,
      hits: saved.folder_id === 1 ? [searchHit({ folder_id: 1 })] : [] } });
  });
  let moves = 0;
  let release;
  await page.route('**/api/documents/41/folder', async route => {
    expect(route.request().method()).toBe('PATCH');
    expect(route.request().postDataJSON()).toEqual({ folder_id: 2 });
    if (++moves === 1) return route.fulfill({ status: 403, json: { detail: 'Access denied' } });
    await new Promise(resolve => { release = resolve; });
    saved = { ...saved, folder_id: 2 };
    return route.fulfill({ json: saved });
  });
  await page.goto('/workspace');
  await openWorkspaceControls(page);
  for (const summary of await page.locator('.library-disclosure > summary').all()) await summary.click();
  const row = page.getByTestId('workspace-document-row');
  await row.getByLabel('Chuyển tài liệu tới', { exact: true }).selectOption('2');
  await row.getByRole('button', { name: 'Chuyển', exact: true }).click();
  await expect(row.getByRole('alert')).toContainText('Không thể chuyển tài liệu');
  await expect(row.getByLabel('Chuyển tài liệu tới', { exact: true })).toHaveValue('2');
  await expect(row.getByTestId('document-folder-placement')).toContainText('Economics 101');
  await row.getByRole('button', { name: 'Chuyển', exact: true }).click();
  await expect.poll(() => typeof release).toBe('function');
  await expect(row.getByRole('button', { name: 'Đang chuyển…', exact: true })).toBeDisabled();
  await expect(row.getByLabel('Chuyển tài liệu tới', { exact: true })).toBeDisabled();
  await expect(row.getByTestId('document-ai-label')).toHaveAttribute('data-original-label', 'Economics');
  await expect(row.getByTestId('document-ai-confidence')).toContainText('91%');
  release();
  await expect(row.getByTestId('document-folder-placement')).toContainText('Research');
  await expect(row.getByTestId('document-user-label')).toContainText('Semester 1');
  expect(searches).toBe(0);
  expect(lists).toBe(2);
  expect(moves).toBe(2);
});

test('folder listing retries without hiding documents, then shows its empty state', async ({ page }) => {
  let attempts = 0;
  let release;
  await page.route('**/api/folders?*', async route => {
    if (++attempts === 1) {
      await new Promise(resolve => { release = resolve; });
      return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    }
    return route.fulfill({ json: [] });
  });
  await page.route('**/api/documents?*', route => route.fulfill({ json: [document] }));
  await page.goto('/workspace');
  await openWorkspaceControls(page);
  for (const summary of await page.locator('.library-disclosure > summary').all()) await summary.click();
  const panel = page.getByRole('region', { name: 'Lịch sử tài liệu' });
  await expect(panel.getByText('Đang tải thư mục…')).toBeVisible();
  await expect(page.getByTestId('workspace-document-row')).toBeVisible();
  await expect.poll(() => typeof release).toBe('function');
  release();
  await expect(panel.getByRole('alert')).toContainText('Không thể tải thư mục');
  await panel.getByRole('button', { name: 'Thử lại thư mục', exact: true }).click();
  await expect(panel.getByText('Chưa có thư mục.', { exact: false })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Recents', exact: true })).toBeVisible();
});

test('folder selectors load every API page instead of truncating at one hundred folders', async ({ page }) => {
  const all = Array.from({ length: 101 }, (_, index) => ({ id: index + 1, name: `Folder ${index + 1}` }));
  await page.route('**/api/folders?*', route => {
    const skip = Number(new URL(route.request().url()).searchParams.get('skip'));
    return route.fulfill({ json: all.slice(skip, skip + 100) });
  });
  await page.route('**/api/documents?*', route => route.fulfill({ json: [] }));
  await page.goto('/workspace');
  await openWorkspaceControls(page);
  for (const summary of await page.locator('.library-disclosure > summary').all()) await summary.click();
  await expect(page.getByRole('button', { name: /^Mở thư mục Folder / })).toHaveCount(101);
  await page.getByRole('button', { name: 'Mở thư mục Folder 101', exact: true }).click();
  await openWorkspaceControls(page);
  await expect(page.locator(`section[data-folder-id="${new URL(page.url()).searchParams.get('folder')}"]`).getByText('Thư mục này chưa có tài liệu.', { exact: true })).toBeVisible();
});
