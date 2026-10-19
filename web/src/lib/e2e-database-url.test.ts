import { describe, expect, it } from 'vitest';
import { assertE2EDatabaseUrl } from '../../e2e/database-url';

describe('E2E database isolation', () => {
  it('requires an explicit E2E database URL', () => {
    expect(() => assertE2EDatabaseUrl({})).toThrow(/Set E2E_DATABASE_URL/);
  });

  it('requires the target database name to end in _e2e', () => {
    expect(() =>
      assertE2EDatabaseUrl({ E2E_DATABASE_URL: 'postgresql+asyncpg://test:test@localhost:5432/momentum25' }),
    ).toThrow(/ending in _e2e/);
  });

  it('refuses the configured application database even when its URL differs', () => {
    expect(() =>
      assertE2EDatabaseUrl({
        E2E_DATABASE_URL: 'postgresql+asyncpg://test:test@localhost:5432/momentum25_e2e',
        M25_DATABASE_URL: 'postgresql+asyncpg://test:test@127.0.0.1:5432/momentum25_e2e',
      }),
    ).toThrow(/different database target/);
  });

  it('does not include credentials in malformed URL errors', () => {
    expect(() => assertE2EDatabaseUrl({ E2E_DATABASE_URL: 'postgresql://secret:password@/' })).toThrow(
      /Credentials are omitted/,
    );
  });

  it('accepts a separate explicitly named E2E target on the same PostgreSQL server', () => {
    const url = 'postgresql+asyncpg://audit:audit@127.0.0.1:5432/wickstreet_audit_e2e';
    expect(
      assertE2EDatabaseUrl({
        E2E_DATABASE_URL: url,
        M25_DATABASE_URL: 'postgresql+asyncpg://app:secret@localhost:5432/wickstreet',
      }),
    ).toBe(url);
  });
});
