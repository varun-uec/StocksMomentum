import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import type { Browser, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/**
 * M13 benchmark: 1, 4 and 16 charts, each holding a different symbol's 10
 * years of daily bars (MAX range), crosshair sync on. The NFR-11 method: at
 * least 30 runs per case, the environment recorded. It reports; it does not
 * redefine NFR-11, except that the 1-chart case must still meet it.
 *
 * - Open: navigation start → the N-th `wickstreet:chart-painted` mark (each
 *   chart marks its first frame with bars). Warm = same context; cold = a new
 *   context per run.
 * - Pan: a 0.5 s drag across the active chart, frames counted with
 *   requestAnimationFrame. With crosshair sync on, every chart redraws.
 * - Memory: the JS heap after a forced garbage collection, once the charts are
 *   open (CDP). Canvas backing stores are not in the JS heap.
 *
 * Opt-in, because it takes minutes: `M13_BENCH=1 npx playwright test e2e/m13-bench.spec.ts`.
 */

const RUNS = 30;
const LAYOUTS = [
  { charts: 1, layout: '1x1' },
  { charts: 4, layout: '2x2' },
  { charts: 16, layout: '4x4' },
] as const;
const SYMBOLS = Array.from({ length: 16 }, (_, i) => `E2E10Y${i}`);
const slotId = (i: number) => (i === 0 ? 'main' : `c${i + 1}`);

test.skip(!process.env.M13_BENCH, 'set M13_BENCH=1 to run the M13 benchmark');
test.describe.configure({ mode: 'serial' });
test.setTimeout(600_000);

function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(p * sorted.length) - 1)];
}
const summary = (values: number[]) => ({
  runs: values.length,
  p50: Math.round(percentile(values, 0.5)),
  p95: Math.round(percentile(values, 0.95)),
  max: Math.round(Math.max(...values)),
});

async function openTime(page: Page, n: number): Promise<number> {
  await page.goto(`/chart/${SYMBOLS[0]}`);
  await page.waitForFunction((count) => performance.getEntriesByName('wickstreet:chart-painted').length >= count, n, {
    timeout: 60_000,
  });
  const at = await page.evaluate((count) => performance.getEntriesByName('wickstreet:chart-painted')[count - 1].startTime, n);
  // A chart that marked twice would make the N-th mark early; record any.
  await page.waitForTimeout(300);
  const marks = await page.evaluate(() => performance.getEntriesByName('wickstreet:chart-painted').length);
  extraMarks = Math.max(extraMarks, marks - n);
  return at;
}

let extraMarks = 0;

async function panFps(page: Page): Promise<number> {
  const box = (await page.getByTestId('price-chart').first().boundingBox())!;
  const y = box.y + box.height * 0.5;
  await page.evaluate(() => {
    const w = window as unknown as { frames_: number; counting: boolean };
    w.frames_ = 0;
    w.counting = true;
    const tick = () => {
      if (!w.counting) return;
      w.frames_ += 1;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  const start = Date.now();
  await page.mouse.move(box.x + box.width * 0.7, y);
  await page.mouse.down();
  for (let i = 0; i < 30; i += 1) await page.mouse.move(box.x + box.width * (0.7 - i * 0.01), y);
  await page.mouse.up();
  const seconds = (Date.now() - start) / 1000;
  const frames = await page.evaluate(() => {
    const w = window as unknown as { frames_: number; counting: boolean };
    w.counting = false;
    return w.frames_;
  });
  return frames / seconds;
}

async function heapMb(page: Page): Promise<number> {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('HeapProfiler.collectGarbage');
  await cdp.send('Performance.enable');
  const { metrics } = await cdp.send('Performance.getMetrics');
  await cdp.detach();
  return (metrics.find((m) => m.name === 'JSHeapUsedSize')?.value ?? 0) / 2 ** 20;
}

const results: Record<string, unknown> = {};

for (const { charts, layout } of LAYOUTS) {
  test.describe(`${charts} chart${charts > 1 ? 's' : ''}`, () => {
    test.beforeAll(async ({ request }) => {
      resetDocuments();
      const body = {
        active_chart_id: 'main',
        layout,
        sync: { symbol: false, interval: false, crosshair: true },
        charts: Object.fromEntries(
          SYMBOLS.slice(0, charts).map((symbol, i) => [
            slotId(i),
            { symbol, range: 'MAX', mas: [50, 200], panes: [], indicators: [] },
          ]),
        ),
      };
      const res = await request.put('/api/v1/workspaces/default', { data: body, headers: { 'If-None-Match': '*' } });
      expect(res.status()).toBe(201);
    });

    test('warm open, pan and memory', async ({ page }) => {
      await openTime(page, charts); // load the app's assets once
      const open: number[] = [];
      const fps: number[] = [];
      const heap: number[] = [];
      for (let i = 0; i < RUNS; i += 1) {
        open.push(await openTime(page, charts));
        await expect(page.getByTestId('price-chart')).toHaveCount(charts);
        fps.push(await panFps(page));
        if (i % 5 === 0) heap.push(await heapMb(page));
      }
      results[`${charts}`] = {
        ...(results[`${charts}`] as object),
        warm_open_ms: summary(open),
        pan_fps: { runs: fps.length, p5: Math.round(percentile(fps, 0.05)), p50: Math.round(percentile(fps, 0.5)) },
        js_heap_mb: { samples: heap.length, p50: Math.round(percentile(heap, 0.5)), max: Math.round(Math.max(...heap)) },
      };
      if (charts === 1) expect(summary(open).p95).toBeLessThanOrEqual(1000); // NFR-11 warm
    });

    test('cold open', async ({ browser }: { browser: Browser }) => {
      const open: number[] = [];
      for (let i = 0; i < RUNS; i += 1) {
        const context = await browser.newContext();
        open.push(await openTime(await context.newPage(), charts));
        await context.close();
      }
      results[`${charts}`] = { ...(results[`${charts}`] as object), cold_open_ms: summary(open) };
      if (charts === 1) expect(summary(open).p95).toBeLessThanOrEqual(3000); // NFR-11 cold
    });
  });
}

test.afterAll(async ({ browser }) => {
  const report = {
    measured_at: new Date().toISOString(),
    git_commit: execSync('git rev-parse --short HEAD').toString().trim(),
    hardware: `${os.cpus()[0]?.model ?? 'unknown CPU'} × ${os.cpus().length}, ${Math.round(os.totalmem() / 2 ** 30)} GB RAM`,
    os: `${os.type()} ${os.release()} ${os.arch()}`,
    browser: `Chromium ${browser.version()} (headless)`,
    viewport: '1280 × 720 (Playwright default)',
    dataset: `${SYMBOLS.length} synthetic symbols, 2016-08-08 → 2026-08-07, 2,610 daily bars each (e2e/db.py seed); MAX range`,
    extra_paint_marks_seen: extraMarks,
    results,
  };
  mkdirSync('test-results', { recursive: true });
  writeFileSync('test-results/m13-bench.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
});
