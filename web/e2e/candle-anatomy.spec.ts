import type { APIRequestContext, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/**
 * Each rendered candle spans its own bar: the wick runs from the bar's high to
 * its low and the body from its open to its close, on one linear price scale.
 * The test reads the price pane's canvas pixels, so it checks what the user
 * sees. It covers adjusted bars, replay and every interval. E2ECANDLE is the
 * varied chart fixture in db.py; a renderer that drew fixed wick lengths or
 * inferred a high or low would leave residuals of many pixels.
 */

const SYMBOL = 'E2ECANDLE';
const SPLIT = '2026-06-22'; // 1:2, so every earlier bar has factor 0.5
const UP = [0x14, 0x7d, 0x65];
const DOWN = [0xc9, 0x38, 0x50];

type Bar = { date: string; open: string; high: string; low: string; close: string };
type Run = { x: number; up: boolean; top: number; bottom: number };
type Candle = { wick: Run; body: Run | null };

test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
test.beforeEach(async ({ page }) => {
  resetDocuments();
  await page.addInitScript(() => localStorage.setItem('m25-theme', 'light'));
});

async function series(request: APIRequestContext, query: string): Promise<Bar[]> {
  return (await (await request.get(`/api/v1/securities/${SYMBOL}/ohlcv?${query}`)).json()).bars;
}

async function openChart(page: Page): Promise<void> {
  await page.goto(`/chart/${SYMBOL}`);
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  // Moving averages share the candles' pixels; this test reads candles only.
  for (const name of ['Remove MA50', 'Remove MA200']) await page.getByRole('button', { name }).click();
}

async function showRange(page: Page, range: string, barWord: string, last: string): Promise<void> {
  await page.getByRole('button', { name: range, exact: true }).click();
  const chart = page.getByTestId('price-chart');
  await expect(chart).toHaveAttribute('aria-label', new RegExp(` ${barWord} bars from .* to ${last}\\.`));
  await expect(chart).toHaveAttribute('data-visible-to', last);
  await page.mouse.move(0, 0);
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
}

/**
 * The longest candle-coloured vertical run in every column of the price pane's
 * canvas, and the row of the dotted last-price line. That line is drawn over the
 * candles, so a run passes through its row only where both neighbours are lit.
 */
async function readRuns(page: Page): Promise<{ runs: Run[]; lineY: number }> {
  return page.getByTestId('price-chart').evaluate((el, [up, down]) => {
    const canvases = [...el.querySelectorAll('canvas')];
    const area = (c: HTMLCanvasElement) => c.width * c.height;
    const pane = canvases.find((c) => area(c) === Math.max(...canvases.map(area)))!;
    const { width, height } = pane;
    const px = pane.getContext('2d')!.getImageData(0, 0, width, height).data;
    const is = (x: number, y: number, rgb: number[]) => rgb.every((v, k) => Math.abs(px[(y * width + x) * 4 + k] - v) <= 8);
    const on = (x: number, y: number) => y >= 0 && y < height && (is(x, y, up) || is(x, y, down));
    const dots = new Map<number, number>();
    for (let x = 0; x < width; x++) {
      for (let y = 0; y < height; y++) if (on(x, y) && !on(x, y - 1) && !on(x, y + 1)) dots.set(y, (dots.get(y) ?? 0) + 1);
    }
    const [lineY, count] = [...dots].sort((a, b) => b[1] - a[1])[0] ?? [-10, 0];
    const lit = (x: number, y: number) => (y === lineY ? on(x, y - 1) && on(x, y + 1) : on(x, y));
    const runs: Run[] = [];
    for (let x = 0; x < width; x++) {
      let best: { top: number; bottom: number } | null = null;
      let start = -1;
      for (let y = 0; y <= height; y++) {
        const isLit = y < height && lit(x, y);
        if (isLit && start < 0) start = y;
        if (!isLit && start >= 0) {
          if (!best || y - 1 - start > best.bottom - best.top) best = { top: start, bottom: y - 1 };
          start = -1;
        }
      }
      if (!best || best.bottom === best.top) continue;
      let ups = 0;
      for (let y = best.top; y <= best.bottom; y++) if (y !== lineY && is(x, y, up)) ups++;
      runs.push({ x, up: 2 * ups > best.bottom - best.top + 1, ...best });
    }
    return { runs, lineY: count >= 10 ? lineY : -10 };
  }, [UP, DOWN]);
}

/** Group adjacent same-coloured columns into candles: the tallest column is the wick, the most common other one the body. */
function toCandles(runs: Run[]): Candle[] {
  const groups: Run[][] = [];
  for (const run of runs) {
    const previous = groups.at(-1)?.at(-1);
    if (previous && previous.x === run.x - 1 && previous.up === run.up) groups.at(-1)!.push(run);
    else groups.push([run]);
  }
  // A candle cut by the pane's left edge has lost its wick column.
  return groups.filter((group) => group[0].x > 0).map((group) => {
    const wick = group.reduce((a, b) => (b.bottom - b.top > a.bottom - a.top ? b : a));
    const counts = new Map<string, { run: Run; n: number }>();
    for (const run of group.filter((r) => r !== wick)) {
      const key = `${run.top}:${run.bottom}`;
      counts.set(key, { run, n: (counts.get(key)?.n ?? 0) + 1 });
    }
    const body = [...counts.values()].sort((a, b) => b.n - a.n)[0]?.run ?? null;
    return { wick, body };
  });
}

/**
 * Match the candles to the visible bars from the right (the leftmost bar can sit
 * half outside the pane), fit y = a + b·price over every high, low and body
 * edge, and require every edge within 1 px of the fit.
 */
async function expectCandlesMatch(page: Page, bars: Bar[]): Promise<void> {
  const chart = page.getByTestId('price-chart');
  const from = (await chart.getAttribute('data-visible-from'))!;
  const to = (await chart.getAttribute('data-visible-to'))!;
  const visible = bars.filter((b) => b.date >= from && b.date <= to);
  const { runs, lineY } = await readRuns(page);
  const candles = toCandles(runs);
  expect(candles.length, `candles drawn for ${visible.length} visible bars`).toBeGreaterThanOrEqual(visible.length - 1);
  expect(candles.length).toBeLessThanOrEqual(visible.length);
  const spacing = candles.slice(1).map((c, i) => c.wick.x - candles[i].wick.x);
  expect(Math.max(...spacing) - Math.min(...spacing), 'even bar spacing: no candle missed or merged').toBeLessThanOrEqual(1);

  // An edge beside the last-price line could be the line's dot, so it proves nothing either way.
  const points: [number, number][] = [];
  const edge = (price: number, y: number) => { if (Math.abs(y - lineY) > 1) points.push([price, y]); };
  candles.forEach((candle, i) => {
    const bar = visible[visible.length - candles.length + i];
    const [open, high, low, close] = [bar.open, bar.high, bar.low, bar.close].map(Number);
    expect(candle.wick.up, `${bar.date} colour`).toBe(close >= open);
    edge(high, candle.wick.top);
    edge(low, candle.wick.bottom);
    if (candle.body) { edge(Math.max(open, close), candle.body.top); edge(Math.min(open, close), candle.body.bottom); }
  });
  const n = points.length;
  const mp = points.reduce((s, [p]) => s + p, 0) / n;
  const my = points.reduce((s, [, y]) => s + y, 0) / n;
  const b = points.reduce((s, [p, y]) => s + (p - mp) * (y - my), 0) / points.reduce((s, [p]) => s + (p - mp) ** 2, 0);
  const a = my - b * mp;
  const worst = Math.max(...points.map(([p, y]) => Math.abs(a + b * p - y)));
  expect(b, 'a higher price draws higher').toBeLessThan(0);
  expect(worst, 'largest gap between a drawn edge and its price, in pixels').toBeLessThanOrEqual(1);

  // The fixture is varied, so the test can tell a true wick from a fixed one.
  const spans = candles.map((c) => c.wick.bottom - c.wick.top);
  expect(Math.max(...spans)).toBeGreaterThanOrEqual(4 * Math.min(...spans));
}

/** ISO week (Monday's date) or calendar month of a session. */
function periodOf(date: string, interval: '1W' | '1M'): string {
  if (interval === '1M') return date.slice(0, 7);
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
}

test('daily candles match their adjusted bars on both sides of a split', async ({ page, request }) => {
  const adjusted = await series(request, 'interval=1D');
  const raw = await series(request, `interval=1D&as_of=2026-06-19`);
  const before = adjusted.filter((b) => b.date < SPLIT);
  // Before the split the chart shows the raw print times 0.5; the session before it is as it was then.
  for (const [i, bar] of raw.entries()) {
    for (const key of ['open', 'high', 'low', 'close'] as const) expect(Number(bar[key])).toBeCloseTo(2 * Number(before[i][key]), 4);
  }
  await openChart(page);
  await showRange(page, '3M', 'daily', adjusted.at(-1)!.date);
  expect((await page.getByTestId('price-chart').getAttribute('data-visible-from'))! < SPLIT, 'the view spans the split').toBe(true);
  await expectCandlesMatch(page, adjusted);
});

for (const [interval, name, range] of [['1W', 'Weekly bars', '1Y'], ['1M', 'Monthly bars', 'MAX']] as const) {
  test(`${name.toLowerCase()} match their aggregated daily highs and lows`, async ({ page, request }) => {
    const daily = await series(request, 'interval=1D');
    const periods = await series(request, `interval=${interval}`);
    for (const bar of periods) {
      const days = daily.filter((d) => periodOf(d.date, interval) === periodOf(bar.date, interval));
      expect(Number(bar.high), bar.date).toBe(Math.max(...days.map((d) => Number(d.high))));
      expect(Number(bar.low), bar.date).toBe(Math.min(...days.map((d) => Number(d.low))));
      expect([bar.open, bar.close]).toEqual([days[0].open, days.at(-1)!.close]);
    }
    await openChart(page);
    await page.getByRole('button', { name }).click();
    await showRange(page, range, interval === '1W' ? 'weekly' : 'monthly', periods.at(-1)!.date);
    await expectCandlesMatch(page, periods);
  });
}

test('replay candles match the series as it stood on the replay date, before the split', async ({ page, request }) => {
  const date = '2026-06-12';
  const asOf = await series(request, `interval=1D&as_of=${date}`);
  expect(asOf.at(-1)!.date).toBe(date);
  await openChart(page);
  await page.getByRole('button', { name: 'Replay', exact: true }).click();
  await page.getByRole('toolbar', { name: 'Bar replay' }).getByLabel('Replay date').fill(date);
  await showRange(page, '3M', 'daily', date);
  await expectCandlesMatch(page, asOf);
});
