import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:5179',
    headless: true,
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: 'cd ../backend && source venv/bin/activate && DATABASE_URL=sqlite:///./test_e2e.db uvicorn app.main:app --port 8000',
      port: 8000,
      timeout: 15000,
      reuseExistingServer: false,
    },
    {
      command: 'npx vite --port 5179',
      port: 5179,
      timeout: 15000,
      reuseExistingServer: false,
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});
