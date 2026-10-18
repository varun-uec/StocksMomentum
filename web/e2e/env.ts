import { fileURLToPath } from 'node:url';

/** The E2E database clone (`make e2e-db`). Override with E2E_DATABASE_URL. */
export const E2E_DATABASE_URL =
  process.env.E2E_DATABASE_URL ?? 'postgresql+asyncpg://momentum25:momentum25@localhost:5432/momentum25_e2e';

export const BACKEND_DIR = fileURLToPath(new URL('../../backend', import.meta.url));
