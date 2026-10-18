import { fileURLToPath } from 'node:url';

/**
 * The E2E database clone (`make e2e-db`). Tests reset its saved documents, so
 * it must be named explicitly and must be a clone: there is no default, and
 * the app database (`M25_DATABASE_URL`) is never used. The app under test and
 * every cleanup read this one value.
 */
function e2eDatabaseUrl(): string {
  const url = process.env.E2E_DATABASE_URL;
  if (!url) {
    throw new Error(
      'Set E2E_DATABASE_URL to the E2E clone, e.g. postgresql+asyncpg://momentum25:momentum25@localhost:5432/momentum25_e2e',
    );
  }
  if (!/\/[^/?]+_e2e(\?|$)/.test(url)) throw new Error(`E2E_DATABASE_URL must name a database ending in _e2e: ${url}`);
  return url;
}

export const E2E_DATABASE_URL = e2eDatabaseUrl();

export const BACKEND_DIR = fileURLToPath(new URL('../../backend', import.meta.url));
