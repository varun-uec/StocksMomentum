import { mkdirSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import type { APIRequestContext, Page } from '@playwright/test';
import { chooseLayout, expect, pickTool, resetDocuments, test } from './fixtures';

const OUT = '../audit-evidence/r2/stress-benchmark.json';
const SYMBOLS = Array.from({ length: 16 }, (_, i) => `E2E10Y${i}`);
const BENCH_DRAWINGS = 120;
const INDICATORS = [
  { uid: 'r2-sma', id: 'sma', params: { period: 30 } },
  { uid: 'r2-ema', id: 'ema', params: { period: 34 } },
  { uid: 'r2-bb', id: 'bollinger', params: { period: 20, k: 2 } },
  { uid: 'r2-donchian', id: 'donchian', params: { period: 55 } },
  { uid: 'r2-rsi', id: 'rsi', params: {} },
  { uid: 'r2-macd', id: 'macd', params: {} },
  { uid: 'r2-adx', id: 'adx', params: {} },
];

test.describe.configure({ mode: 'serial' });
test.setTimeout(300_000);

async function configure(request: APIRequestContext, count: number, layout: string) {
  resetDocuments();
  const charts = Object.fromEntries(
    SYMBOLS.slice(0, count).map((symbol, i) => [
      i === 0 ? 'main' : `c${i + 1}`,
      {
        symbol,
        range: 'MAX',
        interval: '1D',
        chart_type: 'candles',
        scale: 'normal',
        mas: [20, 50, 100, 200],
        panes: [],
        indicators: INDICATORS,
        compare: SYMBOLS.filter((s) => s !== symbol).slice(0, 4),
      },
    ]),
  );
  const workspace = await request.put('/api/v1/workspaces/default', {
    data: { active_chart_id: 'main', layout, sync: { symbol: false, interval: false, crosshair: true }, charts },
    headers: { 'If-None-Match': '*' },
  });
  expect(workspace.status()).toBe(201);

  await Promise.all(
    SYMBOLS.slice(0, count).map(async (symbol, symbolIndex) => {
      const drawings = Array.from({ length: BENCH_DRAWINGS }, (_, i) => ({
        id: `r2d${i}`,
        kind: 'hline',
        points: [{ date: `2016-08-${String((i % 28) + 1).padStart(2, '0')}`, price: 100 + symbolIndex + i / 10 }],
        color: '#2563eb',
        width: 1 + (i % 4),
        text: null,
      }));
      const response = await request.put(`/api/v1/drawings/${symbol}`, {
        data: { price_basis: 'traded', drawings },
        headers: { 'If-None-Match': '*' },
      });
      expect(response.status()).toBe(201);
    }),
  );
}

async function heapMb(page: Page): Promise<number> {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('HeapProfiler.collectGarbage');
  await cdp.send('Performance.enable');
  const { metrics } = await cdp.send('Performance.getMetrics');
  await cdp.detach();
  return (metrics.find((m) => m.name === 'JSHeapUsedSize')?.value ?? 0) / 2 ** 20;
}

async function panFps(page: Page): Promise<number> {
  const box = (await page.getByTestId('price-chart').first().boundingBox())!;
  await page.evaluate(() => {
    const w = window as unknown as { r2Frames: number; r2Counting: boolean };
    w.r2Frames = 0;
    w.r2Counting = true;
    const tick = () => {
      if (!w.r2Counting) return;
      w.r2Frames += 1;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  const start = Date.now();
  await page.mouse.move(box.x + box.width * 0.72, box.y + box.height * 0.5);
  await page.mouse.down();
  for (let i = 0; i < 30; i += 1) {
    await page.mouse.move(box.x + box.width * (0.72 - i * 0.01), box.y + box.height * 0.5);
  }
  await page.mouse.up();
  const elapsed = (Date.now() - start) / 1000;
  const frames = await page.evaluate(() => {
    const w = window as unknown as { r2Frames: number; r2Counting: boolean };
    w.r2Counting = false;
    return w.r2Frames;
  });
  return frames / elapsed;
}

const stressResults: Record<string, unknown> = {};

for (const { count, layout } of [
  { count: 1, layout: '1x1' },
  { count: 4, layout: '2x2' },
  { count: 16, layout: '4x4' },
]) {
  test(`R2 stress: ${count} long-history charts with indicators, comparisons and drawings`, async ({ page, request }) => {
    await configure(request, count, layout);
    const started = Date.now();
    await page.goto(`/chart/${SYMBOLS[0]}`);
    await page.waitForFunction(
      (n) => performance.getEntriesByName('wickstreet:chart-painted').length >= n,
      count,
      { timeout: 90_000 },
    );
    await expect(page.getByTestId('price-chart')).toHaveCount(count);
    await page.waitForLoadState('networkidle');
    const readyMs = Date.now() - started;
    const panFrameRate = await panFps(page);
    stressResults[String(count)] = {
      ready_ms: readyMs,
      charts: count,
      bars_per_chart: 2610,
      indicators_per_chart: INDICATORS.length,
      comparison_symbols_per_chart: 4,
      drawings_per_symbol: BENCH_DRAWINGS,
      pan_frame_rate: Math.round(panFrameRate),
      js_heap_mb_after_gc: await heapMb(page),
      canvas_count: await page.locator('canvas').count(),
      long_tasks: await page.evaluate(() =>
        performance.getEntriesByType('longtask').map((entry) => Math.round(entry.duration)),
      ),
    };
  });
}

test('R2 bounded endurance: navigate symbols, change layouts, add and delete drawings', async ({ page, request }) => {
  resetDocuments();
  const initial = await request.put('/api/v1/workspaces/default', {
    data: {
      active_chart_id: 'main',
      layout: '1x1',
      sync: { symbol: false, interval: false, crosshair: true },
      charts: { main: { range: 'MAX', mas: [50, 200], panes: [], indicators: [] } },
    },
    headers: { 'If-None-Match': '*' },
  });
  expect(initial.status()).toBe(201);
  await page.goto(`/chart/${SYMBOLS[0]}`);
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByTestId('price-chart').first()).toHaveAttribute('aria-label', /2610 daily bars/);
  const samples: { symbol: string; heap_mb: number; canvas_count: number }[] = [];

  for (let i = 0; i < 8; i += 1) {
    const symbol = SYMBOLS[i];
    if (i > 0) {
      const search = page.getByLabel('Look up a symbol');
      await search.fill(symbol);
      // Until the new bars arrive, the label below can still describe the previous symbol's chart.
      const bars = page.waitForResponse((r) => r.url().includes(`/securities/${symbol}/ohlcv`));
      await page.keyboard.press('Enter');
      await expect(page).toHaveURL(new RegExp(`/chart/${symbol}$`));
      await bars;
    }
    await expect(page.getByTestId('price-chart').first()).toHaveAttribute('aria-label', /2610 daily bars/);
    const chart = page.getByTestId('price-chart').first();
    await pickTool(page, 'Horizontal line');
    const bounds = (await chart.boundingBox())!;
    await page.mouse.click(bounds.x + bounds.width * 0.42, bounds.y + bounds.height * 0.4);
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/drawings/${symbol}`);
      return response.ok() ? (await response.json()).body?.drawings.length ?? 0 : 0;
    }).toBe(1);
    await page.keyboard.press('Shift+F10');
    await page.getByRole('menu', { name: 'Drawing' }).getByRole('menuitem', { name: 'Delete' }).click();
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/drawings/${symbol}`);
      return response.ok() ? (await response.json()).body?.drawings.length ?? 0 : 0;
    }).toBe(0);

    await chooseLayout(page, '2x2');
    await expect(page.getByTestId('price-chart')).toHaveCount(4);
    await chooseLayout(page, '1x1');
    await expect(page.getByTestId('price-chart')).toHaveCount(1);
    if (i % 2 === 1) {
      samples.push({ symbol, heap_mb: await heapMb(page), canvas_count: await page.locator('canvas').count() });
    }
  }
  stressResults.endurance = samples;
});

test.afterAll(async ({ browser }) => {
  mkdirSync('../audit-evidence/r2', { recursive: true });
  writeFileSync(
    OUT,
    JSON.stringify(
      {
        measured_at: new Date().toISOString(),
        hardware: `${os.cpus()[0]?.model ?? 'unknown CPU'} × ${os.cpus().length}, ${Math.round(os.totalmem() / 2 ** 30)} GB RAM`,
        os: `${os.type()} ${os.release()} ${os.arch()}`,
        browser: `Chromium ${browser.version()} (headless)`,
        viewport: '1280 × 720 (Playwright default)',
        dataset: '16 synthetic 10-year symbols, 2,610 daily bars each, 2016-08-08 through 2026-08-07',
        load_configuration: `${INDICATORS.length} catalogue indicators, four comparison symbols, four moving averages, ${BENCH_DRAWINGS} saved drawings per symbol`,
        results: stressResults,
      },
      null,
      2,
    ),
  );
});
