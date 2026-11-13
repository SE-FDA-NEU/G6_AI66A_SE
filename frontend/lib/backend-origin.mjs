// Server-only configuration shared by rewrites and SSR session lookup.
export function getBackendOrigin(env = process.env, production = env.NODE_ENV === 'production') {
  const value = env.BACKEND_ORIGIN?.trim();
  if (!value && production) throw new Error('BACKEND_ORIGIN is required in production (build and runtime).');
  const url = new URL(value || 'http://127.0.0.1:8001');
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) {
    throw new Error('BACKEND_ORIGIN must be an HTTP(S) origin without credentials, path, query or fragment.');
  }
  const host = url.hostname.replace(/\.$/, '').toLowerCase();
  if (production && (host === 'localhost' || host.endsWith('.localhost') ||
      /^127\./.test(host) || host === '0.0.0.0' || host === '[::1]' || host === '[::]' ||
      host.startsWith('[::ffff:'))) {
    throw new Error('BACKEND_ORIGIN must not target localhost or a loopback address in production.');
  }
  return url.origin;
}

export function backendRewrites(origin) {
  return [
    { source: '/health', destination: `${origin}/health` },
    { source: '/auth/:path*', destination: `${origin}/auth/:path*` },
    { source: '/jobs/:path*', destination: `${origin}/jobs/:path*` },
    { source: '/api/upload', destination: `${origin}/upload` },
    { source: '/api/search', destination: `${origin}/search` },
    { source: '/api/folders', destination: `${origin}/folders` },
    { source: '/api/documents/:path*', destination: `${origin}/documents/:path*` },
  ];
}

export function assertBuiltBackend(rewrites, origin) {
  const built = Array.isArray(rewrites) ? rewrites : Object.values(rewrites).flat();
  for (const expected of backendRewrites(origin)) {
    if (!built.some(rule => rule.source === expected.source && rule.destination === expected.destination)) {
      throw new Error('BACKEND_ORIGIN differs from the built API rewrites. Rebuild before starting.');
    }
  }
}
