import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests run the production build, served by the real API, against a
 * CLONE of the local database, so tests that save data never touch your own
 * workspace. Create the clone once with `make e2e-db`.
 *
 * E2E_DATABASE_URL overrides the clone's address (default: port 5432).
 */
const PORT = 8765;
const webDist = fileURLToPath(new URL('./dist', import.meta.url));
const backend = fileURLToPath(new URL('../backend', import.meta.url));
const databaseUrl =
  process.env.E2E_DATABASE_URL ?? 'postgresql+asyncpg://momentum25:momentum25@localhost:5432/momentum25_e2e';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run build && cd ${backend} && .venv/bin/uvicorn momentum25.main:app --host 127.0.0.1 --port ${PORT} --app-dir src`,
    url: `http://localhost:${PORT}/api/v1/health/live`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      M25_DATABASE_URL: databaseUrl,
      M25_WEB_DIST_DIR: webDist,
      M25_STRATEGY_DIR: '../docs/architecture/strategies',
      M25_SCHEDULER_ENABLED: 'false',
      M25_ENVIRONMENT: 'test',
      M25_LOG_JSON: 'false',
      M25_RATE_LIMIT_MAX_REQUESTS: '100000',
    },
  },
});
