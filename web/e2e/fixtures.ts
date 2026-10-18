import { execFileSync } from 'node:child_process';
import { expect, test as base, type Page } from '@playwright/test';
import { BACKEND_DIR, E2E_DATABASE_URL } from './env';

/**
 * Chrome logs every 4xx response as a console error. A saved document answers
 * 404 before its first save and 412 when another window saved first; both are
 * normal (ADR-013 §5), so only those are allowed.
 */
function expectedDocumentStatus(text: string, url: string): boolean {
  return /\/api\/v1\/(drawings|workspaces)\//.test(url) && /status of (404|412)/.test(text);
}

/** Every test fails on a browser console error, an uncaught page error or a CSP violation. */
export const test = base.extend<{ page: Page }>({
  page: async ({ page }, run) => {
    const problems: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() !== 'error' || expectedDocumentStatus(msg.text(), msg.location().url)) return;
      problems.push(`console: ${msg.text()}`);
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

/** Delete every saved workspace, drawing and alert in the E2E clone. */
export const resetDocuments = (): void => db('reset');

/** Move every alert's armed date 30 days back, so it can fire on stored bars. */
export const ageAlerts = (): void => db('age-alerts');
