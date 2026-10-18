import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  forbidOnly: Boolean(process.env.CI),
  use: { baseURL: 'http://127.0.0.1:18000', headless: true, trace: 'retain-on-failure' },
  workers: 1,
  projects: [
    { name: 'chromium', testIgnore: '**/responsive-layout.spec.js' },
    { name: 'android-375', testMatch: '**/responsive-layout.spec.js',
      use: { ...devices['Pixel 5'], browserName: 'chromium', viewport: { width: 375, height: 812 } } },
    { name: 'ios-375', testMatch: '**/responsive-layout.spec.js',
      use: { ...devices['iPhone SE'], browserName: 'webkit', viewport: { width: 375, height: 667 } } },
  ],
  reporter: process.env.CI ? [
    ['list'],
    ['junit', { outputFile: 'test-results/frontend-junit.xml' }],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ] : 'list',
  webServer: [
    { command: 'node tests/start-backend.mjs', url: 'http://127.0.0.1:18001/', timeout: 60000, reuseExistingServer: false },
    {
      command: 'npx next dev --hostname 127.0.0.1 --port 18000',
      url: 'http://127.0.0.1:18000/', timeout: 120000, reuseExistingServer: false,
      env: { BACKEND_ORIGIN: 'http://127.0.0.1:18001' },
    },
  ],
});
