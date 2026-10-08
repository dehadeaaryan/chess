import { defineConfig, devices } from '@playwright/test';

const localURL = process.env.CHESS_BASE_URL;

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  retries: 0,
  reporter: 'list',
  use: { baseURL: localURL || 'http://127.0.0.1:5179', trace: 'retain-on-failure', screenshot: 'only-on-failure', reducedMotion: 'reduce' },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1100 } } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 5'] } },
  ],
  webServer: localURL ? [] : [
    { command: '../.venv/bin/uvicorn chess_game.api:app --host 127.0.0.1 --port 8101', url: 'http://127.0.0.1:8101/api/health', reuseExistingServer: false },
    { command: 'CHESS_API_URL=http://127.0.0.1:8101 bun run dev -- --host 127.0.0.1 --port 5179 --strictPort', url: 'http://127.0.0.1:5179', reuseExistingServer: false },
  ],
});
