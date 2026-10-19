import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { expect, resetDocuments, test } from './fixtures';

const screenshots = resolve(process.cwd(), '../audit-evidence/screenshots');
const benchmarks = resolve(process.cwd(), '../audit-evidence/benchmarks');
mkdirSync(screenshots, { recursive: true });
mkdirSync(benchmarks, { recursive: true });

test.beforeEach(() => resetDocuments());

test('a slow market API keeps a loading state, then renders the result', async ({ page }) => {
  const artificialDelayMs = 1200;
  let intercepted = false;
  await page.route('**/api/v1/market/context**', async (route) => {
    intercepted = true;
    const response = await route.fetch();
    await new Promise((resolveDelay) => setTimeout(resolveDelay, artificialDelayMs));
    await route.fulfill({ response });
  });

  const started = Date.now();
  await page.goto('/market');
  await expect(page.getByText('Computing universe breadth…')).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'market-slow-loading.png') });
  await expect(page.getByText(/Universe breadth and sector strength as of/)).toBeVisible();
  expect(intercepted, 'the synthetic delay must intercept the market API request').toBe(true);
  const observedMs = Date.now() - started;
  expect(observedMs).toBeGreaterThanOrEqual(artificialDelayMs);
  writeFileSync(
    join(benchmarks, 'api-resilience.json'),
    JSON.stringify({ measured_at: new Date().toISOString(), artificial_market_api_delay_ms: artificialDelayMs, observed_render_ms: observedMs, synthetic_delay_intercepted: intercepted }, null, 2),
  );
});

test('an unavailable market API shows an error state', async ({ page }) => {
  await page.route('**/api/v1/market/context**', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      headers: { 'x-e2e-fault-injection': 'true' },
      body: JSON.stringify({ detail: 'Synthetic E2E API outage' }),
    }),
  );

  await page.goto('/market');
  await expect(page.getByText(/Market context could not be computed/)).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'market-api-unavailable.png'), fullPage: true });
});

test('an incomplete market API response is reported instead of crashing the page', async ({ page }) => {
  await page.route('**/api/v1/market/context**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: { 'x-e2e-fault-injection': 'true' },
      body: JSON.stringify({ as_of: '2026-08-07', breadth: null }),
    }),
  );

  await page.goto('/market');
  await expect(page.getByText(/Market context response was incomplete/)).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'market-incomplete-response.png'), fullPage: true });
});
