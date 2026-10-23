import { defineConfig, devices } from '@playwright/test';

/**
 * MF workstation journeys (Slice 4). They read the local Wickstreet API with
 * real MF data through `vite preview` (its proxy rewrites Host and Origin) and
 * never write to it: every /workspace call is answered by an in-memory mock.
 * Point WICKSTREET_API_TARGET at another API to test against it.
 */
const PORT = 8767;

export default defineConfig({
  testDir: './e2e/mf',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [['list']],
  use: { baseURL: `http://localhost:${PORT}`, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run build && npx vite preview --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}/mf`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
