import { resolve } from 'node:path';
import { FUND, OTHER, expect, test } from './fixtures';

const ROUTES = [
  '/mf',
  '/mf/screen',
  '/mf/screen?preset=calm_equity',
  `/mf/funds/${FUND}`,
  `/mf/funds/${FUND}?tab=performance`,
  `/mf/funds/${FUND}?tab=risk`,
  `/mf/funds/${FUND}?tab=peers`,
  `/mf/funds/${FUND}?tab=facts`,
  `/mf/funds/${FUND}?tab=benchmark`,
  `/mf/funds/${FUND}?tab=holdings`,
  `/mf/funds/${FUND}?tab=profile`,
  `/mf/studio?code=${FUND}`,
  `/mf/studio?mode=frontier&code=${FUND}`,
  '/mf/studio?mode=transitions',
  `/mf/studio?mode=regimes&code=${FUND}`,
  `/mf/compare?code=${FUND}&code=${OTHER}`,
  `/mf/compare?code=${FUND}&code=119076`,
  `/mf/simulate?code=${FUND}`,
  '/mf/workspace',
  '/mf/workspace?tab=alerts',
  '/mf/portfolio',
  '/mf/ask',
];

/** Every MF route, both themes: one main landmark and no WCAG 2.1 A/AA axe violation. */
test('MF routes pass axe in light and dark', async ({ page }) => {
  test.setTimeout(300_000);
  await page.addInitScript({ path: resolve(process.cwd(), 'node_modules/axe-core/axe.min.js') });
  const found: string[] = [];
  for (const theme of ['light', 'dark'] as const) {
    await page.goto('/mf/ask');
    await page.evaluate((mode) => localStorage.setItem('m25-theme', mode), theme);
    for (const path of ROUTES) {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('h1').first()).toBeAttached();
      const mains = await page.locator('main, [role="main"]').count();
      if (mains !== 1) found.push(`${theme} ${path}: ${mains} main landmarks`);
      const violations = await page.evaluate(async () => {
        const axe = (window as unknown as {
          axe: { run: (d: Document, o: object) => Promise<{ violations: { id: string; nodes: { target: unknown[] }[] }[] }> };
        }).axe;
        const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
        return r.violations.map((v) => `${v.id} x${v.nodes.length} e.g. ${String(v.nodes[0].target[0]).slice(0, 80)}`);
      });
      violations.forEach((v) => found.push(`${theme} ${path}: ${v}`));
    }
  }
  expect(found, 'axe findings and landmark counts').toEqual([]);
});

test('keyboard: "/" focuses fund search, arrows pick a result, Enter opens it', async ({ page }) => {
  await page.goto('/mf');
  // Routes load as separate chunks: wait for the shell before using its shortcut.
  await expect(page.getByRole('combobox', { name: 'Search funds', exact: true })).toBeVisible();
  await page.keyboard.press('/');
  await page.keyboard.type('parag parikh flexi');
  const option = page.getByRole('option').first();
  await expect(option).toBeVisible();
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('ArrowUp');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/mf\/funds\/\d+/);
});
