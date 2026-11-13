// Public smoke test for #254: browser-equivalent HTTP through the Next.js proxy.
import { createHash, randomBytes } from 'node:crypto';

const BASE = process.argv[2] || 'https://documind-web-k6i1.onrender.com';
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const sha = b => createHash('sha256').update(b).digest('hex');

async function session(label) {
  let cookie = '';
  const tag = `p254_${label}_${Date.now().toString(36)}${randomBytes(2).toString('hex')}`;
  const password = randomBytes(12).toString('base64url');
  const call = async (path, opts = {}) => {
    const headers = { ...(opts.headers || {}), ...(cookie ? { cookie } : {}) };
    const t0 = Date.now();
    const res = await fetch(BASE + path, { ...opts, headers, redirect: 'manual' });
    const sc = res.headers.getSetCookie?.() || [];
    for (const c of sc) if (c.startsWith('documind_session=')) cookie = c.split(';')[0];
    res.ms = Date.now() - t0;
    res.setCookies = sc;
    return res;
  };
  const r = await call('/auth/register', { method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: tag, email: `${tag}@example.com`, password }) });
  log(`[${label}] register ${r.status} (${r.ms} ms) user=${tag}`);
  log(`[${label}] Set-Cookie: ${r.setCookies.map(c => c.replace(/=([^;]{8})[^;]*/, '=$1…')).join(' | ')}`);
  return { call, tag };
}

function makePdf(size, marker) {
  const stream = `%${' '.repeat(size - 2048)}\nBT /F1 12 Tf 72 720 Td (${marker}) Tj ET\n`;
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
    `<< /Length ${stream.length} >>\nstream\n${stream}endstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ];
  let pdf = '%PDF-1.4\n';
  const offsets = [];
  for (const [i, o] of objects.entries()) { offsets.push(pdf.length); pdf += `${i + 1} 0 obj\n${o}\nendobj\n`; }
  const xref = pdf.length;
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.map(o => `${String(o).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n`;
  const bytes = Buffer.alloc(size, 32);
  bytes.write(pdf);
  bytes.write('\n%%EOF\n', size - 7);
  return bytes;
}

const health = await fetch('https://documind-n9ny.onrender.com/health').then(r => r.text());
log('backend health', health);
const home = await fetch(BASE + '/'); log('frontend / ', home.status);

const A = await session('a');
const me = await A.call('/auth/me'); log('[a] /auth/me', me.status, await me.text());

const size = 5 * 1024 * 1024 - 4096; // "near 5 MiB", stays under the limit
const files = Array.from({ length: 5 }, (_, i) => makePdf(size, `Proxy check ${i}`));
const form = new FormData();
form.append('mode', 'bullet');
form.append('language', 'vi');
files.forEach((b, i) => form.append('files', new Blob([b], { type: 'application/pdf' }), `p254-batch-${i}.pdf`));
log(`upload 5 x ${size} B = ${(5 * size / 1048576).toFixed(2)} MiB`);
const up = await A.call('/api/upload', { method: 'POST', body: form });
const upText = await up.text();
log('upload', up.status, `${up.ms} ms`, upText.slice(0, 200));
if (up.status !== 202) process.exit(1);
const { jobId } = JSON.parse(upText);

let job; const t0 = Date.now();
for (;;) {
  const r = await A.call(`/jobs/${jobId}`); job = await r.json();
  log(`poll /jobs/${jobId} ${r.status} status=${job.status} ${job.completed_count}/${job.file_count}`);
  if (['completed', 'failed', 'timed_out'].includes(job.status) || Date.now() - t0 > 6 * 60e3) break;
  await new Promise(s => setTimeout(s, 5000));
}
log(`job ended status=${job.status} after ${Math.round((Date.now() - t0) / 1000)} s`);

const docs = await (await A.call('/api/documents')).json();
const mine = files.map((b, i) => [b, docs.find(d => d.original_filename === `p254-batch-${i}.pdf`)]);
for (const [b, d] of mine) {
  const r = await A.call(`/api/documents/${d.id}/file`);
  const body = Buffer.from(await r.arrayBuffer());
  log(`download doc ${d.id} ${r.status} size=${d.file_size_bytes} sha_match=${sha(body) === sha(b)} (${r.ms} ms)`);
}
const d0 = mine[0][1];
const rg = await A.call(`/api/documents/${d0.id}/file`, { headers: { Range: 'bytes=0-15' } });
const rgBody = Buffer.from(await rg.arrayBuffer());
log('range', rg.status, rg.headers.get('content-range'), JSON.stringify(rgBody.toString()));

const s = await A.call('/api/search?q=' + encodeURIComponent('Proxy check'));
log('[a] search', s.status, (await s.text()).slice(0, 160));

const B = await session('b');
const bDocs = await (await B.call('/api/documents')).json();
log('[b] documents count', bDocs.length, 'sees A docs:', bDocs.some(d => d.id === d0.id));
for (const p of [`/api/documents/${d0.id}`, `/api/documents/${d0.id}/file`, `/jobs/${jobId}`]) {
  const r = await B.call(p); log(`[b] GET ${p} -> ${r.status}`);
}
const bs = await (await B.call('/api/search?q=' + encodeURIComponent('Proxy check'))).json();
log('[b] search total_hits', bs.total_hits);

const lo = await A.call('/auth/logout', { method: 'POST' });
log('[a] logout', lo.status, lo.setCookies.join(' | ').slice(0, 160));
console.log(JSON.stringify({ accountA: A.tag, accountB: B.tag, jobId, docIds: mine.map(([, d]) => d.id) }));
