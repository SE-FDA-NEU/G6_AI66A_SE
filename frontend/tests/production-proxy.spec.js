import { test, expect } from '@playwright/test';
import { createHash } from 'node:crypto';
import { user } from './helpers';

test('all API rewrites reach the authenticated backend on the frontend origin', async ({ request }) => {
  for (const path of ['/auth/me', '/jobs', '/api/folders', '/api/documents', '/api/search?q=private']) {
    expect((await request.get(path)).status(), path).toBe(401);
  }
  expect((await request.post('/api/upload')).status()).toBe(401);
  const login = await request.post('/auth/login', { form: { username: user.email, password: user.password } });
  expect(login.status()).toBe(200);
  for (const path of ['/auth/me', '/jobs', '/api/folders', '/api/documents', '/api/search?q=private&mode=content']) {
    const response = await request.get(path);
    expect(response.status(), path).toBe(200);
    expect(response.headers()['content-type'], path).toContain('application/json');
  }
  const documents = await (await request.get('/api/documents')).json();
  expect((await request.get(`/api/documents/${documents[0].id}`)).status()).toBe(200);
  expect((await request.post('/auth/logout')).status()).toBe(204);
  expect((await request.get('/auth/me')).status()).toBe(401);
});

test('trusted HTTPS forwarding preserves Secure HttpOnly cookie and SSR authentication', async ({ playwright, baseURL }) => {
  const request = await playwright.request.newContext({ baseURL });
  try {
    // Simulate headers supplied by the TLS edge. This tests transport through
    // Next rewrites, not the public host's header sanitization policy.
    const response = await request.post('/auth/login', {
      headers: { 'X-Forwarded-Proto': 'https' },
      form: { username: user.email, password: user.password },
    });
    expect(response.status()).toBe(200);
    const cookie = response.headers()['set-cookie'];
    expect(cookie).toMatch(/; Secure/i);
    expect(cookie).toMatch(/; HttpOnly/i);
    expect(cookie).toMatch(/; SameSite=Lax/i);
    expect(cookie).not.toMatch(/; Domain=/i);
    // Browser won't send a Secure cookie on this HTTP fixture, so explicitly
    // forward it to verify the SSR -> /auth/me hop using the same session.
    const headers = { Cookie: cookie.split(';')[0] };
    const page = await request.get('/workspace', { headers, maxRedirects: 0 });
    expect(page.status()).toBe(200);
    expect(await page.text()).toContain(user.email);
    expect((await request.get('/auth/me', { headers })).status()).toBe(200);
    const logout = await request.post('/auth/logout', { headers });
    expect(logout.status()).toBe(204);
    expect(logout.headers()['set-cookie']).toMatch(/Max-Age=0/i);
  } finally {
    await request.dispose();
  }
});

test('five 5 MiB files survive upload and download rewrites without corruption', async ({ request }) => {
  test.setTimeout(60000);
  expect((await request.post('/auth/login', { form: { username: user.email, password: user.password } })).status()).toBe(200);
  const size = 5 * 1024 * 1024;
  const form = new FormData();
  form.append('mode', 'bullet');
  // A readable one-page PDF with a large comment inside its content stream.
  // No provider is configured: this checks transport, not generated AI output.
  const stream = `%${' '.repeat(size - 2048)}\nBT /F1 12 Tf 72 720 Td (Production upload) Tj ET\n`;
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
    `<< /Length ${stream.length} >>\nstream\n${stream}endstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ];
  let pdf = '%PDF-1.4\n';
  const offsets = [];
  for (const [index, object] of objects.entries()) {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  }
  const xref = pdf.length;
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n`;
  const bytes = Buffer.alloc(size, 32);
  bytes.write(pdf);
  bytes.write('\n%%EOF\n', size - 7);
  for (let i = 0; i < 5; i++) form.append('files', new Blob([bytes], { type: 'application/pdf' }), `production-batch-${i}.pdf`);
  const response = await request.post('/api/upload', { multipart: form });
  expect(response.status(), await response.text()).toBe(202);
  const { jobId } = await response.json();
  expect((await request.get(`/jobs/${jobId}`)).status()).toBe(200);
  const documents = await (await request.get('/api/documents')).json();
  const digest = buffer => createHash('sha256').update(buffer).digest('hex');
  for (let i = 0; i < 5; i++) {
    const document = documents.find(doc => doc.original_filename === `production-batch-${i}.pdf`);
    expect(document?.file_size_bytes).toBe(size);
    const download = await request.get(`/api/documents/${document.id}/file`);
    expect(download.status()).toBe(200);
    expect(digest(await download.body())).toBe(digest(bytes));
  }
  const document = documents.find(doc => doc.original_filename === 'production-batch-0.pdf');
  const range = await request.get(`/api/documents/${document.id}/file`, { headers: { Range: 'bytes=0-15' } });
  expect(range.status()).toBe(206);
  expect(range.headers()['content-range']).toBe(`bytes 0-15/${size}`);
  expect(await range.body()).toEqual(bytes.subarray(0, 16));
});
