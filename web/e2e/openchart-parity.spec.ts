import type { APIRequestContext, Page } from '@playwright/test';
import { chooseLayout, expect, resetDocuments, test } from './fixtures';

/**
 * Regressions for the defects the OpenChart parity audit (2026-10-19) found.
 * The synthetic bars end on 2026-08-07, weeks before the test date, which is
 * the stale-data case D1 needs.
 */

test.beforeEach(() => resetDocuments());
// Later specs read the workspace without resetting it; leave no grid layout behind.
test.afterAll(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ (daily|weekly|monthly) bars from the stored NSE series/).first()).toBeVisible();
}

async function drawings(request: APIRequestContext, symbol: string): Promise<{ kind: string; points: { date: string }[] }[]> {
  const res = await request.get(`/api/v1/drawings/${symbol}`);
  return res.ok() ? (await res.json()).body.drawings : [];
}

test('D1, D2: a short range counts back from the last bar, and MA200 has a value on it', async ({ page }) => {
  await page.goto('/chart/RELIANCE');
  await ready(page);
  for (const range of ['1W', '1M']) {
    await page.getByRole('button', { name: range, exact: true }).click();
    await expect(page.getByTestId('price-chart')).toHaveAttribute('aria-label', /Price chart, [1-9]\d* daily bars from .* to 2026-08-07/);
  }
  // Five bars on screen; the 200-bar mean still comes from the stored closes before them.
  await page.getByRole('button', { name: '1W', exact: true }).click();
  await expect(page.getByText('MA200', { exact: true }).last().locator('xpath=following-sibling::*[1]')).toHaveText(/^\d+\.\d{2}$/);
});

test('D3: RSI from the indicator dialog reads once, and the pane row turns it off', async ({ page }) => {
  await page.goto('/chart/RELIANCE');
  await ready(page);
  await page.getByRole('button', { name: 'Indicators', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Indicators' });
  await dialog.getByRole('button', { name: /RSI \(14\)/ }).click();
  await page.keyboard.press('Escape');
  const chart = page.getByTestId('price-chart');
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.3);
  const readout = page.getByTestId('crosshair-readout');
  await expect(readout).toBeVisible();
  await expect(readout.getByText(/^RSI \(14\):/)).toHaveCount(1);

  await page.getByText('Studies', { exact: true }).click();
  const rsi = page.getByRole('checkbox', { name: 'RSI (14)' });
  await expect(rsi).toBeChecked();
  await rsi.click();
  await expect(rsi).not.toBeChecked();
  await expect(page.getByRole('button', { name: 'Indicators', exact: true })).toBeVisible(); // no "· 1" count left
});

test('D4: the crosshair readout stays clear of the price axis', async ({ page }) => {
  await page.goto('/chart/RELIANCE');
  await ready(page);
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  const readout = (await page.getByTestId('crosshair-readout').boundingBox())!;
  expect(readout.x + readout.width).toBeLessThan(box.x + box.width / 2);
});

test('D5, D10: workspace keys work after a checkbox click, and Enter adds the first indicator match', async ({ page }) => {
  await page.goto('/chart/RELIANCE');
  await ready(page);
  await page.getByText('Studies', { exact: true }).click();
  await page.getByRole('checkbox', { name: 'MA20', exact: true }).click();
  await page.keyboard.press('Alt+KeyI');
  const dialog = page.getByRole('dialog', { name: 'Indicators' });
  await expect(dialog).toBeVisible();
  await dialog.getByPlaceholder('Search indicators…').fill('boll');
  await page.keyboard.press('Enter');
  await expect(dialog.getByText('Bollinger upper (20, 2σ)')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Indicators · 1' })).toBeVisible();
});

test('D6: a double-click with a two-point tool saves nothing; two distinct clicks save the line', async ({ page, request }) => {
  await page.goto('/chart/INFY');
  await ready(page);
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  const rail = page.getByRole('toolbar', { name: 'Drawing tools' });
  await rail.getByRole('button', { name: 'Trendline', exact: true }).click();
  await page.mouse.dblclick(box.x + box.width * 0.3, box.y + box.height * 0.3);
  await expect(rail.getByRole('button', { name: 'Trendline', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.2);
  await expect(rail.getByRole('button', { name: 'Select' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => drawings(request, 'INFY')).toHaveLength(1);
  const [line] = await drawings(request, 'INFY');
  expect(line.points[0].date).not.toBe(line.points[1].date);
});

test('D8: a cell the layout opens keeps its own symbol when another cell changes', async ({ page }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await chooseLayout(page, '2x2');
  const charts = page.getByTestId('price-chart');
  await expect(charts).toHaveCount(4);
  const second = (await charts.nth(1).boundingBox())!;
  await page.mouse.click(second.x + second.width / 2, second.y + second.height / 2);
  await page.keyboard.type('INFY');
  await expect(page.getByRole('dialog', { name: 'Search symbols' }).getByText('INFY', { exact: true })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/chart\/INFY$/);
  for (const cell of ['main: TCS', 'c2: INFY', 'c3: TCS', 'c4: TCS']) {
    await expect(page.getByLabel(`Chart ${cell}`)).toBeVisible();
  }
});

test('D9: a synced readout clears after a dialog opened over the hovered chart', async ({ page }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await chooseLayout(page, '2x1');
  const charts = page.getByTestId('price-chart');
  await expect(charts).toHaveCount(2);
  const first = (await charts.nth(0).boundingBox())!;
  await page.mouse.move(first.x + first.width / 2, first.y + first.height / 2);
  await expect(page.getByTestId('crosshair-readout').first()).toBeVisible();
  await page.keyboard.press('i');
  await expect(page.getByRole('dialog', { name: 'Search symbols' })).toBeVisible();
  await page.keyboard.press('Escape');
  await page.mouse.move(5, 5);
  await expect(page.getByTestId('crosshair-readout')).toHaveCount(0);
});
