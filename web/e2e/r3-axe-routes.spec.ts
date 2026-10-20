import { resolve } from 'node:path';
import { expect, SYMBOL, test } from './fixtures';

/** Round 3: every route, both themes, no WCAG 2.x A/AA axe violation and one main landmark. */
const ROUTES = [
  '/',
  `/chart/${SYMBOL}`,
  `/stock/${SYMBOL}`,
  `/stock/${SYMBOL}/analysis`,
  `/stock/${SYMBOL}/elliott-wave`,
  '/watchlist',
  '/market',
  '/strategies',
  '/studio',
  '/validation',
  '/backtest',
  '/historical',
  '/experiment',
  '/analytics',
  '/data',
  '/about',
  '/learn',
  '/learn/faq',
  '/learn/momentum-investing',
  '/learn/minervini-methodology',
  '/learn/momentum25-methodology',
  '/learn/scoring-guide',
  '/learn/rule-guide',
];

test('every route has one main landmark and no WCAG A/AA axe violation in light and dark', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript({ path: resolve(process.cwd(), 'node_modules/axe-core/axe.min.js') });
  const found: string[] = [];
  for (const theme of ['light', 'dark'] as const) {
    await page.goto('/about');
    await page.evaluate((mode) => localStorage.setItem('m25-theme', mode), theme);
    for (const path of ROUTES) {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('h1').first()).toBeVisible();
      const mains = await page.locator('main, [role="main"]').count();
      if (mains !== 1) found.push(`${theme} ${path}: ${mains} main landmarks`);
      const violations = await page.evaluate(async () => {
        const axe = (window as unknown as {
          axe: { run: (d: Document, o: object) => Promise<{ violations: { id: string; nodes: { target: unknown[] }[] }[] }> };
        }).axe;
        const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
        return r.violations.map((v) => `${v.id} x${v.nodes.length} e.g. ${String(v.nodes[0].target[0]).slice(0, 70)}`);
      });
      violations.forEach((v) => found.push(`${theme} ${path}: ${v}`));
    }
  }
  expect(found, 'axe findings and landmark counts').toEqual([]);
});
