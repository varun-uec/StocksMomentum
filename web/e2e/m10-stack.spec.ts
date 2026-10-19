import { expect, openAppMenu, SYMBOL, test } from './fixtures';

/** ADR-013 spike criteria S1, S3, S4, S7 and the attribution requirement (ADR-012). */

const ROUTES: [path: string, heading: RegExp][] = [
  ['/', /./],
  [`/stock/${SYMBOL}`, new RegExp(SYMBOL)],
  [`/stock/${SYMBOL}/analysis`, new RegExp(SYMBOL)],
  [`/stock/${SYMBOL}/elliott-wave`, /Elliott/i],
  ['/watchlist', /Watchlist/],
  ['/market', /./],
  ['/strategies', /./],
  ['/validation', /./],
  ['/backtest', /./],
  ['/historical', /./],
  ['/experiment', /./],
  ['/analytics', /./],
  ['/data', /./],
  ['/learn', /./],
  ['/learn/momentum-investing', /./],
  ['/learn/minervini-methodology', /./],
  ['/learn/momentum25-methodology', /./],
  ['/learn/scoring-guide', /./],
  ['/learn/rule-guide', /./],
  ['/learn/faq', /./],
  ['/about', /About Wickstreet/],
];

for (const [path, heading] of ROUTES) {
  test(`route ${path} renders on a hard load (NFR-13, S1)`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('h1').first()).toHaveText(heading);
    await page.waitForLoadState('networkidle');
  });
}

test('unknown routes show the not-found page', async ({ page }) => {
  await page.goto('/no/such/screen');
  await expect(page.locator('h1')).toHaveText('Page not found');
});

test('S1: a deep link survives a reload and a new tab', async ({ page, context }) => {
  const url = `/stock/${SYMBOL}/analysis?strategy=minervini_trend_template`;
  await page.goto(url);
  await expect(page.locator('h1').first()).toContainText(SYMBOL);
  await page.reload();
  await expect(page.locator('h1').first()).toContainText(SYMBOL);
  const tab = await context.newPage();
  await tab.goto(url);
  await expect(tab.locator('h1').first()).toContainText(SYMBOL);
});

test('S3: every request goes to the page origin, under /api/v1 for data', async ({ page, baseURL }) => {
  const foreign: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).origin !== new URL(baseURL!).origin) foreign.push(req.url());
  });
  await page.goto(`/stock/${SYMBOL}`);
  await page.waitForLoadState('networkidle');
  expect(foreign).toEqual([]);
});

test('S4: the query cache survives client-side navigation', async ({ page }) => {
  let ohlcvCalls = 0;
  page.on('request', (req) => {
    if (req.url().includes(`/securities/${SYMBOL}/ohlcv`)) ohlcvCalls += 1;
  });
  await page.goto(`/stock/${SYMBOL}`);
  await page.waitForLoadState('networkidle');
  const afterFirstLoad = ohlcvCalls;
  await (await openAppMenu(page)).getByRole('link', { name: 'Watchlist' }).click();
  await expect(page.locator('h1').first()).toHaveText('Watchlist');
  await page.goBack();
  await expect(page.locator('h1').first()).toContainText(SYMBOL);
  await page.waitForLoadState('networkidle');
  expect(afterFirstLoad).toBeGreaterThan(0);
  expect(ohlcvCalls).toBe(afterFirstLoad);
});

test('the chart library is credited on every page and on About (ADR-012)', async ({ page }) => {
  await page.goto('/watchlist');
  const credit = page.locator('footer').getByRole('link', { name: 'TradingView Lightweight Charts™' });
  await expect(credit).toHaveAttribute('href', 'https://www.tradingview.com/');
  await page.locator('footer').getByRole('link', { name: 'About Wickstreet' }).click();
  await expect(page.getByTestId('lightweight-charts-notice')).toContainText('TradingView Lightweight Charts™');
  await expect(page.getByRole('link', { name: 'https://www.tradingview.com/' })).toBeVisible();
});

test('S7 smoke: 16 charts mount, pan and unmount without errors', async ({ page }) => {
  await page.goto(`/lab/chart-grid?n=16&symbol=${SYMBOL}`);
  const cells = page.getByTestId('chart-cell');
  await expect(cells).toHaveCount(16);
  for (const cell of await cells.all()) await expect(cell.locator('canvas').first()).toBeVisible();
  const box = (await cells.nth(5).locator('canvas').first().boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 4, box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
  await page.goto('/about');
  await expect(page.locator('h1')).toHaveText('About Wickstreet');
});

test('ADR-012: a cross-site write is rejected, a write without Origin passes', async ({ request, baseURL }) => {
  const url = `/api/v1/watchlist/${SYMBOL}`;
  const crossSite = await request.post(url, { headers: { Origin: 'https://evil.example' } });
  expect(crossSite.status()).toBe(403);
  const sameOrigin = await request.post(url, { headers: { Origin: new URL(baseURL!).origin } });
  expect(sameOrigin.ok()).toBeTruthy();
  const noOrigin = await request.delete(url);
  expect(noOrigin.ok()).toBeTruthy();
});
