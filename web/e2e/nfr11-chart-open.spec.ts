import { execSync, spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import type { Browser, Page } from '@playwright/test';
import { BACKEND_DIR, E2E_DATABASE_URL } from './env';
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
 * Cold: each run starts a fresh API process on a separate port and a fresh
 * browser context. The chart navigation starts after the API is healthy, so
 * this measures the first chart open after restart, not process boot time.
 */

const RUNS = 30;
const SYMBOLS = Array.from({ length: 10 }, (_, i) => `E2E10Y${i}`);

test.describe.configure({ mode: 'serial' });
test.setTimeout(600_000);

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

const COLD_API_PORT = 8766;
const COLD_API_URL = `http://127.0.0.1:${COLD_API_PORT}`;

async function waitForColdApi(server: ReturnType<typeof spawn>): Promise<void> {
  const deadline = Date.now() + 30_000;
  let lastError = 'no health response';
  while (Date.now() < deadline && server.exitCode === null) {
    try {
      const response = await fetch(`${COLD_API_URL}/api/v1/health/live`);
      if (response.ok) return;
      lastError = `health returned ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(`cold API failed to become healthy: ${lastError}`);
}

async function openAfterApiRestart(browser: Browser, symbol: string): Promise<number> {
  const server = spawn(
    `${BACKEND_DIR}/.venv/bin/python`,
    ['-m', 'uvicorn', 'momentum25.main:app', '--host', '127.0.0.1', '--port', String(COLD_API_PORT), '--app-dir', 'src'],
    {
      cwd: BACKEND_DIR,
      env: {
        ...process.env,
        M25_DATABASE_URL: E2E_DATABASE_URL,
        E2E_DATABASE_URL,
        M25_WEB_DIST_DIR: `${process.cwd()}/dist`,
        M25_STRATEGY_DIR: '../docs/architecture/strategies',
        M25_SCHEDULER_ENABLED: 'false',
        M25_ENVIRONMENT: 'test',
        M25_LOG_JSON: 'false',
        M25_RATE_LIMIT_MAX_REQUESTS: '100000',
      },
      stdio: 'ignore',
    },
  );
  const exited = new Promise<void>((resolve) => server.once('exit', () => resolve()));
  let context: Awaited<ReturnType<Browser['newContext']>> | undefined;
  try {
    await waitForColdApi(server);
    context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(`${COLD_API_URL}/chart/${symbol}`);
    await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
    await expect(page.getByText(/^2\d{3} daily bars/)).toBeVisible();
    const paint = await page.evaluate(
      () => performance.getEntriesByName('wickstreet:chart-painted')[0].startTime,
    );
    return paint;
  } finally {
    await context?.close();
    if (server.exitCode === null) server.kill('SIGTERM');
    await exited;
  }
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

test('cold open after API restart, 30 runs', async ({ browser }: { browser: Browser }) => {
  const times: number[] = [];
  for (let i = 0; i < RUNS; i += 1) {
    times.push(await openAfterApiRestart(browser, SYMBOLS[i % SYMBOLS.length]));
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
    dataset: `${SYMBOLS.length} synthetic symbols, 2016-08-08 → 2026-08-07, 2,610 daily bars each (marked E2E database)`,
    cold_method: 'fresh API process on port 8766 and fresh browser context for each run; navigation starts after /health/live returns 200; API boot time is excluded',
    results,
  };
  mkdirSync('test-results', { recursive: true });
  writeFileSync('test-results/nfr11.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
});
