/** Validate that a Playwright database target is explicit and isolated. */
export function assertE2EDatabaseUrl(env: {
  E2E_DATABASE_URL?: string;
  M25_DATABASE_URL?: string;
}): string {
  const raw = env.E2E_DATABASE_URL;
  if (!raw) {
    throw new Error(
      'Set E2E_DATABASE_URL to a dedicated PostgreSQL database ending in _e2e. The application database is never used by Playwright.',
    );
  }

  const target = parsePostgresTarget(raw, 'E2E_DATABASE_URL');
  if (!target.database.endsWith('_e2e')) {
    throw new Error('E2E_DATABASE_URL must name a dedicated database ending in _e2e.');
  }

  const applicationUrl = env.M25_DATABASE_URL;
  if (applicationUrl) {
    const application = parsePostgresTarget(applicationUrl, 'M25_DATABASE_URL');
    if (
      target.database === application.database &&
      target.host === application.host &&
      target.port === application.port
    ) {
      throw new Error('E2E_DATABASE_URL must point to a different database target than M25_DATABASE_URL.');
    }
  }

  return raw;
}

function parsePostgresTarget(raw: string, variable: string): { host: string; port: string; database: string } {
  try {
    const url = new URL(raw);
    if (!['postgres:', 'postgresql:', 'postgresql+asyncpg:'].includes(url.protocol)) throw new Error();
    const database = decodeURIComponent(url.pathname.slice(1));
    if (!url.hostname || !database) throw new Error();
    const host = url.hostname.toLowerCase() === 'localhost' ? '127.0.0.1' : url.hostname.toLowerCase();
    return { host, port: url.port || '5432', database };
  } catch {
    throw new Error(`${variable} must be a valid PostgreSQL URL. Credentials are omitted from this error.`);
  }
}
