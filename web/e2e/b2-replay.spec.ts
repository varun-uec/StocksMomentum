import type { APIRequestContext, Page } from '@playwright/test';
import { addExtraBar, dropExtraBar, expect, openPanelTab, pickTool, resetDocuments, test } from './fixtures';

/** B2 (plan 2026-10-19): EOD bar replay never shows a bar, value, drawing, alert or run from after its date. */

const STRATEGY = 'minervini_trend_template';

test.beforeEach(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ daily bars from the stored NSE series/)).toBeVisible();
}

async function sessions(request: APIRequestContext, symbol: string): Promise<string[]> {
  return (await (await request.get(`/api/v1/securities/${symbol}/ohlcv`)).json()).bars.map((b: { date: string }) => b.date);
}

const chart = (page: Page) => page.getByTestId('price-chart');
const bar = (page: Page) => page.getByRole('toolbar', { name: 'Bar replay' });
const replayDate = async (page: Page) => bar(page).getByLabel('Replay date').inputValue();

/** The chart's own label names its bar count and last date: nothing after the replay date may show. */
async function expectBarsTo(page: Page, all: string[], date: string): Promise<void> {
  const shown = all.filter((d) => d <= date);
  await expect(chart(page)).toHaveAttribute('aria-label', new RegExp(`^Price chart, ${shown.length} daily bars from ${all[0]} to ${date}\\.`));
}

