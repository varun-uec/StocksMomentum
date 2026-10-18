import type { APIRequestContext, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/** M13: professional charting. */

test.beforeEach(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ (daily|weekly) bars from the stored NSE series/)).toBeVisible();
}

async function mainChart(request: APIRequestContext): Promise<Record<string, unknown> | null> {
  const res = await request.get('/api/v1/workspaces/default');
  return res.ok() ? (await res.json()).body.charts.main ?? null : null;
}

test('every chart type and price scale draws, and the choice is saved with the chart', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  const type = page.getByLabel('Chart type');
  for (const value of ['bars', 'line', 'area', 'heikin_ashi', 'candles']) {
    await type.selectOption(value);
    await expect(page.getByTestId('price-chart').locator('canvas').first()).toBeVisible();
  }
  await type.selectOption('heikin_ashi');
  await page.getByRole('button', { name: 'Log scale' }).click();
  await expect(page.getByRole('button', { name: 'Log scale' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => mainChart(request)).toMatchObject({ chart_type: 'heikin_ashi', scale: 'log' });

  await page.getByRole('button', { name: 'Percent scale' }).click();
  await expect(page.getByRole('button', { name: 'Log scale' })).toHaveAttribute('aria-pressed', 'false');
  await expect.poll(() => mainChart(request)).toMatchObject({ scale: 'percent' });

  await page.reload();
  await ready(page);
  await expect(page.getByLabel('Chart type')).toHaveValue('heikin_ashi');
  await expect(page.getByRole('button', { name: 'Percent scale' })).toHaveAttribute('aria-pressed', 'true');
});
