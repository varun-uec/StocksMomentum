import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import type { Browser, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/**
 * NFR-11 (ADD A1 §3): one chart opens a symbol with 10 years of locally stored
 * daily bars. Warm P95 ≤ 1 s; cold P95 ≤ 3 s (provisional); at least 30 runs per
 * case across at least 10 symbols; the environment is recorded.
 *
 * "Open" = navigation start → the `wickstreet:chart-painted` mark (first frame
 * after the price series holds its bars).
 * Warm: the same browser context, so the app's assets are cached; each run is a
 * new page load, so no symbol data is in the query cache.
 * Cold: a new browser context per run, so nothing is cached in the browser.
 * The API process is not restarted between runs (see the report).
 */

const RUNS = 30;
const SYMBOLS = Array.from({ length: 10 }, (_, i) => `E2E10Y${i}`);

test.describe.configure({ mode: 'serial' });
test.setTimeout(180_000);

function p95(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.ceil(0.95 * sorted.length) - 1];
}

const summary = (values: number[]) => ({
  runs: values.length,
  p50: Math.round([...values].sort((a, b) => a - b)[Math.floor(values.length / 2)]),
  p95: Math.round(p95(values)),
  max: Math.round(Math.max(...values)),
});

async function openTime(page: Page, symbol: string): Promise<number> {
  await page.goto(`/chart/${symbol}`);
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/^2\d{3} daily bars/)).toBeVisible(); // the full 10-year series is on screen
  return page.evaluate(() => performance.getEntriesByName('wickstreet:chart-painted')[0].startTime);
}

const results: Record<string, ReturnType<typeof summary>> = {};

test.beforeAll(async ({ request }) => {
  resetDocuments();
  // Show the whole series: the workspace's main chart opens on MAX.
  const body = { active_chart_id: 'main', charts: { main: { range: 'MAX', mas: [50, 200], panes: [], indicators: [] } } };
  const res = await request.put('/api/v1/workspaces/default', { data: body, headers: { 'If-None-Match': '*' } });
  expect(res.status()).toBe(201);
});

test('warm open, 30 runs', async ({ page }) => {
  await openTime(page, SYMBOLS[0]); // load the app's assets once
  const times: number[] = [];
  for (let i = 0; i < RUNS; i += 1) times.push(await openTime(page, SYMBOLS[i % SYMBOLS.length]));
  results.warm = summary(times);
  expect(results.warm.p95).toBeLessThanOrEqual(1000);
});

test('cold open, 30 runs', async ({ browser }: { browser: Browser }) => {
  const times: number[] = [];
  for (let i = 0; i < RUNS; i += 1) {
    const context = await browser.newContext();
    times.push(await openTime(await context.newPage(), SYMBOLS[i % SYMBOLS.length]));
    await context.close();
  }
  results.cold = summary(times);
  expect(results.cold.p95).toBeLessThanOrEqual(3000);
});

test.afterAll(async ({ browser }) => {
  const report = {
    measured_at: new Date().toISOString(),
    git_commit: execSync('git rev-parse --short HEAD').toString().trim(),
    hardware: `${os.cpus()[0]?.model ?? 'unknown CPU'} × ${os.cpus().length}, ${Math.round(os.totalmem() / 2 ** 30)} GB RAM`,
    os: `${os.type()} ${os.release()} ${os.arch()}`,
    browser: `Chromium ${browser.version()} (headless)`,
    dataset: `${SYMBOLS.length} synthetic symbols, 2016-08-08 → 2026-08-07, 2,610 daily bars each (e2e/db.py seed)`,
    results,
  };
  mkdirSync('test-results', { recursive: true });
  writeFileSync('test-results/nfr11.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
});
