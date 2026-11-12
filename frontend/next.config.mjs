import { readFileSync } from 'node:fs';
import { getBackendOrigin, backendRewrites, assertBuiltBackend } from './lib/backend-origin.mjs';

export default function config(phase) {
  const production = phase === 'phase-production-build' || phase === 'phase-production-server';
  const backend = getBackendOrigin(process.env, production);
  if (phase === 'phase-production-server') {
    let manifest;
    try {
      manifest = JSON.parse(readFileSync(new URL('./.next/routes-manifest.json', import.meta.url), 'utf8'));
    } catch (error) {
      // Let Next.js report a missing production build itself.
      if (error.code !== 'ENOENT') throw error;
    }
    if (manifest) assertBuiltBackend(manifest.rewrites, backend);
  }
  return {
    // Five 5 MiB files plus multipart overhead must survive external rewrites.
    experimental: { agentUpgrade: 'security', proxyClientMaxBodySize: '30mb' },
    devIndicators: false,
    poweredByHeader: false,
    async rewrites() {
      return backendRewrites(backend);
    },
  };
}
