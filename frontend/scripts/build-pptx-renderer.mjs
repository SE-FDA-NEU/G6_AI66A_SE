import { build } from 'esbuild';
import { mkdir } from 'node:fs/promises';
await mkdir(new URL('../public/', import.meta.url), { recursive: true });
await build({
  entryPoints: [new URL('../browser/pptx-renderer.js', import.meta.url).pathname],
  outfile: new URL('../public/pptx-renderer.js', import.meta.url).pathname,
  bundle: true, format: 'iife', platform: 'browser', target: 'es2020',
  minify: true, legalComments: 'eof',
});
