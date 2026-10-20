import type { APIRequestContext, Page } from '@playwright/test';
import { addExtraBar, ageAlerts, chooseLayout, dropExtraBar, expect, openPanelTab, pickTool, resetDocuments, test } from './fixtures';

/**
 * A8b (plan 2026-10-19): the acceptance journeys for steps 5–8. Each one
 * crosses views; together they prove the workstation's context model.
 */

const STRATEGY = 'minervini_trend_template';
const OTHER = 'benchmark_a_pure_momentum';

test.beforeEach(() => resetDocuments());

async function chartReady(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ (daily|weekly) bars from the stored NSE series/).first()).toBeVisible();
}

async function latestRun(request: APIRequestContext, strategy = STRATEGY) {
  const run = await (await request.get(`/api/v1/runs/latest?strategy=${strategy}`)).json();
  const rankings = await (await request.get(`/api/v1/rankings/runs/${run.id}?limit=100&offset=0`)).json();
  return { id: run.id as number, runDate: (run.run_date as string).slice(0, 10), items: rankings.items as { symbol: string; rank: number }[] };
}

const savedDrawings = async (request: APIRequestContext, symbol: string) => {
  const res = await request.get(`/api/v1/drawings/${symbol}`);
  return res.ok() ? ((await res.json()).body?.drawings ?? []) : [];
};

const cell = (page: Page, id: string) => page.getByRole('region', { name: new RegExp(`^Chart ${id}: `) });

async function setCellSymbol(page: Page, id: string, symbol: string) {
  await cell(page, id).getByTestId('price-chart').click({ position: { x: 60, y: 40 } });
  await expect(cell(page, id)).toHaveAttribute('aria-current', 'true');
  await page.keyboard.press('Escape');
  await page.keyboard.type(symbol);
  await page.getByRole('dialog', { name: 'Search symbols' }).getByRole('option', { name: new RegExp(`^${symbol}`) }).first().waitFor();
  await page.keyboard.press('Enter');
  await expect(cell(page, id)).toHaveAccessibleName(`Chart ${id}: ${symbol}`);
}

test('journey 1: screener → chart → ranking → evidence → research → back', async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const run = await latestRun(request);
  const top = run.items.find((i) => i.rank === 1);
  test.skip(!top, 'the fixture run has no qualified symbol');

  await page.goto('/');
  await expect(page.locator('#strategy-selector option:checked')).toHaveText(/^Minervini Trend Template/);
  await page.getByRole('group', { name: 'Filters' }).getByRole('button', { name: 'Qualified', exact: true }).click();
  const rows = page.locator('tbody tr');
  await expect(rows.first().locator('td').first()).toHaveText('1');
  await rows.first().getByRole('button', { name: top!.symbol, exact: true }).click();
  const assessment = page.getByRole('tabpanel', { name: 'Assessment' });
  await expect(assessment.getByTestId('assessment-rank')).toHaveText('#1');
  await expect(assessment.getByTestId('provenance')).toContainText(`run #${run.id}`);

  await assessment.getByRole('button', { name: 'Open in chart' }).click();
  await expect(page).toHaveURL(new RegExp(`/chart/${top!.symbol}$`));
  await chartReady(page);
  await expect(page.getByRole('button', { name: '#1 · Qualified' })).toBeVisible();

  // A drawing to prove the chart comes back as it was.
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await pickTool(page, 'Horizontal line');
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.4);
  await expect.poll(async () => (await savedDrawings(request, top!.symbol)).length).toBe(1);

  await openPanelTab(page, 'Assessment');
  const show = assessment.locator('button', { hasText: /^Show SMA .* on chart$/ }).first();
  if (await show.count()) {
    await show.evaluate((el) => ((el.closest('details') as HTMLDetailsElement).open = true));
    await show.click();
    await expect(page.getByLabel('Study legend')).toContainText('Evidence · temporary');
  }

  await assessment.getByRole('link', { name: 'Full analysis →' }).click();
  await expect(page).toHaveURL(new RegExp(`/stock/${top!.symbol}\\?.*from=`));
  const reason = page.locator('a[href^="#evidence-"]').first();
  const target = (await reason.getAttribute('href'))!.slice(1);
  await reason.click();
  await expect(page.locator(`#${target}`)).toBeFocused();
  await page.getByRole('link', { name: `Back to chart · ${top!.symbol}` }).click();
  await chartReady(page);

  await page.getByRole('region', { name: 'Bottom panel' }).getByRole('link', { name: 'Research' }).click();
  await expect(page.getByRole('navigation', { name: 'Research strategies' }).getByRole('button', { pressed: true })).toHaveCount(1);
  await page.getByRole('link', { name: `Back to chart · ${top!.symbol}` }).first().click();
  await expect(page).toHaveURL(new RegExp(`/chart/${top!.symbol}$`));
  await chartReady(page);
  await expect(page.locator('div.chart-page')).toHaveAttribute('data-layout', '1x1');
  expect(await savedDrawings(request, top!.symbol)).toHaveLength(1);
});

