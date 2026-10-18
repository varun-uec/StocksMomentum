import type { APIRequestContext, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

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

test('the details tab explains the symbol in Momentum25 terms', async ({ page }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await page.getByRole('tab', { name: 'Details' }).click();
  const details = page.getByRole('tabpanel', { name: 'Details' });
  await expect(details.getByRole('heading', { name: 'Why it ranks' })).toBeVisible({ timeout: 15_000 });
  await expect(details.getByText('Gate failures')).toBeVisible();
  await details.getByRole('link', { name: 'Full research →' }).click();
  await expect(page).toHaveURL(/\/stock\/TCS$/);
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
  await page.getByRole('button', { name: 'Panel' }).click();
  await expect(page.getByRole('tabpanel', { name: 'Watchlist' })).toBeVisible();
});
