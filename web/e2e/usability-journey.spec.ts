import type { Page } from '@playwright/test';
import { chooseLayout, expect, resetDocuments, test } from './fixtures';

/**
 * Usability journey (round 4): find a stock, open its chart, run the strategy,
 * read the ranking, run a backtest, read the result and its trades, then
 * restore the saved workspace. Keyboard first, in both themes.
 */

test.beforeEach(() => resetDocuments());

async function chartReady(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ (daily|weekly) bars from the stored NSE series/).first()).toBeVisible();
}

test('journey: find stock → chart → run strategy → ranking → backtest → results → trades → restore workspace', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });

  // Find a stock with the keyboard from the chart.
  await page.goto('/chart/E2E10Y0');
  await chartReady(page);
  await page.getByTestId('price-chart').click({ position: { x: 60, y: 40 } });
  await page.keyboard.press('Escape');
  await page.keyboard.type('E2E10Y3');
  const search = page.getByRole('dialog', { name: 'Search symbols' });
  await search.getByRole('option', { name: /^E2E10Y3/ }).first().waitFor();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/chart\/E2E10Y3$/);
  await chartReady(page);

  // Run the strategy on stored data, then read the ranking.
  await page.goto('/');
  await page.getByRole('button', { name: /^Run screening/ }).first().click();
  await expect(page.locator('tbody tr').first()).toBeVisible();

  // Backtest over the synthetic history.
  await page.goto('/backtest?from=%2F');
  await page.getByLabel('Start Date').fill('2024-01-02');
  await page.getByLabel('End Date').fill('2025-12-30');
  await page.getByRole('button', { name: 'Run Backtest' }).click();
  await expect(page.getByTestId('backtest-provenance')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole('note')).toContainText(/simulation/i);

  // The trades are readable: a symbol that opens its chart, not a bare id.
  const trades = page.getByTestId('backtest-trades');
  await expect(trades.locator('tr').first()).toBeVisible();
  const firstSymbol = trades.locator('tr').first().getByRole('link');
  await expect(firstSymbol).toHaveAttribute('href', /^\/chart\/E2E10Y\d+$/);
  await firstSymbol.click();
  await expect(page).toHaveURL(/\/chart\/E2E10Y\d+$/);
  await chartReady(page);

  // Save and restore the workspace: the layout survives a reload.
  await chooseLayout(page, '2x2');
  await page.reload();
  await chartReady(page);
  await expect(page.locator('div.chart-page')).toHaveAttribute('data-layout', '2x2');
});

for (const scheme of ['light', 'dark'] as const) {
  test(`backtest page keyboard path works in ${scheme} mode`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto('/backtest');
    await page.getByLabel('Initial Capital (INR)').focus();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: 'Run Backtest' })).toBeFocused();
  });
}
