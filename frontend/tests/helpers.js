export const user = { email: 'playwright@example.com', password: 'LocalIssueTest2026!' };
export function searchHit(overrides = {}) {
  const snippet = 'Doanh thu tài chính: 1,200,000,000 VND.';
  return { document_id: 61, doc_name: 'bao_cao_tai_chinh.pdf', page: 1,
    start: 0, end: snippet.length, snippet, reader_version: 'a'.repeat(64), score: 2,
    highlight_url: `/documents/61?page=1&start=0&end=${snippet.length}`,
    ai_label: 'Báo cáo', folder_id: null, ...overrides };
}
export async function login(page, credentials = user) {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill(credentials.email);
  await page.getByLabel('Mật khẩu', { exact: true }).fill(credentials.password);
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
}
