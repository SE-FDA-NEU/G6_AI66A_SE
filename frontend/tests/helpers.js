export const user = { email: 'playwright@example.com', password: 'LocalIssueTest2026!' };
export async function login(page, credentials = user) {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill(credentials.email);
  await page.getByLabel('Mật khẩu', { exact: true }).fill(credentials.password);
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
}
