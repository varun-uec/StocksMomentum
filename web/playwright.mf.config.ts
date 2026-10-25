import { defineConfig, devices } from '@playwright/test';
import { runArtifacts } from './e2e/run-artifacts';

/**
 * MF workstation journeys (Slice 4). They read the local Wickstreet API with
 * real MF data through `vite preview` (its proxy rewrites Host and Origin) and
 * never write to it: every /workspace call is answered by an in-memory mock.
 * Point WICKSTREET_API_TARGET at another API to test against it. Set
 * MF_BASE_URL (for example http://localhost:8000) to test an app that is already
 * served, such as the deployed container, instead of a fresh preview build.
 */
const PORT = Number(process.env.MF_PREVIEW_PORT ?? 8767);
if (!Number.isInteger(PORT) || PORT < 1024 || PORT > 65535) throw new Error('MF_PREVIEW_PORT must be 1024–65535');
const artifacts = runArtifacts('mf');
const served = process.env.MF_BASE_URL;

export default defineConfig({
  testDir: './e2e/mf',
  outputDir: artifacts.results,
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
        command: `npm run build -- --outDir "${artifacts.dist}" && npx vite preview --outDir "${artifacts.dist}" --port ${PORT} --strictPort`,
        url: `http://localhost:${PORT}/mf`,
        reuseExistingServer: false,
        timeout: 180_000,
      },
});
