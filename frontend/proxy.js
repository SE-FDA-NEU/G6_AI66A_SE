import { NextResponse } from 'next/server';
import { getSession } from './lib/session';

// Next.js 16 calls request middleware "Proxy".
export async function proxy(request) {
  if (request.cookies.get('documind_session')?.value) {
    // FastAPI verifies the JWT signature, expiry and account existence.
    const user = await getSession({ headers: { cookie: request.headers.get('cookie') || '' } });
    if (user) {
      const response = NextResponse.next();
      response.headers.set('Cache-Control', 'no-store');
      return response;
    }
  }

  const response = NextResponse.redirect(new URL('/', request.url));
  response.headers.set('Cache-Control', 'no-store');
  return response;
}

export const config = {
  matcher: [
    '/workspace/:path*',
    '/upload/:path*',
    '/results/:path*',
    '/documents/:path*',
  ],
};
