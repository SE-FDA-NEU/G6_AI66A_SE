const backend = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8001';
export default {
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: '/auth/:path*', destination: `${backend}/auth/:path*` },
      { source: '/jobs/:path*', destination: `${backend}/jobs/:path*` },
      { source: '/api/upload', destination: `${backend}/upload` },
      { source: '/api/search', destination: `${backend}/search` },
      { source: '/api/folders', destination: `${backend}/folders` },
      { source: '/api/documents/:path*', destination: `${backend}/documents/:path*` },
    ];
  },
};
