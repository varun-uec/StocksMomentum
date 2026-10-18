import type { Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/** M11b: weekly bars, an interval switch apart from the range, one data version. */

test.beforeEach(() => resetDocuments());

const footnote = (page: Page, word: 'daily' | 'weekly') =>
  page.getByText(new RegExp(`^\\d+ ${word} bars from the stored NSE series.* Data version [0-9a-f]{12}\\.$`));

async function ready(page: Page, word: 'daily' | 'weekly'): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(footnote(page, word)).toBeVisible();
}

test('the interval switch shows weekly bars and indicators, and is saved with the chart', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page, 'daily');
  const daily = Number((await footnote(page, 'daily').textContent())!.split(' ')[0]);

  await page.getByLabel('RSI (14)', { exact: true }).check();
  const weeklySeries = page.waitForResponse(
    (r) => r.url().includes('/indicators/series') && r.url().includes('interval=1W') && r.ok(),
  );
  await page.getByRole('button', { name: 'Weekly bars' }).click();
  await ready(page, 'weekly');
  const series = await (await weeklySeries).json();
  expect(series.bars.at(-1).rsi14).not.toBeNull();
  const weekly = Number((await footnote(page, 'weekly').textContent())!.split(' ')[0]);
  expect(weekly).toBeGreaterThan(daily / 6); // about one bar per five sessions
  expect(weekly).toBeLessThan(daily / 4);
  await expect(page.getByRole('button', { name: 'Weekly bars' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: '1Y', exact: true })).toHaveAttribute('aria-pressed', 'true'); // the range is unchanged

  await expect
    .poll(async () => {
      const res = await request.get('/api/v1/workspaces/default');
      return res.ok() ? (await res.json()).body.charts.main?.interval : null;
    })
    .toBe('1W');
  await page.reload();
  await ready(page, 'weekly');
});

test('a drawing made on weekly bars stays on the daily chart', async ({ page, request }) => {
  await page.goto('/chart/INFY');
  await ready(page, 'daily');
  await page.getByRole('button', { name: 'Weekly bars' }).click();
  await ready(page, 'weekly');

  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.getByRole('button', { name: 'Horizontal ray' }).click();
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.3);
  await expect
    .poll(async () => {
      const res = await request.get('/api/v1/drawings/INFY');
      return res.ok() ? (await res.json()).body.drawings.length : 0;
    })
    .toBe(1);

  await page.getByRole('button', { name: 'Daily bars' }).click();
  await ready(page, 'daily');
  await expect(page.getByRole('button', { name: 'Clear' })).toBeVisible();
});

test('research screens keep daily bars and offer no interval switch', async ({ page }) => {
  await page.goto('/stock/RELIANCE');
  await expect(page.getByTestId('price-chart').locator('canvas').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Weekly bars' })).toHaveCount(0);
});
