import { getBackendOrigin } from './backend-origin.mjs';

export async function getSession(req) {
  const backend = getBackendOrigin();
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
