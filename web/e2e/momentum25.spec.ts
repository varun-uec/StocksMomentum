import type { APIRequestContext, Page } from '@playwright/test';
import { chooseLayout, expect, openPanelTab, resetDocuments, test } from './fixtures';

/** A5 (plan 2026-10-19): Momentum25 in the workstation — Assessment, layers, watchlist, alerts, return paths. */

const STRATEGY = 'minervini_trend_template';

test.beforeEach(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ daily bars from the stored NSE series/)).toBeVisible();
}

/** The fixture run and its rows, straight from the API the views use. */
async function run(request: APIRequestContext) {
  const latest = await (await request.get(`/api/v1/runs/latest?strategy=${STRATEGY}`)).json();
  const rankings = await (await request.get(`/api/v1/rankings/runs/${latest.id}?limit=100&offset=0`)).json();
  const items = rankings.items as { symbol: string; rank: number }[];
  return { id: latest.id as number, items, qualified: items.find((i) => i.rank > 0), unqualified: items.find((i) => i.rank === 0) };
}

test('Assessment shows the rank and the run it comes from, and each criterion opens to its evidence', async ({ page, request }) => {
  const { id, qualified, items } = await run(request);
  const symbol = (qualified ?? items[0]).symbol;
  await page.goto(`/chart/${symbol}`); await ready(page);
  await openPanelTab(page, 'Assessment');
  const panel = page.getByRole('tabpanel', { name: 'Assessment' });
  await expect(panel.getByTestId('provenance')).toContainText(`run #${id}`);
  await expect(panel.getByTestId('assessment-rank')).toHaveText(qualified ? `#${qualified.rank}` : 'Not ranked');
  const criterion = panel.getByLabel('Criteria').locator('details').first();
  await criterion.locator('summary').click();
  await expect(criterion.getByText('Threshold')).toBeVisible();
});

test('Assessment never shows the previous symbol while the next one loads', async ({ page, request }) => {
  const { items } = await run(request);
  const [first, second] = items.map((i) => i.symbol);
  await page.goto(`/chart/${first}`); await ready(page);
  await openPanelTab(page, 'Assessment');
  const heading = page.getByTestId('assessment-symbol');
  await expect(heading).toHaveText(first);
  await page.route('**/api/v1/stocks/**', async (route) => { await new Promise((r) => setTimeout(r, 400)); await route.continue(); });
  await page.goto(`/chart/${second}`);
  await expect(heading).toHaveText(second);
  await expect(page.getByTestId('assessment')).not.toContainText(`${first} `);
});

test('Show on chart adds a temporary layer: no document write, and a reload clears it', async ({ page, request }) => {
  const { items } = await run(request);
  await page.goto(`/chart/${items[0].symbol}`); await ready(page);
  await openPanelTab(page, 'Assessment');
  const panel = page.getByRole('tabpanel', { name: 'Assessment' });
  // Inside a closed criterion, so not yet in the accessibility tree.
  const show = panel.locator('button', { hasText: /^Show SMA .* on chart$/ }).first();
  await show.waitFor({ state: 'attached' });
  const label = (await show.textContent())!.replace(/^Show /, '').replace(/ on chart$/, '');
  await expect(page.getByTestId('save-state')).toContainText('Saved');
  const puts: string[] = [];
  page.on('request', (r) => { if (r.method() === 'PUT') puts.push(r.url()); });
  await show.evaluate((el) => (el.closest('details') as HTMLDetailsElement).open = true);
  await show.click();
  const legend = page.getByLabel('Study legend');
  await expect(legend).toContainText(`Evidence · temporary: ${label}`);
  await expect(panel.getByRole('button', { name: `Hide ${label} from chart` }).first()).toHaveAttribute('aria-pressed', 'true');
  await legend.getByRole('button', { name: `Remove evidence ${label}` }).click();
  await expect(legend).not.toContainText('Evidence · temporary');
  await panel.getByRole('button', { name: `Show ${label} on chart` }).first().click();
  await expect(legend).toContainText('Evidence · temporary');
  await page.waitForLoadState('networkidle');
  expect(puts).toEqual([]);
  await expect(page.getByTestId('save-state')).toContainText('Saved');
  await page.reload(); await ready(page);
  await expect(page.getByLabel('Study legend')).not.toContainText('Evidence · temporary');
});

test('the legend chip names the rank in the run and opens Assessment', async ({ page, request }) => {
  const { qualified, unqualified } = await run(request);
  const target = qualified ?? unqualified!;
  await page.goto(`/chart/${target.symbol}`); await ready(page);
  const chip = page.getByRole('button', { name: qualified ? `#${qualified.rank} · Qualified` : 'Not qualified' });
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page.getByRole('tab', { name: 'Assessment' })).toHaveAttribute('aria-selected', 'true');
});

test('watchlist rank and qualification match the screener for the same run', async ({ page, request }) => {
  const { id, items } = await run(request);
  const picks = [items.find((i) => i.rank > 0), items.find((i) => i.rank === 0)].filter((i): i is { symbol: string; rank: number } => !!i);
  for (const p of picks) await request.post(`/api/v1/watchlist/${p.symbol}`);
  await page.goto(`/chart/${picks[0].symbol}`); await ready(page);
  await openPanelTab(page, 'Watchlist');
  const panel = page.getByRole('tabpanel', { name: 'Watchlist' });
  await expect(panel.getByTestId('watchlist-run')).toHaveText(`Ranks: ${STRATEGY} · run #${id}`);
  for (const p of picks) {
    const row = panel.getByRole('listitem').filter({ hasText: p.symbol });
    await expect(row).toContainText(p.rank > 0 ? `#${p.rank}` : '—');
    await expect(row).toContainText(p.rank > 0 ? 'qualified' : 'not qualified');
  }
});

