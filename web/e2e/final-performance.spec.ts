import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import { resolve } from 'node:path';
import type { APIRequestContext, Browser, Page } from '@playwright/test';
import { BACKEND_DIR, E2E_DATABASE_URL } from './env';
import { expect, resetDocuments, test } from './fixtures';

const OUT = resolve(process.cwd(), '../audit-evidence/final-stabilisation/performance.json');
const SYMBOLS = Array.from({ length: 16 }, (_, i) => `E2E10Y${i}`);
const results: Record<string, unknown> = {};

test.describe.configure({ mode: 'serial' });
test.setTimeout(600_000);

function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(p * sorted.length) - 1)];
}

function distribution(values: number[]) {
  return {
    runs: values.length,
    p50_ms: Math.round(percentile(values, 0.5)),
    p95_ms: Math.round(percentile(values, 0.95)),
    max_ms: Math.round(Math.max(...values)),
  };
}

function bumpSyntheticBar(): void {
  execFileSync(
    resolve(BACKEND_DIR, '.venv/bin/python'),
    [resolve(process.cwd(), 'e2e/db.py'), 'bump-synthetic-close'],
    { env: { ...process.env, E2E_DATABASE_URL }, stdio: 'pipe' },
  );
}

async function finishedEvaluation(request: APIRequestContext, id: number) {
  let latest: any;
  await expect
    .poll(
      async () => {
        const response = await request.get(`/api/v1/studio/evaluations/${id}`);
        latest = await response.json();
        return latest.status;
      },
      { timeout: 180_000, intervals: [250, 500, 1000] },
    )
    .toMatch(/^(completed|failed)$/);
  expect(latest.status, latest.error ?? 'evaluation failed').toBe('completed');
  return latest;
}

async function heapMb(page: Page): Promise<number> {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('HeapProfiler.collectGarbage');
  await cdp.send('Performance.enable');
  const { metrics } = await cdp.send('Performance.getMetrics');
  await cdp.detach();
  return (metrics.find((metric) => metric.name === 'JSHeapUsedSize')?.value ?? 0) / 2 ** 20;
}

test('latency distributions for search, workspace persistence, screening and alert evaluation', async ({
  request,
}) => {
  resetDocuments();
  const searchMs: number[] = [];
  for (let i = 0; i < 30; i += 1) {
    const start = Date.now();
    const response = await request.get('/api/v1/securities?q=E2E10Y&limit=10');
    expect(response.ok()).toBe(true);
    expect(await response.json()).toHaveLength(10);
    searchMs.push(Date.now() - start);
  }

  const workspaceBody = {
    active_chart_id: 'main',
    layout: '1x1',
    right_panel: 'watchlist',
    sync: { symbol: false, interval: false, crosshair: true },
    charts: {
      main: {
        symbol: 'RELIANCE',
        range: 'MAX',
        interval: '1D',
        chart_type: 'candles',
        scale: 'normal',
        mas: [],
        panes: [],
        indicators: [],
      },
    },
  };
  let save = await request.put('/api/v1/workspaces/default', {
    data: workspaceBody,
    headers: { 'If-None-Match': '*' },
  });
  expect(save.status()).toBe(201);
  let etag = save.headers().etag;
  const workspaceMs: number[] = [];
  for (let i = 0; i < 30; i += 1) {
    const start = Date.now();
    save = await request.put('/api/v1/workspaces/default', {
      data: {
        ...workspaceBody,
        charts: {
          main: {
            ...workspaceBody.charts.main,
            show_signals: i % 2 === 0,
          },
        },
      },
      headers: { 'If-Match': etag },
    });
    expect(save.status()).toBe(200);
    etag = save.headers().etag;
    workspaceMs.push(Date.now() - start);
  }
  const restored = await request.get('/api/v1/workspaces/default');
  expect(restored.ok()).toBe(true);
  expect((await restored.json()).revision).toBe(31);

  const screeningMs: number[] = [];
  const screeningIds: number[] = [];
  const screeningVersions: string[] = [];
  for (let i = 0; i < 10; i += 1) {
    bumpSyntheticBar();
    const start = Date.now();
    const response = await request.post('/api/v1/runs/execute', {
      data: { strategy: 'minervini_trend_template', force: false, background: false },
    });
    expect(response.status()).toBe(201);
    const run = await response.json();
    expect(run.status).toBe('COMPLETED');
    screeningIds.push(run.id);
    screeningVersions.push(run.data_version);
    screeningMs.push(Date.now() - start);
  }
  expect(new Set(screeningIds).size).toBe(10);
  expect(new Set(screeningVersions).size).toBe(10);
  const latest = await request.get('/api/v1/runs/latest?strategy=minervini_trend_template');
  expect(latest.ok()).toBe(true);
  expect((await latest.json()).id).toBe(screeningIds.at(-1));

  for (let i = 0; i < 20; i += 1) {
    const created = await request.post('/api/v1/alerts', {
      data: {
        symbol: 'RELIANCE',
        source: 'close',
        interval: '1D',
        condition: 'below',
        threshold: '0',
      },
    });
    expect(created.status()).toBe(201);
  }
  const alertMs: number[] = [];
  for (let i = 0; i < 20; i += 1) {
    const start = Date.now();
    const response = await request.post('/api/v1/alerts/evaluate');
    expect(response.ok()).toBe(true);
    expect((await response.json()).evaluated).toBe(20);
    alertMs.push(Date.now() - start);
  }

  results.api_latency = {
    synthetic_dataset: '22 symbols, 2,610 daily bars each, 2016-08-08 through 2026-08-07',
    search: distribution(searchMs),
    workspace_save: distribution(workspaceMs),
    live_screening_after_same_session_correction: distribution(screeningMs),
    screening_run_ids: screeningIds,
    screening_data_versions: screeningVersions,
    alert_evaluation_20_active_alerts: distribution(alertMs),
  };
});