test('journey 2: in a 2×2 grid, "Open in chart" from the screener changes only the active cell; Assessment follows activation', async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const symbols = (await latestRun(request)).items.map((i) => i.symbol);
  const [a, b, c, d, target] = symbols;
  await page.goto(`/chart/${a}`); await chartReady(page);
  await chooseLayout(page, '2x2');
  await setCellSymbol(page, 'c2', b);
  await setCellSymbol(page, 'c3', c);
  await setCellSymbol(page, 'c4', d);
  await cell(page, 'c3').getByTestId('price-chart').click({ position: { x: 60, y: 40 } });

  await page.goto('/');
  await page.locator('tbody tr').getByRole('button', { name: target, exact: true }).click();
  await page.getByRole('tabpanel', { name: 'Assessment' }).getByRole('button', { name: 'Open in chart' }).click();
  await expect(page).toHaveURL(new RegExp(`/chart/${target}$`));
  await expect(cell(page, 'c3')).toHaveAccessibleName(`Chart c3: ${target}`);
  await expect(cell(page, 'main')).toHaveAccessibleName(`Chart main: ${a}`);
  await expect(cell(page, 'c2')).toHaveAccessibleName(`Chart c2: ${b}`);
  await expect(cell(page, 'c4')).toHaveAccessibleName(`Chart c4: ${d}`);

  await openPanelTab(page, 'Assessment');
  const heading = page.getByTestId('assessment-symbol');
  await expect(heading).toHaveText(target);
  await cell(page, 'c2').getByTestId('price-chart').click({ position: { x: 60, y: 40 } });
  await expect(heading).toHaveText(b);
});

test('journey 3: watchlist rank and qualification equal the screener for the same run; a row click moves only the active chart', async ({ page, request }) => {
  const run = await latestRun(request);
  const picks = [run.items.find((i) => i.rank > 0), run.items.find((i) => i.rank === 0)].filter((i): i is { symbol: string; rank: number } => !!i);
  for (const p of picks) await request.post(`/api/v1/watchlist/${p.symbol}`);
  const other = run.items.find((i) => !picks.includes(i))!.symbol;
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/chart/${other}`); await chartReady(page);
  await chooseLayout(page, '2x1');
  await openPanelTab(page, 'Watchlist');
  const panel = page.getByRole('tabpanel', { name: 'Watchlist' });
  await expect(panel.getByTestId('watchlist-run')).toHaveText(new RegExp(`^Ranks: ${STRATEGY} · run #${run.id} · cfg [0-9a-f]{8}$`));
  for (const p of picks) {
    const row = panel.getByRole('listitem').filter({ hasText: p.symbol });
    await expect(row).toContainText(p.rank > 0 ? `#${p.rank}` : '—');
    await expect(row).toContainText(p.rank > 0 ? 'qualified' : 'not qualified');
  }
  const before = await cell(page, 'c2').getAttribute('aria-label');
  await panel.getByRole('button', { name: new RegExp(`^${picks[0].symbol}`) }).click();
  await expect(cell(page, 'main')).toHaveAccessibleName(`Chart main: ${picks[0].symbol}`);
  expect(await cell(page, 'c2').getAttribute('aria-label')).toBe(before);
});

test('journey 4: a stored research strategy cannot be selected; the workstation falls back to a production strategy and names its run', async ({ page, request }) => {
  // Since cecb3e5 the workspace lists production and saved user strategies only. A research
  // strategy left in storage must never supply the run the Assessment and watchlist show.
  // Switching between saved strategies is covered in strategy-integration.spec.ts.
  const main = await latestRun(request);
  const options = await (await request.get('/api/v1/strategies?workspace=true')).json();
  expect(options.map((s: { name: string }) => s.name)).not.toContain(OTHER);
  expect((await request.get(`/api/v1/runs/latest?strategy=${OTHER}`)).status()).toBe(404);
  await request.post('/api/v1/watchlist/TCS');

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/chart/TCS'); await chartReady(page);
  await page.evaluate((name) => localStorage.setItem('momentum25.selectedStrategy', name), OTHER);
  await page.reload(); await chartReady(page);
  await openPanelTab(page, 'Assessment');
  await expect(page.getByTestId('assessment').getByTestId('provenance')).toContainText(`${STRATEGY} · run #${main.id}`);
  await expect(page.getByTestId('assessment').getByTestId('provenance')).not.toContainText(OTHER);
  await openPanelTab(page, 'Watchlist');
  await expect(page.getByTestId('watchlist-run')).toHaveText(new RegExp(`^Ranks: ${STRATEGY} · run #${main.id} · cfg [0-9a-f]{8}$`));
  await page.evaluate(() => localStorage.removeItem('momentum25.selectedStrategy'));
  await request.delete('/api/v1/watchlist/TCS');
});