test('alerts open on this symbol; All lists the others', async ({ page, request }) => {
  for (const symbol of ['TCS', 'INFY']) {
    expect((await request.post('/api/v1/alerts', { data: { symbol, source: 'close', condition: 'above', threshold: '1' } })).status()).toBe(201);
  }
  await page.goto('/chart/TCS'); await ready(page);
  await openPanelTab(page, /^Alerts/);
  const list = page.getByRole('list', { name: 'Alerts' });
  await expect(page.getByRole('button', { name: 'This symbol' })).toHaveAttribute('aria-pressed', 'true');
  await expect(list.getByRole('listitem')).toHaveCount(1);
  await expect(list).toContainText('TCS Close is above 1');
  await page.getByRole('button', { name: 'All', exact: true }).click();
  await expect(list.getByRole('listitem')).toHaveCount(2);
  await expect(list).toContainText('INFY Close is above 1');
});

test('Full analysis carries the way back to the chart; a foreign return path is ignored', async ({ page }) => {
  await page.goto('/chart/TCS'); await ready(page);
  await openPanelTab(page, 'Assessment');
  await page.getByRole('tabpanel', { name: 'Assessment' }).getByRole('link', { name: 'Full analysis →' }).click();
  await expect(page).toHaveURL(/\/stock\/TCS\?.*from=%2Fchart%2FTCS/);
  await page.getByRole('link', { name: 'Back to chart · TCS' }).click();
  await expect(page).toHaveURL(/\/chart\/TCS$/);

  await page.goto('/stock/TCS?from=%2F%2Fevil.example%2Fx');
  await expect(page.getByRole('link', { name: 'Open in chart' })).toBeVisible();
  await expect(page.getByRole('link', { name: /^Back/ })).toHaveCount(0);
});

test('the bottom panel screener loads a row into the active chart only, and stays open after a reload', async ({ page, request }) => {
  const { items } = await run(request);
  await page.goto('/chart/TCS'); await ready(page);
  await chooseLayout(page, '2x2');
  const cell = (id: string) => page.getByRole('region', { name: new RegExp(`^Chart ${id}: `) });
  await cell('c2').getByTestId('price-chart').click({ position: { x: 60, y: 40 } });
  await expect(cell('c2')).toHaveAttribute('aria-current', 'true');
  const before = { main: await cell('main').getAttribute('aria-label'), c3: await cell('c3').getAttribute('aria-label') };
  const bottom = page.getByRole('region', { name: 'Bottom panel' });
  await bottom.getByRole('button', { name: 'Stock Screener' }).click();
  const target = items.find((i) => i.symbol !== 'TCS')!.symbol;
  await bottom.getByRole('region', { name: 'Ranked stock results' }).getByRole('button', { name: target, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/chart/${target}$`));
  await expect(cell('c2')).toHaveAccessibleName(`Chart c2: ${target}`);
  expect(await cell('main').getAttribute('aria-label')).toBe(before.main);
  expect(await cell('c3').getAttribute('aria-label')).toBe(before.c3);

  await page.reload();
  await expect(bottom.getByRole('button', { name: 'Stock Screener' })).toHaveAttribute('aria-expanded', 'true');
  await bottom.getByRole('button', { name: 'Maximise bottom panel' }).click();
  await expect(bottom).toHaveAttribute('data-state', 'max');
  await bottom.getByRole('button', { name: 'Collapse bottom panel' }).click();
  await expect(bottom.getByRole('region', { name: 'Ranked stock results' })).toHaveCount(0);
  await expect(bottom.getByRole('link', { name: 'Research' })).toHaveAttribute('href', `/strategies?from=%2Fchart%2F${target}`);
});

test('symbol pages share one header: tabs, the chart hand-off, and criterion links that focus their evidence', async ({ page }) => {
  await page.goto('/stock/TCS');
  const views = page.getByRole('navigation', { name: 'Symbol views' });
  await expect(views.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByText(/EOD as of \d{4}-\d{2}-\d{2}/)).toBeVisible();
  const reason = page.locator('a[href^="#evidence-"]').first();
  const target = (await reason.getAttribute('href'))!.slice(1);
  await reason.click();
  await expect(page.locator(`#${target}`)).toBeFocused();
  await views.getByRole('link', { name: 'Elliott Wave' }).click();
  await expect(page).toHaveURL(/\/stock\/TCS\/elliott-wave/);
  await expect(views.getByRole('link', { name: 'Elliott Wave' })).toHaveAttribute('aria-current', 'page');
  await views.getByRole('link', { name: 'Open in chart' }).click();
  await expect(page).toHaveURL(/\/chart\/TCS$/);
});

test('the Research workspace keeps one tab row, the selected strategy and the way back to the chart', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/backtest?from=%2Fchart%2FTCS');
  const tabs = page.getByRole('navigation', { name: 'Research', exact: true });
  await expect(tabs.getByRole('link', { name: 'Backtest' })).toHaveAttribute('aria-current', 'page');
  const strategies = page.getByRole('navigation', { name: 'Research strategies' });
  const pick = strategies.getByRole('button').last();
  const chosen = (await pick.textContent())!.trim();
  await pick.click();
  await expect(pick).toHaveAttribute('aria-pressed', 'true');
  await tabs.getByRole('link', { name: 'Validation' }).click();
  await expect(page).toHaveURL(/\/validation\?from=%2Fchart%2FTCS$/);
  await expect(strategies.getByRole('button', { name: chosen })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('link', { name: 'Back to chart · TCS' }).first().click();
  await expect(page).toHaveURL(/\/chart\/TCS$/);
});
