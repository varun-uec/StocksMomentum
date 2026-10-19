import { writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import os from 'node:os';
import { expect, resetDocuments, test } from './fixtures';

const evidence = resolve(process.cwd(), '../audit-evidence/r2');
const routes: [string, string][] = [
  ['dashboard', '/'],
  ['chart-entry', '/chart'],
  ['chart', '/chart/RELIANCE'],
  ['stock-detail', '/stock/RELIANCE'],
  ['stock-analysis', '/stock/RELIANCE/analysis'],
  ['elliott-wave', '/stock/RELIANCE/elliott-wave'],
  ['watchlist', '/watchlist'],
  ['market', '/market'],
  ['strategies', '/strategies'],
  ['studio', '/studio'],
  ['validation', '/validation'],
  ['backtest', '/backtest'],
  ['historical', '/historical'],
  ['experiment', '/experiment'],
  ['analytics', '/analytics'],
  ['data', '/data'],
  ['learn', '/learn'],
  ['learn-momentum-investing', '/learn/momentum-investing'],
  ['learn-minervini-methodology', '/learn/minervini-methodology'],
  ['learn-momentum25-methodology', '/learn/momentum25-methodology'],
  ['learn-scoring-guide', '/learn/scoring-guide'],
  ['learn-rule-guide', '/learn/rule-guide'],
  ['learn-faq', '/learn/faq'],
  ['about', '/about'],
  ['chart-grid-diagnostic', '/lab/chart-grid?n=4&symbol=RELIANCE'],
  ['not-found', '/audit-missing-route'],
];
const viewports = [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
];
const themes = ['light', 'dark'] as const;
const screenshotRoutes = new Set(['dashboard', 'chart', 'strategies', 'studio', 'market']);

test.beforeEach(() => resetDocuments());

test('R2 all 26 routes render in both themes at four requested viewport sizes', async ({ page, browser }) => {
  test.setTimeout(900_000);
  const measurements: {
    route: string;
    path: string;
    theme: string;
    viewport: string;
    document_width: number;
    body_width: number;
    scroll_height: number;
  }[] = [];

  await page.goto('/about');
  for (const [name, path] of routes) {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      for (const theme of themes) {
        await page.evaluate((mode) => localStorage.setItem('m25-theme', mode), theme);
        await page.goto(path);
        if (name === 'chart-grid-diagnostic') {
          await expect(page.getByTestId('chart-cell')).toHaveCount(4);
        } else {
          await expect(page.locator('h1').first()).toBeVisible();
        }
        await page.waitForLoadState('networkidle');
        if (theme === 'dark') {
          await expect(page.locator('html')).toHaveClass(/\bdark\b/);
        } else {
          await expect(page.locator('html')).not.toHaveClass(/\bdark\b/);
        }
        const bounds = await page.evaluate(() => ({
          document_width: document.documentElement.scrollWidth,
          body_width: document.body.scrollWidth,
          scroll_height: document.documentElement.scrollHeight,
        }));
        measurements.push({
          route: name,
          path,
          theme,
          viewport: `${viewport.width}x${viewport.height}`,
          ...bounds,
        });

        if (screenshotRoutes.has(name)) {
          await page.screenshot({
            path: join(evidence, `viewport-${name}-${theme}-${viewport.width}x${viewport.height}.png`),
          });
        }
      }
    }
  }

  writeFileSync(
    join(evidence, 'viewport-audit.json'),
    JSON.stringify(
      {
        audited_at: new Date().toISOString(),
        browser: `Chromium ${browser.version()} (headless)`,
        hardware: `${os.cpus()[0]?.model ?? 'unknown CPU'} × ${os.cpus().length}, ${Math.round(os.totalmem() / 2 ** 30)} GB RAM`,
        requested_viewports: viewports,
        routes: routes.length,
        themes: [...themes],
        total_render_states: measurements.length,
        measurements,
      },
      null,
      2,
    ),
  );

  // A horizontal scroll within a table may be intentional, but page-level
  // overflow clips controls and makes the shell hard to operate by touch.
  const overflow = measurements.filter((m) => m.document_width > Number(m.viewport.split('x')[0]) + 2);
  expect(overflow, 'routes with page-level horizontal overflow').toEqual([]);
});
