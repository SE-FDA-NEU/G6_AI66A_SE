export async function getSession(req) {
  const backend = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8001';
  try {
    const response = await fetch(`${backend}/auth/me`, {
      headers: { cookie: req.headers.cookie || '' },
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}