test('Strategy Studio screening and in-sample research execution latency', async ({ page, request }) => {
  const stamp = Date.now();
  const hypothesis = `Measure isolated Strategy Studio execution latency ${stamp}.`;
  await page.goto('/studio');
  await expect(page.getByRole('heading', { name: 'Strategy Studio' })).toBeVisible();
  await page.getByLabel('Hypothesis, in one sentence').fill(hypothesis);
  await page.getByLabel('Start from').selectOption('minervini_trend_template');
  await page.getByLabel('Name of the first config').fill(`latency-${stamp}`);
  const familyCreated = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().endsWith('/api/v1/studio/families'),
  );
  await page.getByRole('button', { name: 'Create family' }).click();
  expect((await familyCreated).status()).toBe(201);

  const familiesResponse = await request.get('/api/v1/studio/families');
  expect(familiesResponse.ok()).toBe(true);
  const families = await familiesResponse.json();
  const family = families.find((item: { hypothesis: string }) => item.hypothesis === hypothesis);
  expect(family).toBeTruthy();
  const configHash = family.members[0].config_hash;
  const screeningMs: number[] = [];
  for (let i = 0; i < 10; i += 1) {
    const start = Date.now();
    const queued = await request.post(`/api/v1/studio/families/${family.id}/evaluations`, {
      data: { config_hash: configHash, result_class: 'screening' },
    });
    expect(queued.status()).toBe(202);
    const evaluation = await finishedEvaluation(request, (await queued.json()).id);
    expect(evaluation.result.label).toBe('Screening Result');
    screeningMs.push(Date.now() - start);
  }

  // Three complete in-sample evaluations bound the expensive research path.
  // The sample count is explicit: its empirical P95 is the maximum of these three.
  const researchMs: number[] = [];
  const researchDecisions: number[] = [];
  for (let i = 0; i < 3; i += 1) {
    const start = Date.now();
    const queued = await request.post(`/api/v1/studio/families/${family.id}/evaluations`, {
      data: { config_hash: configHash, result_class: 'in_sample' },
    });
    expect(queued.status()).toBe(202);
    const evaluation = await finishedEvaluation(request, (await queued.json()).id);
    expect(evaluation.result.label).toContain('Historical Research');
    researchDecisions.push(evaluation.result.decisions);
    researchMs.push(Date.now() - start);
  }
  results.strategy_studio = {
    synthetic_dataset: 'same isolated 22-symbol, 10-year fixture',
    screening_result: distribution(screeningMs),
    in_sample_research: distribution(researchMs),
    in_sample_research_decisions: researchDecisions,
    research_p95_note: '3 observations; empirical P95 is the observed maximum, not a stable production percentile.',
  };
});

