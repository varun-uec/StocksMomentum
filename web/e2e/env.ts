import { fileURLToPath } from 'node:url';
import { assertE2EDatabaseUrl } from './database-url';

/**
 * Tests mutate their database. Require an explicit, separately named target,
 * and refuse to run against the configured application database.
 */
export const E2E_DATABASE_URL = assertE2EDatabaseUrl(process.env);

export const BACKEND_DIR = fileURLToPath(new URL('../../backend', import.meta.url));
