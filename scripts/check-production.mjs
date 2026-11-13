// Read-only public smoke checks; never substitutes for P0/browser/deployment acceptance.
import { writeFile } from 'node:fs/promises';

const frontend = new URL(process.env.DOCUMIND_FRONTEND || 'https://documind-web-k6i1.onrender.com');
const backend = new URL(process.env.DOCUMIND_BACKEND || 'https://documind-n9ny.onrender.com');
for (const url of [frontend, backend]) {
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('Production targets must be HTTPS origins without credentials, paths or query strings.');
  }
}
const report = { started_at: new Date().toISOString(), frontend: frontend.origin,
  backend: backend.origin, scope: 'read-only health and guest access; not full release acceptance', checks: [] };
async function check(name, url, verify) {
  const started = Date.now();
  try {
    const response = await fetch(url, { redirect: 'manual', signal: AbortSignal.timeout(55000) });
    const result = await verify(response);
    report.checks.push({ name, pass: result === true, http_status: response.status,
      elapsed_ms: Date.now() - started, ...(result === true ? {} : { reason: result }) });
  } catch {
    // Do not serialize provider/network errors, headers, tokens or response bodies.
    report.checks.push({ name, pass: false, elapsed_ms: Date.now() - started,
      reason: 'Request timed out, failed, or returned an invalid response.' });
  }
}
await check('public landing', frontend, async response => {
  const text = await response.text();
  return response.status === 200 && /DocuMind/i.test(text) && /<form/i.test(text)
    ? true : 'Expected the application sign-in page, not a platform loading page.';
});
for (const [name, origin] of [['frontend readiness', frontend], ['backend readiness', backend]]) {
  await check(name, new URL('/health', origin), async response => {
    const body = await response.json();
    return response.status === 200 && body.status === 'ok' && body.database === 'ready'
      && response.headers.get('cache-control') === 'no-store'
      ? true : 'Expected uncached HTTP 200 with API/database ready.';
  });
}
for (const path of ['/workspace', '/upload', '/results/1', '/documents/1']) {
  await check(`guest guard ${path}`, new URL(path, frontend), response => {
    const location = response.headers.get('location');
    return [302, 303, 307, 308].includes(response.status) && location
      && new URL(location, frontend).origin === frontend.origin
      && new URL(location, frontend).pathname === '/'
      ? true : 'Expected a same-origin redirect to the sign-in page.';
  });
}
for (const path of ['/auth/me', '/jobs', '/api/documents', '/api/search?q=synthetic']) {
  await check(`guest API ${path}`, new URL(path, frontend), response =>
    response.status === 401 ? true : 'Expected HTTP 401 without authentication.');
}
report.finished_at = new Date().toISOString();
report.passed = report.checks.every(check => check.pass);
const output = JSON.stringify(report, null, 2) + '\n';
if (process.argv[2]) await writeFile(process.argv[2], output, { flag: 'wx' });
process.stdout.write(output);
if (!report.passed) process.exitCode = 1;
