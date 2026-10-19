import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, resetDocuments, test } from './fixtures';

/**
 * A9.1 (plan 2026-10-19): Wickstreet screenshots of the TradingView-structured
 * screens at four widths in both themes, with the geometry the plan names
 * (header, rail, strip, range bar) and page overflow for each.
 */

const evidence = resolve(process.cwd(), '..', 'audit-evidence', 'tradingview-clone');
const SCREENS = [
  ['chart', '/chart/RELIANCE'],
  ['screener', '/'],
  ['symbol', '/stock/RELIANCE'],
  ['research', '/backtest'],
] as const;
const SIZES = [[1920, 1080], [1440, 900], [768, 1024], [390, 844]] as const;

test('TradingView-structure screenshots at four widths in both themes', async ({ page }) => {
  test.setTimeout(240_000);
  resetDocuments();
  mkdirSync(evidence, { recursive: true });
  const geometry: object[] = [];
  for (const theme of ['light', 'dark'] as const) {
    for (const [width, height] of SIZES) {
      await page.setViewportSize({ width, height });
      for (const [name, path] of SCREENS) {
        await page.goto(path);
        await page.evaluate((value) => localStorage.setItem('m25-theme', value), theme);
        await page.reload();
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 15_000 });
        await page.waitForLoadState('networkidle');
        // Some regions do not exist at every width (no strip below 1024 px): measure only what is there.
        const box = async (selector: string) => {
          const found = page.locator(selector).first();
          return (await found.count()) ? await found.boundingBox() : null;
        };
        const measured = {
          name,
          width,
          height,
          theme,
          header: await box('header.ws-header'),
          rail: name === 'chart' ? await box('.chart-rail') : null,
          strip: await box('.ws-strip'),
          rangeBar: name === 'chart' ? await box('.chart-rangebar') : null,
          plot: name === 'chart' ? await box('[data-testid="price-chart"]') : null,
          overflow: await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth),
        };
        expect(measured.overflow, `${name} ${width}px ${theme}`).toBeLessThanOrEqual(2);
        geometry.push(measured);
        await page.screenshot({ path: resolve(evidence, `${name}-${width}-${theme}.png`) });
      }
    }
  }
  writeFileSync(resolve(evidence, 'geometry.json'), JSON.stringify(geometry, null, 2));
});
