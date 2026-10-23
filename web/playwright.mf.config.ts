import { defineConfig, devices } from '@playwright/test';

/**
 * MF workstation journeys (Slice 4). They read the local Wickstreet API with
 * real MF data through `vite preview` (its proxy rewrites Host and Origin) and
 * never write to it: every /workspace call is answered by an in-memory mock.
 * Point WICKSTREET_API_TARGET at another API to test against it. Set
 * MF_BASE_URL (for example http://localhost:8000) to test an app that is already
 * served, such as the deployed container, instead of a fresh preview build.
 */
const PORT = 8767;
const served = process.env.MF_BASE_URL;

export default defineConfig({
  testDir: './e2e/mf',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [['list']],
  use: { baseURL: served ?? `http://localhost:${PORT}`, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: served
    ? undefined
    : {
        command: `npm run build && npx vite preview --port ${PORT} --strictPort`,
        url: `http://localhost:${PORT}/mf`,
        reuseExistingServer: false,
        timeout: 180_000,
      },
});
