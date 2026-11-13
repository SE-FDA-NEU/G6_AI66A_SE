import { test, expect } from '@playwright/test';
import { user, searchHit } from './helpers';

for (const width of [1280, 375]) {
  test(`workspace exposes content search and source links at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.request.post('/auth/login', { form: { username: user.email, password: user.password } });
    const documents = Array.from({ length: 21 }, (_, index) => ({
      id: index + 1, original_filename: `document-${index + 1}.pdf`, ai_label: 'Research', folder_id: null,
    }));
    await page.route('**/api/documents?*', route => route.fulfill({ json: documents }));
    await page.route('**/api/search?*', route => {
      const params = new URL(route.request().url()).searchParams;
      expect(params.get('q')).toBe('Orchid liquidity covenant');
      expect(params.get('mode')).toBe('content');
      return route.fulfill({ json: { query: params.get('q'), total_hits: 1, hits: [searchHit({
        document_id: 21, doc_name: 'document-21.pdf', page: 6,
        snippet: 'Orchid liquidity covenant requires a quarterly cash reserve review.',
        highlight_url: '/documents/21?page=6&start=0&end=67',
      })] } });
    });
    await page.goto('/workspace');
    await expect(page.getByLabel('Tìm kiếm trong tài liệu', { exact: true })).toHaveCount(0);
    const toggle = page.getByRole('button', { name: 'Tìm kiếm tài liệu', exact: true });
    await toggle.click({ timeout: 5000 });
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const search = page.getByRole('region', { name: 'Tìm kiếm tài liệu', exact: true });
    await search.getByLabel('Tìm kiếm trong tài liệu', { exact: true }).fill('Orchid liquidity covenant');
    await search.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
    await expect(search).toContainText('Orchid liquidity covenant requires a quarterly cash reserve review.');
    const citation = search.getByRole('link', { name: 'document-21.pdf — trang 6', exact: true });
    await expect(citation).toHaveAttribute('href', /\/documents\/21\?.*page=6/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await toggle.click();
    await expect(search).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Chọn tệp tài liệu', exact: true })).toBeEnabled();
  });
}