test('24-cycle 1×1 ↔ 4×4 chart endurance releases mounted chart DOM and canvases', async ({
  page,
  request,
}) => {
  resetDocuments();
  const charts = Object.fromEntries(
    SYMBOLS.map((symbol, index) => [
      index === 0 ? 'main' : `c${index + 1}`,
      {
        symbol,
        range: 'MAX',
        interval: '1D',
        chart_type: 'candles',
        scale: 'normal',
        mas: [],
        panes: [],
        indicators: [],
      },
    ]),
  );
  const workspace = await request.put('/api/v1/workspaces/default', {
    data: {
      active_chart_id: 'main',
      layout: '4x4',
      sync: { symbol: false, interval: false, crosshair: true },
      charts,
    },
    headers: { 'If-None-Match': '*' },
  });
  expect(workspace.status()).toBe(201);
  await page.goto(`/chart/${SYMBOLS[0]}`);
  await expect(page.getByTestId('price-chart')).toHaveCount(16);
  await page.waitForLoadState('networkidle');

  await page.getByLabel('Layout').selectOption('1x1');
  await expect(page.getByTestId('price-chart')).toHaveCount(1);
  const initialCanvases = await page.locator('canvas').count();
  const startingHeap = await heapMb(page);
  const samples: { cycle: number; heap_mb: number; canvases: number }[] = [];
  const drawingCounts: number[] = [];

  for (let cycle = 0; cycle < 24; cycle += 1) {
    const symbol = SYMBOLS[cycle % SYMBOLS.length];
    const search = page.getByLabel('Look up a symbol');
    await search.fill(symbol);
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(new RegExp(`/chart/${symbol}$`));

    const chart = page.getByTestId('price-chart').first();
    const rail = page.getByRole('toolbar', { name: 'Drawing tools' });
    await rail.getByRole('button', { name: 'Horizontal line', exact: true }).click();
    const box = (await chart.boundingBox())!;
    await page.mouse.click(box.x + box.width * 0.43, box.y + box.height * 0.4);
    await expect
      .poll(async () => {
        const response = await request.get(`/api/v1/drawings/${symbol}`);
        return response.ok() ? (await response.json()).body.drawings.length : 0;
      })
      .toBe(1);
    drawingCounts.push(1);
    await page.keyboard.press('Shift+F10');
    await page.getByRole('menu', { name: 'Drawing' }).getByRole('menuitem', { name: 'Delete' }).click();
    await expect
      .poll(async () => {
        const response = await request.get(`/api/v1/drawings/${symbol}`);
        return response.ok() ? (await response.json()).body.drawings.length : 0;
      })
      .toBe(0);

    await page.getByLabel('Layout').selectOption('4x4');
    await expect(page.getByTestId('price-chart')).toHaveCount(16);
    await page.waitForLoadState('networkidle');
    await page.getByLabel('Layout').selectOption('1x1');
    await expect(page.getByTestId('price-chart')).toHaveCount(1);
    if ((cycle + 1) % 4 === 0) {
      samples.push({
        cycle: cycle + 1,
        heap_mb: await heapMb(page),
        canvases: await page.locator('canvas').count(),
      });
    }
  }
  const finalCanvases = await page.locator('canvas').count();
  const endingHeap = await heapMb(page);
  expect(finalCanvases).toBe(initialCanvases);
  results.chart_endurance = {
    cycles: 24,
    layouts_per_cycle: ['1x1', '4x4', '1x1'],
    long_history_bars_per_chart: 2610,
    drawings_created_and_deleted: drawingCounts.length,
    starting_heap_mb_after_gc: startingHeap,
    ending_heap_mb_after_gc: endingHeap,
    heap_delta_mb_after_gc: endingHeap - startingHeap,
    initial_canvas_count: initialCanvases,
    final_canvas_count: finalCanvases,
    samples,
  };
});

test.afterAll(async ({ browser }: { browser: Browser }) => {
  const e2eDatabase = new URL(E2E_DATABASE_URL).pathname.slice(1);
  mkdirSync(resolve(process.cwd(), '../audit-evidence/final-stabilisation'), {
    recursive: true,
  });
  writeFileSync(
    OUT,
    JSON.stringify(
      {
        measured_at: new Date().toISOString(),
        hardware: `${os.cpus()[0]?.model ?? 'unknown CPU'} × ${os.cpus().length}, ${Math.round(os.totalmem() / 2 ** 30)} GB RAM`,
        os: `${os.type()} ${os.release()} ${os.arch()}`,
        browser: `Chromium ${browser.version()} (headless)`,
        database: `${e2eDatabase}; loopback-only isolated PostgreSQL; synthetic fixtures only`,
        results,
      },
      null,
      2,
    ),
  );
});
