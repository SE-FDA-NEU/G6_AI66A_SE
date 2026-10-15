import { test, expect } from '@playwright/test';
import { login } from './helpers';
import { MB, MAX_BATCH_BYTES, batchErrors, validateFile } from '../lib/upload-validation.js';

const file = (name, size = 32, mimeType = 'application/octet-stream') => ({
  name, mimeType, buffer: Buffer.alloc(size),
});

test('BR01 checks file size in bytes and permits case-insensitive allowed extensions', () => {
  for (const name of ['report.PDF', 'report.docx', 'report.PpTx']) {
    expect(validateFile({ name, size: 5 * MB }, [])).toEqual([]);
  }
  expect(validateFile({ name: 'report.pdf', size: 5 * MB + 1 }, [])).toContain('Tệp vượt quá 5 MB.');
  for (const name of ['report', 'report.pdf.exe', 'report.txt']) {
    expect(validateFile({ name, size: 10 }, [])).toContain('Chỉ chấp nhận PDF, DOCX hoặc PPTX.');
  }
});

test('BR01 independently checks the inclusive 50 MB batch boundary', () => {
  // A valid five-file batch cannot reach 50 MB; exercise this defensive rule directly.
  expect(batchErrors([{ size: MAX_BATCH_BYTES }])).toEqual([]);
  expect(batchErrors([{ size: MAX_BATCH_BYTES + 1 }])).toContain('Tổng dung lượng vượt quá 50 MB.');
  expect(validateFile({ name: 'next.pdf', size: 1 }, [{ size: MAX_BATCH_BYTES }]))
    .toContain('Tổng dung lượng vượt quá 50 MB.');
});

test.describe('upload page', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await expect(page).toHaveURL('/workspace');
    await page.getByRole('link', { name: 'Tải tài liệu', exact: true }).click();
    await expect(page).toHaveURL('/upload');
    await expect(page.getByLabel('Chọn tệp tài liệu')).toBeEnabled();
  });

  test('accepts PDF, DOCX and PPTX even with missing MIME types', async ({ page }) => {
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles([
      file('report.PDF'), file('notes.docx'), file('slides.pptx'),
    ]);
    await expect(page.getByRole('status')).toContainText('3/5 tệp hợp lệ');
    await expect(page.getByRole('listitem')).toHaveCount(3);
    await expect(page.getByText('Hợp lệ', { exact: true })).toHaveCount(3);
    await expect(page.getByRole('list', { name: 'Tệp đã chọn' }).getByRole('alert')).toHaveCount(0);
  });

  test('accepts five files at exactly 5 MB and rejects a sixth without clearing them', async ({ page }) => {
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles(
      Array.from({ length: 5 }, (_, i) => file(`contract-${i}.pdf`, 5 * MB)),
    );
    await expect(page.getByRole('status')).toContainText('5/5 tệp hợp lệ · 25.00 MB');
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles(file('sixth.pdf'));
    await expect(page.getByRole('listitem')).toHaveCount(6);
    await expect(page.getByRole('listitem').filter({ hasText: 'sixth.pdf' }))
      .toContainText('Tối đa 5 tệp mỗi lần.');
    await expect(page.getByText('Hợp lệ', { exact: true })).toHaveCount(5);
    await expect(page.getByRole('status')).toContainText('5/5 tệp hợp lệ · 25.00 MB');
    await page.getByRole('button', { name: 'Xóa sixth.pdf', exact: true }).click();
    await expect(page.getByRole('listitem')).toHaveCount(5);
  });

  test('shows per-file size and format errors, keeps valid selections and sends no upload', async ({ page }) => {
    const uploads = [];
    page.on('request', request => {
      if (request.method() === 'POST') uploads.push(request.url());
    });
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles(file('keep.pdf'));
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles([
      file('malware.exe', 32, 'application/pdf'),
      file('oversize.pdf', Math.ceil(5.1 * MB), 'application/pdf'),
      file('valid.docx'),
    ]);
    await expect(page.getByRole('listitem').filter({ hasText: 'malware.exe' }))
      .toContainText('Chỉ chấp nhận PDF, DOCX hoặc PPTX.');
    await expect(page.getByRole('listitem').filter({ hasText: 'oversize.pdf' }))
      .toContainText('Tệp vượt quá 5 MB.');
    await expect(page.getByRole('listitem').filter({ hasText: 'keep.pdf' })).toContainText('Hợp lệ');
    await expect(page.getByRole('status')).toContainText('2/5 tệp hợp lệ');
    await expect(page.getByRole('status')).toContainText('2 tệp cần kiểm tra');
    expect(uploads).toEqual([]);
  });

  test('revalidates rejected files when a slot is freed without displacing accepted files', async ({ page }) => {
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles([
      file('a.pdf'), file('b.pdf'), file('c.pdf'), file('d.pdf'), file('e.pdf'), file('f.pdf'),
    ]);
    await expect(page.getByRole('list', { name: 'Tệp đã chọn' }).getByRole('alert')).toContainText('Tối đa 5 tệp mỗi lần.');
    await page.getByRole('button', { name: 'Xóa a.pdf', exact: true }).click();
    await expect(page.getByRole('list', { name: 'Tệp đã chọn' }).getByRole('alert')).toHaveCount(0);
    await expect(page.getByRole('listitem').filter({ hasText: 'f.pdf' })).toContainText('Hợp lệ');
    await expect(page.getByText('Hợp lệ', { exact: true })).toHaveCount(5);
  });

  test('drag and drop validates files and supports selecting the same file after removal', async ({ page }) => {
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles(file('keep.pdf'));
    const transfer = await page.evaluateHandle(() => {
      const data = new DataTransfer();
      data.items.add(new File(['test'], 'bad.exe'));
      data.items.add(new File(['test'], 'slides.pptx'));
      return data;
    });
    await page.locator('.upload-picker').dispatchEvent('drop', { dataTransfer: transfer });
    await transfer.dispose();
    await expect(page.getByRole('status')).toContainText('2/5 tệp hợp lệ');
    await expect(page.getByRole('list', { name: 'Tệp đã chọn' }).getByRole('alert')).toContainText('Chỉ chấp nhận PDF, DOCX hoặc PPTX.');
    await page.getByRole('button', { name: 'Xóa keep.pdf', exact: true }).click();
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles(file('keep.pdf'));
    await expect(page.getByRole('listitem').filter({ hasText: 'keep.pdf' })).toHaveCount(1);
    await expect(page.getByRole('status')).toContainText('2/5 tệp hợp lệ');
  });

  test('mobile layout accommodates long filenames and keeps removal accessible', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    const name = `${'long-filename-'.repeat(12)}.pdf`;
    await page.getByLabel('Chọn tệp tài liệu').setInputFiles(file(name));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('button', { name: `Xóa ${name}`, exact: true }).click();
    await expect(page.getByRole('status')).toContainText('0/5 tệp hợp lệ');
  });
});
