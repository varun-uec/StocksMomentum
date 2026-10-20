import { execFileSync } from 'node:child_process';
import { expect, test as base, type Locator, type Page } from '@playwright/test';
import { BACKEND_DIR, E2E_DATABASE_URL } from './env';

const injectedNetworkFailures = new WeakMap<Page, number>();

/** Allow one deliberately aborted browser request in a test that verifies recovery. */
export function allowOneInjectedNetworkFailure(page: Page): void {
  injectedNetworkFailures.set(page, (injectedNetworkFailures.get(page) ?? 0) + 1);
}

/** These are normal boundary responses while a first document is being saved. */
async function expectedResponseError(status: number, url: string, body: () => Promise<string>): Promise<boolean> {
  const path = new URL(url).pathname;
  if ((status === 404 || status === 412) && /\/api\/v1\/(drawings|workspaces|screens)\//.test(path)) return true;
  if (status === 404 && path === '/api/v1/indices/NIFTY500/closes') return true;
  // journey 4 stores a research strategy on purpose. Until the app resets it, one load asks for its runs.
  if (status === 404 && url.includes('strategy=benchmark_a_pure_momentum')) return true;
  // The chart fixture E2ECANDLE sits outside every screening run (db.py).
  if (status === 404 && path === '/api/v1/stocks/E2ECANDLE') return true;
  if (status === 422 && /^\/api\/v1\/studio\/families\/\d+\/evaluations$/.test(path)) {
    return (await body()).includes('insufficient data');
  }
  return false;
}

/** Every test fails on a browser console error, an uncaught page error or a CSP violation. */
export const test = base.extend<{ page: Page }>({
  page: async ({ page }, run) => {
    const problems: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() !== 'error') return;
      if (
        msg.text().includes('net::ERR_INTERNET_DISCONNECTED') &&
        (injectedNetworkFailures.get(page) ?? 0) > 0
      ) {
        injectedNetworkFailures.set(page, injectedNetworkFailures.get(page)! - 1);
        return;
      }
      // HTTP failures are checked with their response URL below. Chromium's
      // generic console text omits the URL needed to distinguish expected 404s.
      if (/Failed to load resource: the server responded with a status of \d{3}/.test(msg.text())) return;
      problems.push(`console: ${msg.text()}`);
    });
    page.on('response', async (response) => {
      if (response.headers()['x-e2e-fault-injection'] === 'true') return;
      if (response.status() < 400 || await expectedResponseError(response.status(), response.url(), () => response.text())) return;
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

function db(command: 'reset' | 'age-alerts' | 'holdout-provenance' | 'extra-bar' | 'drop-extra-bar', ...args: string[]): void {
  execFileSync(`${BACKEND_DIR}/.venv/bin/python`, [new URL('./db.py', import.meta.url).pathname, command, ...args], {
    env: { ...process.env, E2E_DATABASE_URL },
  });
}

/** Delete test-created workspace, drawing and alert rows in the marked E2E database. */
export const resetDocuments = (): void => db('reset');

/** Move every alert's armed date 30 days back, so it can fire on stored bars. */
export const ageAlerts = (): void => db('age-alerts');

/** Give TCS one stored bar after the screening run's as-of date (journey 5); `dropExtraBar` removes it. */
export const addExtraBar = (): void => db('extra-bar');
export const dropExtraBar = (): void => db('drop-extra-bar');

/** Change only synthetic E2E10Y bars in the fixed OOS window for a rejection test. */
export const setHoldoutProvenance = (value: 'published' | 'reconstructed'): void =>
  db('holdout-provenance', value);

/** Open the ☰ app menu, where routes, the theme and the shortcuts live (D23). */
export async function openAppMenu(page: Page): Promise<Locator> {
  const menu = page.getByRole('navigation', { name: 'App menu' });
  if (!(await menu.isVisible())) await page.getByRole('button', { name: 'App menu' }).click();
  await expect(menu).toBeVisible();
  return menu;
}

/** Open a right-panel tab. Clicking the open tab collapses the panel (D24), so click only when needed. */
export async function openPanelTab(page: Page, name: string | RegExp): Promise<void> {
  const tab = page.getByRole('tab', { name, exact: typeof name === 'string' });
  if ((await tab.getAttribute('aria-selected')) !== 'true') await tab.click();
  await expect(tab).toHaveAttribute('aria-selected', 'true');
}

/** Open the toolbar's layout chooser, which also holds Sync (D23). */
export async function openLayoutMenu(page: Page): Promise<Locator> {
  const panel = page.getByRole('group', { name: 'Layout and sync' });
  if (!(await panel.isVisible())) {
    const layout = page.getByRole('button', { name: 'Layout', exact: true });
    // Below 1024 px the layout chooser sits in the toolbar's ⋯ menu.
    if (!(await layout.isVisible())) await page.getByRole('button', { name: 'More chart controls' }).click();
    await layout.click();
  }
  await expect(panel).toBeVisible();
  return panel;
}

/** Choose a chart layout, e.g. '2x2'. */
export async function chooseLayout(page: Page, layout: string): Promise<void> {
  // A choice made while the workspace document loads can be replaced by the loaded one; choose until it holds.
  await expect(async () => {
    await (await openLayoutMenu(page)).locator(`input[name="layout"][value="${layout}"]`).click();
    await expect(page.locator('div.chart-page')).toHaveAttribute('data-layout', layout, { timeout: 1500 });
  }).toPass();
}

/** Open the chart's settings gear: volume, moving averages and panes (D23). */
export async function openChartSettings(page: Page): Promise<void> {
  const summary = page.locator('summary[aria-label="Chart settings"]');
  const open = await summary.evaluate((el) => (el.parentElement as HTMLDetailsElement).open);
  if (!open) await summary.click();
}

/** Pick a drawing tool from the grouped rail, through its group's flyout when it is not the shown tool (A4.1). */
export async function pickTool(page: Page, name: string): Promise<void> {
  const rail = page.getByRole('toolbar', { name: 'Drawing tools' });
  const draw = page.getByRole('button', { name: 'Draw', exact: true });
  if (!(await rail.isVisible()) && (await draw.isVisible())) await draw.click();
  const shown = rail.getByRole('button', { name, exact: true });
  if (await shown.isVisible()) return shown.click();
  for (const arrow of await rail.getByRole('button', { name: / tools$/ }).all()) {
    await arrow.click();
    const item = page.getByRole('group', { name: await arrow.getAttribute('aria-label') ?? '' }).getByRole('button', { name, exact: true });
    if (await item.isVisible()) return item.click();
    await page.keyboard.press('Escape');
  }
  throw new Error(`No drawing tool named ${name}`);
}
