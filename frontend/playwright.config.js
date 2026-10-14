import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:18000', headless: true, trace: 'retain-on-failure' },
  workers: 1,
  reporter: 'list',
  webServer: [
    { command: 'node tests/start-backend.mjs', url: 'http://127.0.0.1:18001/', timeout: 60000, reuseExistingServer: false },
    {
      command: 'npx next dev --hostname 127.0.0.1 --port 18000',
      url: 'http://127.0.0.1:18000/', timeout: 120000, reuseExistingServer: false,
      env: { BACKEND_ORIGIN: 'http://127.0.0.1:18001' },
    },
  ],
});