test('replay cuts the chart, panes and compare line at its date; it steps, plays, and exit restores the viewport', async ({ page, request }) => {
  const tcs = await sessions(request, 'TCS');
  await page.goto('/chart/TCS'); await ready(page);
  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  await page.getByRole('dialog', { name: 'Compare with' }).getByRole('combobox').fill('INFY');
  await expect(page.getByRole('dialog', { name: 'Compare with' }).getByRole('option', { name: /INFY/ }).first()).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page.getByText(/^INFY [+-]\d+\.\d{2}%$/)).toBeVisible();
  const before = { from: await chart(page).getAttribute('data-visible-from'), to: await chart(page).getAttribute('data-visible-to') };
  expect(before.to).toBeTruthy();

  const replayed: string[] = [];
  page.on('request', (r) => { if (/\/ohlcv|\/indicators\/series/.test(r.url())) replayed.push(r.url()); });
  await page.getByRole('button', { name: 'Replay', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Replay', exact: true })).toHaveAttribute('aria-pressed', 'true');
  const start = await replayDate(page);
  expect(start < tcs.at(-1)!).toBe(true);
  await expectBarsTo(page, tcs, start);
  await expect.poll(() => chart(page).getAttribute('data-visible-to')).not.toBe(before.to);
  expect(await chart(page).getAttribute('data-visible-to')).toBeTruthy();
  // The compare line and the panes come from the server as of the replay date.
  await expect.poll(() => replayed.some((u) => u.includes('/INFY/ohlcv') && u.includes(`as_of=${start}`))).toBe(true);
  expect(replayed.filter((u) => u.includes('/INFY/ohlcv')).every((u) => u.includes('as_of='))).toBe(true);
  expect(replayed.filter((u) => u.includes('/indicators/series')).every((u) => u.includes('as_of='))).toBe(true);
  // Alerts are paused: no toolbar alert, and the panel says why.
  await expect(page.getByRole('button', { name: 'Alert', exact: true })).toBeDisabled();
  await openPanelTab(page, /^Alerts/);
  await expect(page.getByRole('tabpanel', { name: /Alerts/ })).toContainText('Alerts are paused during bar replay');

  await bar(page).getByRole('button', { name: 'Step forward' }).click();
  const stepped = tcs[tcs.indexOf(start) + 1];
  await expect(bar(page).getByLabel('Replay date')).toHaveValue(stepped);
  await expectBarsTo(page, tcs, stepped);
  await page.getByTestId('price-chart').focus();
  await page.keyboard.press('Shift+ArrowRight');
  await expect(bar(page).getByLabel('Replay date')).toHaveValue(tcs[tcs.indexOf(start) + 2]);

  await bar(page).getByRole('button', { name: '10×' }).click();
  await bar(page).getByRole('button', { name: 'Play', exact: true }).click();
  await expect.poll(async () => tcs.indexOf(await replayDate(page)), { timeout: 15_000 }).toBeGreaterThan(tcs.indexOf(start) + 5);
  await bar(page).getByRole('button', { name: 'Pause', exact: true }).click();
  const paused = await replayDate(page);
  await expectBarsTo(page, tcs, paused);

  // A weekly bar in replay holds only its sessions up to the replay date.
  await page.getByRole('button', { name: 'Weekly bars' }).click();
  await expect(chart(page)).toHaveAttribute('aria-label', new RegExp(`weekly bars from .* to ${paused}\\.`));
  const weekly = (await (await request.get(`/api/v1/securities/TCS/ohlcv?interval=1W&as_of=${paused}`)).json()).bars;
  expect(weekly.at(-1).date).toBe(paused);
  await page.getByRole('button', { name: 'Daily bars' }).click();
  await expectBarsTo(page, tcs, paused);

  await bar(page).getByRole('button', { name: 'Exit replay' }).click();
  await expect(bar(page)).toHaveCount(0);
  await expectBarsTo(page, tcs, tcs.at(-1)!);
  await expect.poll(() => chart(page).getAttribute('data-visible-to')).toBe(before.to);
  expect(await chart(page).getAttribute('data-visible-from')).toBe(before.from);
});

test('replay hides drawings anchored after its date, keeps them when another is drawn, and shows them on exit', async ({ page, request }) => {
  const tcs = await sessions(request, 'TCS');
  const early = tcs[tcs.length - 120];
  const late = tcs.at(-1)!;
  const saved = (id: string, kind: string, dates: string[]) => ({ id, kind, color: '#6366f1', points: dates.map((date) => ({ date, price: 100 })) });
  expect((await request.put('/api/v1/drawings/TCS', {
    headers: { 'If-None-Match': '*' },
    data: { drawings: [saved('early', 'hline', [early]), saved('late', 'trendline', [early, late])] },
  })).status()).toBe(201);
  await page.goto('/chart/TCS'); await ready(page);
  await openPanelTab(page, 'Object tree');
  const tree = page.getByRole('tabpanel', { name: 'Object tree' });
  await expect(tree.getByRole('button', { name: /^Hide / })).toHaveCount(2);

  await page.getByRole('button', { name: 'Replay', exact: true }).click();
  await expect(tree.getByRole('button', { name: /^Hide / })).toHaveCount(1);
  await expect(tree.getByRole('button', { name: 'Hide Horizontal line', exact: true })).toBeVisible();

  // A drawing made in replay saves normally; the hidden one is kept, unchanged.
  await pickTool(page, 'Horizontal line');
  const box = (await chart(page).boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await expect(tree.getByRole('button', { name: /^Hide / })).toHaveCount(2);
  await expect.poll(async () => ((await (await request.get('/api/v1/drawings/TCS')).json()).body?.drawings.length ?? 0)).toBe(3);
  const stored = (await (await request.get('/api/v1/drawings/TCS')).json()).body.drawings;
  expect(stored).toHaveLength(3);
  expect(stored.find((d: { id: string }) => d.id === 'late').points.map((p: { date: string }) => p.date)).toEqual([early, late]);

  await bar(page).getByRole('button', { name: 'Exit replay' }).click();
  await expect(tree.getByRole('button', { name: /^Hide / })).toHaveCount(3);
});

test('Assessment, legend chip, watchlist and bottom screener show only a run dated on or before the replay date', async ({ page, request }) => {
  const latest = await (await request.get(`/api/v1/runs/latest?strategy=${STRATEGY}`)).json();
  const runDate = latest.run_date.slice(0, 10) as string;
  addExtraBar(); // TCS gets a session after the run, so replay can stop on the run's own date.
  try {
    expect((await request.post('/api/v1/watchlist/TCS')).ok()).toBe(true);
    await page.goto('/chart/TCS'); await ready(page);
    await page.getByRole('button', { name: 'Replay', exact: true }).click();
    const start = await replayDate(page);
    expect(start < runDate).toBe(true);

    await openPanelTab(page, 'Assessment');
    const assessment = page.getByRole('tabpanel', { name: 'Assessment' });
    await expect(assessment.getByTestId('assessment-replay')).toHaveText(`Not available in replay: no ${STRATEGY} run is dated on or before ${start}.`);
    await expect(assessment.getByRole('link', { name: 'Full analysis →' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /· Qualified$|^Not qualified$/ })).toHaveCount(0);

    await openPanelTab(page, 'Watchlist');
    const watchlist = page.getByRole('tabpanel', { name: 'Watchlist' });
    await expect(watchlist.getByTestId('watchlist-run')).toContainText(`Bar replay to ${start}: prices and ranks are hidden`);
    await expect(watchlist.getByRole('listitem').filter({ hasText: 'TCS' })).not.toContainText(/qualified|#\d/);

    const bottom = page.getByRole('region', { name: 'Bottom panel' });
    await bottom.getByRole('button', { name: 'Stock Screener' }).click();
    await expect(bottom).toContainText(`No ${STRATEGY} run is dated on or before ${start}.`);

    await bar(page).getByLabel('Replay date').fill(runDate);
    await expect(bar(page).getByLabel('Replay date')).toHaveValue(runDate);
    await openPanelTab(page, 'Assessment');
    await expect(assessment.getByTestId('provenance')).toContainText(`Replay — newest run on or before ${runDate}`);
    await expect(assessment.getByTestId('provenance')).toContainText(`run #${latest.id}`);
    await expect(bottom.getByTestId('provenance')).toContainText(`run #${latest.id}`);
    await expect(bottom.getByTestId('screen-count')).toContainText('Matches:');
  } finally {
    dropExtraBar();
  }
});