test('journey 5: a chart whose last bar is newer than the run says the assessment predates it', async ({ page, request }) => {
  const run = await latestRun(request);
  addExtraBar();
  try {
    await page.goto('/chart/TCS'); await chartReady(page);
    await openPanelTab(page, 'Assessment');
    await expect(page.getByTestId('assessment').getByRole('note')).toContainText(`Run #${run.id} is as of ${run.runDate}; TCS's stored bars run to`);
  } finally {
    dropExtraBar();
  }
});

test('journey 6: an alert created from Assessment shows under This symbol, and its triggered row leads back to the chart', async ({ page }) => {
  await page.goto('/chart/TCS'); await chartReady(page);
  await openPanelTab(page, 'Assessment');
  await page.getByRole('tabpanel', { name: 'Assessment' }).getByRole('button', { name: 'Create alert' }).click();
  const alerts = page.getByRole('tabpanel', { name: 'Alerts' });
  const form = alerts.getByRole('form', { name: 'New alert' });
  await form.getByLabel('Condition').selectOption('above');
  await form.getByLabel('Threshold').fill('1');
  await form.getByRole('button', { name: 'Add alert' }).click();
  await expect(alerts.getByRole('button', { name: 'This symbol' })).toHaveAttribute('aria-pressed', 'true');
  await expect(alerts.getByRole('list', { name: 'Alerts' })).toContainText('TCS Close is above 1');

  ageAlerts();
  await form.getByRole('button', { name: 'Check now' }).click();
  await expect(alerts.getByRole('list', { name: 'Alerts' }).getByText(/^Fired on /)).toBeVisible();
  await page.goto('/watchlist');
  await page.getByRole('tablist', { name: 'Panel' }).getByRole('tab', { name: /^Alerts/ }).click();
  await page.getByRole('list', { name: 'Alerts' }).getByRole('link', { name: 'Open chart' }).click();
  await expect(page).toHaveURL(/\/chart\/TCS$/);
});

test('journeys 7 and 8: a historical run keeps its label, its Assessment run, and the watchlist says its ranks are from the latest run', async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const latest = await latestRun(request);
  const bars = (await (await request.get('/api/v1/securities/TCS/ohlcv?interval=1D')).json()).bars as { date: string }[];
  const asOf = bars.at(-6)!.date;
  await request.post(`/api/v1/watchlist/TCS`);

  await page.goto('/historical');
  await page.locator('input[type="date"]').fill(asOf);
  await page.getByRole('button', { name: 'Replay Date' }).click();
  const open = page.getByRole('link', { name: /^Open run #\d+ in the Stock Screener →$/ });
  await expect(open).toBeVisible({ timeout: 20_000 });
  const historicalId = Number(/#(\d+)/.exec((await open.textContent())!)![1]);
  await open.click();
  await expect(page).toHaveURL(new RegExp(`/\\?run=${historicalId}$`));
  const provenance = page.getByTestId('provenance').first();
  await expect(provenance).toContainText(`Historical — as of ${asOf}`);
  await expect(provenance).toContainText(`run #${historicalId}`);
  await expect(provenance).not.toContainText(`run #${latest.id}`);

  await page.locator('tbody tr').first().getByRole('button').first().click();
  const assessment = page.getByRole('tabpanel', { name: 'Assessment' });
  await expect(assessment.getByTestId('provenance')).toContainText(`Historical — as of ${asOf}`);
  await expect(assessment.getByTestId('provenance')).toContainText(`run #${historicalId}`);
  await openPanelTab(page, 'Watchlist');
  await expect(page.getByTestId('watchlist-run')).toHaveText(new RegExp(`^Watchlist ranks: run #${latest.id} · cfg [0-9a-f]{8} \\(latest\\), not this view's run #${historicalId}$`));
});
