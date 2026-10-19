import { execFileSync } from 'node:child_process';
import { expect, test as base, type Page } from '@playwright/test';
import { BACKEND_DIR, E2E_DATABASE_URL } from './env';

/** These are normal boundary responses while a first document is being saved. */
function expectedResponseError(status: number, url: string): boolean {
  const path = new URL(url).pathname;
  if ((status === 404 || status === 412) && /\/api\/v1\/(drawings|workspaces)\//.test(path)) return true;
  return status === 404 && path === '/api/v1/indices/NIFTY500/closes';
}

/** Every test fails on a browser console error, an uncaught page error or a CSP violation. */
export const test = base.extend<{ page: Page }>({
  page: async ({ page }, run) => {
    const problems: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() !== 'error') return;
      // HTTP failures are checked with their response URL below. Chromium's
      // generic console text omits the URL needed to distinguish expected 404s.
      if (/Failed to load resource: the server responded with a status of \d{3}/.test(msg.text())) return;
      problems.push(`console: ${msg.text()}`);
    });
    page.on('response', (response) => {
      if (response.headers()['x-e2e-fault-injection'] === 'true') return;
      if (response.status() < 400 || expectedResponseError(response.status(), response.url())) return;
      problems.push(`HTTP ${response.status()}: ${response.url()}`);
    });
    page.on('pageerror', (err) => problems.push(`pageerror: ${err.message}`));
    await run(page);
    expect(problems, 'browser errors').toEqual([]);
  },
});

export { expect };

/** A symbol present in every local dataset since 2019. */
export const SYMBOL = 'RELIANCE';

function db(command: 'reset' | 'age-alerts'): void {
  execFileSync(`${BACKEND_DIR}/.venv/bin/python`, [new URL('./db.py', import.meta.url).pathname, command], {
    env: { ...process.env, E2E_DATABASE_URL },
  });
}

/** Delete test-created workspace, drawing and alert rows in the marked E2E database. */
export const resetDocuments = (): void => db('reset');

/** Move every alert's armed date 30 days back, so it can fire on stored bars. */
export const ageAlerts = (): void => db('age-alerts');
