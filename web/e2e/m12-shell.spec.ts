import type { APIRequestContext, Page } from '@playwright/test';
import { expect, openPanelTab, resetDocuments, test } from './fixtures';

/** M12: the workspace shell around the chart — rail, keys, side panel. */

test.beforeEach(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ daily bars from the stored NSE series/)).toBeVisible();
}

const watchlist = async (request: APIRequestContext): Promise<string[]> =>
  (await (await request.get('/api/v1/watchlist')).json()).symbols;

test('the drawing tools sit in a rail, and Alt shortcuts pick them', async ({ page }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  const rail = page.getByRole('toolbar', { name: 'Drawing tools' });
  await expect(rail).toBeVisible();
  await expect(rail.getByRole('button', { name: 'Select' })).toHaveAttribute('aria-pressed', 'true');

  await page.getByTestId('price-chart').focus();
  await page.keyboard.press('Alt+t');
  await expect(rail.getByRole('button', { name: 'Trendline' })).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('Alt+Shift+r');
  await expect(rail.getByRole('button', { name: 'Rectangle' })).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('Escape');
  await expect(rail.getByRole('button', { name: 'Select' })).toHaveAttribute('aria-pressed', 'true');

  // Pan, zoom and reset run without an error (the fixture fails on any).
  for (const key of ['ArrowLeft', 'ArrowRight', '+', '-', 'Control+ArrowUp', 'Control+ArrowDown', 'Alt+r']) {
    await page.keyboard.press(key);
  }
  await expect(page.getByRole('combobox', { name: 'Symbol or company' })).toBeHidden(); // no key opened search
});

test('? lists the shortcuts', async ({ page }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await page.keyboard.press('?');
  const dialog = page.getByRole('dialog', { name: 'Keyboard shortcuts' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('rowheader', { name: 'Alt+W' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('Alt+W adds the open symbol to the watchlist panel and removes it again', async ({ page, request }) => {
  const symbol = 'ITC';
  if ((await watchlist(request)).includes(symbol)) await request.delete(`/api/v1/watchlist/${symbol}`);
  try {
    await page.goto(`/chart/${symbol}`);
    await ready(page);
    const panel = page.getByRole('tabpanel', { name: 'Watchlist' });
    await expect(panel.getByRole('button', { name: `Add ${symbol}` })).toBeVisible();

    await page.keyboard.press('Alt+w');
    await expect(panel.getByRole('button', { name: `Remove ${symbol}` })).toBeVisible();
    await expect(panel.getByRole('button', { name: new RegExp(`^${symbol}`) })).toHaveAttribute('aria-current', 'true');
    expect(await watchlist(request)).toContain(symbol);

    await page.keyboard.press('Alt+w');
    await expect(panel.getByRole('button', { name: `Add ${symbol}` })).toBeVisible();
    expect(await watchlist(request)).not.toContain(symbol);
  } finally {
    if ((await watchlist(request)).includes(symbol)) await request.delete(`/api/v1/watchlist/${symbol}`);
  }
});

test('the Assessment tab explains the symbol in Momentum25 terms', async ({ page }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await openPanelTab(page, 'Assessment');
  const details = page.getByRole('tabpanel', { name: 'Assessment' });
  await expect(details.getByRole('heading', { name: 'Why it ranks' })).toBeVisible({ timeout: 15_000 });
  await expect(details.getByText('Gate failures')).toBeVisible();
  await details.getByRole('link', { name: 'Full analysis →' }).click();
  await expect(page).toHaveURL(/\/stock\/TCS\?strategy=\w+&from=%2Fchart%2FTCS$/);
});

test('the panel is saved with the workspace: closed stays closed after a reload', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await page.getByRole('button', { name: 'Close panel' }).click();
  await expect(page.getByRole('complementary', { name: 'Side panel' })).toBeHidden();
  await expect
    .poll(async () => {
      const res = await request.get('/api/v1/workspaces/default');
      return res.ok() ? (await res.json()).body.right_panel : 'missing';
    })
    .toBeNull();
  await page.reload();
  await ready(page);
  await expect(page.getByRole('complementary', { name: 'Side panel' })).toBeHidden();
  await openPanelTab(page, 'Watchlist'); // the right icon strip
  await expect(page.getByRole('tabpanel', { name: 'Watchlist' })).toBeVisible();
});

test('the screener opens the selected row in the Assessment panel, with its chart and close line', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  const rows = page.locator('tbody tr');
  await expect(rows.first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('tab', { name: 'Assessment' })).toHaveCount(0); // no row, no context
  const second = (await rows.nth(1).getByRole('button').first().textContent())!.trim();
  await rows.nth(1).getByRole('button', { name: second, exact: true }).click();
  const panel = page.getByRole('tabpanel', { name: 'Assessment' });
  await expect(panel.getByRole('heading', { name: second, level: 3 })).toBeVisible();
  await expect(rows.nth(1)).toHaveAttribute('aria-selected', 'true');
  await expect(panel.getByRole('heading', { name: 'Why it ranks' })).toBeVisible();
  await expect(panel.getByRole('img', { name: `${second}, last year of closes` })).toBeVisible();
  await expect(panel.getByTestId('provenance')).toContainText('run #');
  await panel.getByRole('button', { name: 'Open in chart' }).click();
  await expect(page).toHaveURL(new RegExp(`/chart/${second}$`));
});

test('on a narrow screen the screener row opens the Assessment as a sheet', async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 900 });
  await page.goto('/');
  const firstSymbol = page.locator('tbody tr').first().getByRole('button').first();
  await expect(firstSymbol).toBeVisible({ timeout: 15_000 });
  const symbol = (await firstSymbol.textContent())!.trim();
  await firstSymbol.click();
  await expect(page.getByRole('tabpanel', { name: 'Assessment' }).getByRole('heading', { name: symbol, level: 3 })).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
});

test('the panel follows the route: an overlay off the chart, Details only with a context symbol', async ({ page }) => {
  await page.goto('/market');
  const strip = page.getByRole('tablist', { name: 'Panel' });
  await expect(strip.getByRole('tab')).toHaveText(['', '']);
  await expect(strip.getByRole('tab', { name: 'Assessment' })).toHaveCount(0);
  await strip.getByRole('tab', { name: 'Alerts' }).click();
  const panel = page.getByRole('complementary', { name: 'Side panel' });
  await expect(panel.getByText('Open a chart or a symbol page to create an alert.')).toBeVisible();
  await expect(panel.getByRole('form', { name: 'New alert' })).toHaveCount(0);
  await strip.getByRole('tab', { name: 'Alerts' }).click(); // the open tab collapses the panel
  await expect(panel).toBeHidden();

  await page.goto('/stock/TCS');
  await expect(strip.getByRole('tab', { name: 'Assessment' })).toHaveCount(0); // the page is the assessment
  await expect(panel).toBeHidden(); // off the chart the panel starts closed on each visit
  await strip.getByRole('tab', { name: 'Alerts' }).click();
  await expect(panel.getByRole('form', { name: 'New alert' })).toContainText('New alert on TCS');
});
