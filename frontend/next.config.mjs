const backend = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8001';
export default {
  poweredByHeader: false,
  async rewrites() {
    return [{ source: '/auth/:path*', destination: `${backend}/auth/:path*` }];
  },
};
