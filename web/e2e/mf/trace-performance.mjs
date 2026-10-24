/**
 * Reproducible cold mobile trace for the three primary MF journeys.
 * Run from web/: `node e2e/mf/trace-performance.mjs`.
 * Set MF_BASE_URL to trace a different local build; defaults to the loopback app.
 */
import { chromium } from '@playwright/test';

const baseUrl = process.env.MF_BASE_URL ?? 'http://localhost:8000';
const runCount = Number(process.env.MF_PERF_RUNS ?? 3);
if (!Number.isInteger(runCount) || runCount < 1) throw new Error('MF_PERF_RUNS must be a positive integer.');

const routes = [
  ['Discover', '/mf'],
  ['Fund Overview', '/mf/funds/122639?tab=overview'],
  ['Investment Lab', '/mf/simulate?code=122639'],
];
const browser = await chromium.launch({ headless: true });
const results = [];

for (const [route, path] of routes) {
  for (let run = 1; run <= runCount; run++) {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 3,
      isMobile: true,
      hasTouch: true,
      serviceWorkers: 'block',
    });
    const page = await context.newPage();
    await page.addInitScript(() => {
      window.__wickstreetPerf = { lcp: 0, shifts: [] };
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) window.__wickstreetPerf.lcp = entry.startTime;
      }).observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) window.__wickstreetPerf.shifts.push({ time: entry.startTime, value: entry.value });
        }
      }).observe({ type: 'layout-shift', buffered: true });
    });

    const client = await context.newCDPSession(page);
    await client.send('Network.enable');
    await client.send('Network.setCacheDisabled', { cacheDisabled: true });
    await client.send('Network.emulateNetworkConditions', {
      offline: false,
      latency: 150,
      downloadThroughput: 200 * 1024,
      uploadThroughput: 50 * 1024,
      connectionType: 'cellular3g',
    });
    await client.send('Emulation.setCPUThrottlingRate', { rate: 4 });

    const started = Date.now();
    await page.goto(new URL(path, baseUrl).toString(), { waitUntil: 'load', timeout: 60_000 });
    await page.locator('h1').first().waitFor({ state: 'visible', timeout: 30_000 });
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1_200);
    const metrics = await page.evaluate(() => ({
      lcpMs: Math.round(window.__wickstreetPerf.lcp),
      cls: (() => {
        let sessionValue = 0;
        let sessionStart = 0;
        let previousTime = -Infinity;
        let maxSession = 0;
        for (const shift of window.__wickstreetPerf.shifts) {
          if (shift.time - previousTime > 1_000 || shift.time - sessionStart > 5_000) {
            sessionValue = shift.value;
            sessionStart = shift.time;
          } else {
            sessionValue += shift.value;
          }
          previousTime = shift.time;
          maxSession = Math.max(maxSession, sessionValue);
        }
        return Number(maxSession.toFixed(3));
      })(),
      transferBytes: performance.getEntriesByType('resource').reduce((sum, entry) => sum + (entry.transferSize || 0), 0),
      resourceCount: performance.getEntriesByType('resource').length,
    }));
    results.push({ route, run, elapsedMs: Date.now() - started, ...metrics });
    await context.close();
  }
}

await browser.close();
const median = (values) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const summary = routes.map(([route]) => {
  const samples = results.filter((result) => result.route === route);
  return {
    route,
    medianLcpMs: median(samples.map((sample) => sample.lcpMs)),
    medianCls: median(samples.map((sample) => sample.cls)),
    medianTransferBytes: median(samples.map((sample) => sample.transferBytes)),
  };
});

console.log(JSON.stringify({
  baseUrl,
  viewport: '390x844',
  cache: 'disabled; fresh context for every run; service workers blocked',
  cpuThrottle: '4x',
  network: { latencyMs: 150, downloadBytesPerSecond: 200 * 1024 },
  runsPerRoute: runCount,
  summary,
  samples: results,
}, null, 2));
