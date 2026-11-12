import { networkInterfaces } from 'node:os';
import config from './playwright.config.js';

// Exercise production without allowing loopback API targets. Only the isolated
// test backend binds the local LAN interface; no application DB or AI is used.
const address = Object.values(networkInterfaces()).flat()
  .find(entry => entry.family === 'IPv4' && !entry.internal)?.address;
if (!address) throw new Error('Production E2E needs a non-loopback IPv4 interface.');
const origin = `http://${address}:18001`;

export default {
  ...config,
  outputDir: 'test-results/production',
  testMatch: /(?:auth|route-guard|production-proxy)\.spec\.js$/,
  reporter: process.env.CI ? [
    ['list'],
    ['junit', { outputFile: 'test-results/production-junit.xml' }],
    ['html', { outputFolder: 'playwright-production-report', open: 'never' }],
  ] : 'list',
  projects: [{ name: 'chromium' }],
  webServer: [
    { ...config.webServer[0], env: { E2E_BACKEND_HOST: '0.0.0.0', FORWARDED_ALLOW_IPS: address } },
    {
      command: 'npm run build && npm run start -- --port 18000',
      url: 'http://127.0.0.1:18000/',
      timeout: 180000,
      reuseExistingServer: false,
      env: { NODE_ENV: 'production', BACKEND_ORIGIN: origin },
    },
  ],
};
