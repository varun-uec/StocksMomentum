import type { APIRequestContext, Locator, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/** M11 vertical slice: Find → Analyse → Draw → Restore (ADR-013 §5, M9 §3). */

test.beforeEach(() => resetDocuments());

const chart = (page: Page) => page.getByTestId('price-chart');

async function chartReady(page: Page): Promise<void> {
  await expect(chart(page).locator('canvas').first()).toBeVisible();
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ daily bars from the stored NSE series/)).toBeVisible();
}

async function changeStudy(page: Page, label: string, checked: boolean) {
  const details = page.locator('details').filter({ has: page.getByText('Studies', { exact: true }) });
  if (!(await details.getAttribute('open'))) { if (!(await details.evaluate((el) => (el as HTMLDetailsElement).open))) await page.getByText('Studies', { exact: true }).click(); }
  await checkbox(page, label).setChecked(checked);
}

/** A point on the price pane, as fractions of the chart box. */
async function at(page: Page, fx: number, fy: number): Promise<{ x: number; y: number }> {
  const box = (await chart(page).boundingBox())!;
  return { x: box.x + box.width * fx, y: box.y + box.height * fy };
}

async function clickAt(page: Page, fx: number, fy: number): Promise<void> {
  const p = await at(page, fx, fy);
  await page.mouse.click(p.x, p.y);
}

async function drag(page: Page, from: [number, number], to: [number, number]): Promise<void> {
  const a = await at(page, ...from);
  const b = await at(page, ...to);
  await page.mouse.move(a.x, a.y);
  await page.mouse.down();
  await page.mouse.move(b.x, b.y, { steps: 8 });
  await page.mouse.up();
}

/** The save indicator shows a confirmed save and nothing is pending. */
async function settled(page: Page): Promise<void> {
  await expect(page.getByTestId('save-state')).toHaveText(/^Saved ✓ \d/, { timeout: 5000 });
}

async function drawTrendline(page: Page, from: [number, number], to: [number, number]): Promise<void> {
  await page.getByRole('button', { name: 'Trendline' }).click();
  await clickAt(page, ...from);
  await clickAt(page, ...to);
}

type Drawing = { id: string; kind: string; points: { date: string; price: number }[] };

async function serverDrawings(request: APIRequestContext, symbol: string): Promise<Drawing[]> {
  const res = await request.get(`/api/v1/drawings/${symbol}`);
  return res.status() === 404 ? [] : (await res.json()).body.drawings;
}

const drawingCount = (request: APIRequestContext, symbol: string) => () =>
  serverDrawings(request, symbol).then((d) => d.length);

async function serverChart(request: APIRequestContext): Promise<{ range: string; mas: number[]; panes: string[] } | null> {
  const res = await request.get('/api/v1/workspaces/default');
  return res.ok() ? (await res.json()).body.charts.main ?? null : null;
}

const checkbox = (page: Page, label: string): Locator => page.getByLabel(label, { exact: true });

test('the app under test and the cleanup use the same E2E database', async ({ request }) => {
  const res = await request.put('/api/v1/workspaces/default', { data: { charts: {} }, headers: { 'If-None-Match': '*' } });
  expect(res.status()).toBe(201);
  resetDocuments();
  expect((await request.get('/api/v1/workspaces/default')).status()).toBe(404);
});

test('Find: typing on the chart opens search and Enter opens the symbol', async ({ page }) => {
  await page.goto('/chart');
  await expect(page).toHaveURL(/\/chart\/RELIANCE$/);
  await chartReady(page);
  await page.keyboard.press('t');
  const box = page.getByRole('combobox', { name: 'Symbol or company' });
  await expect(box).toBeFocused();
  await expect(box).toHaveValue('t');
  await page.keyboard.type('cs');
  await expect(page.getByRole('option', { name: /^TCS/ })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/chart\/TCS$/);
  await expect(page.locator('h1')).toHaveText('TCS');
  await expect(box).toBeHidden();

  await page.keyboard.press('Control+k');
  await expect(box).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(box).toBeHidden();

  // A second search, typed at full speed: the opening letter stays and the last search's text is gone.
  await page.getByTestId('price-chart').focus();
  await page.keyboard.type('INFY', { delay: 0 });
  await expect(box).toHaveValue('INFY');
});

test('Analyse → Draw → Restore: state survives a reload and a second browser', async ({ page, browser, request }) => {
  await page.goto('/chart/TCS');
  await chartReady(page);

  // Analyse: one more moving average, the RSI pane, the full range.
  await changeStudy(page, 'MA20', true);
  await changeStudy(page, 'RSI (14)', true);
  await page.getByRole('button', { name: 'MAX', exact: true }).click();
  await chartReady(page);

  // Draw two trendlines; drag the first; select and delete the second.
  await drawTrendline(page, [0.3, 0.2], [0.5, 0.35]);
  await drawTrendline(page, [0.6, 0.15], [0.8, 0.25]);
  await expect.poll(drawingCount(request, 'TCS')).toBe(2);
  const before = await serverDrawings(request, 'TCS');

  await drag(page, [0.4, 0.275], [0.4, 0.4]); // the middle of the first line
  await clickAt(page, 0.7, 0.2); // select the second
  await page.keyboard.press('Delete');
  await expect.poll(drawingCount(request, 'TCS')).toBe(1);
  await expect
    .poll(async () => (await serverDrawings(request, 'TCS'))[0].points[0].price)
    .toBeLessThan(before[0].points[0].price); // moved down the chart
  await expect.poll(() => serverChart(request)).toMatchObject({ range: 'MAX', mas: expect.arrayContaining([20]), panes: ['rsi'] });
  await settled(page);
  const after = await serverDrawings(request, 'TCS');
  expect(after[0].id).toBe(before[0].id);

  // Restore: reload.
  await page.reload();
  await chartReady(page);
  await expect(checkbox(page, 'MA20')).toBeChecked();
  await expect(checkbox(page, 'RSI (14)')).toBeChecked();
  await expect(page.getByRole('button', { name: 'Clear' })).toBeVisible();

  // Restore: a fresh browser opens the last symbol with the same state.
  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto('/chart');
  await expect(second).toHaveURL(/\/chart\/TCS$/);
  await expect(second.getByTestId('price-chart').locator('canvas').first()).toBeVisible();
  await expect(second.getByLabel('MA20', { exact: true })).toBeChecked();
  await expect(second.getByRole('button', { name: 'Clear' })).toBeVisible();
  await other.close();
});

test('Restore: an edit made just before leaving the page is not lost', async ({ page, request }) => {
  await page.goto('/chart/INFY');
  await chartReady(page);
  await drawTrendline(page, [0.3, 0.2], [0.5, 0.3]);
  await page.goto('/about'); // leave at once, inside the save delay
  await expect.poll(drawingCount(request, 'INFY')).toBe(1);
});

test('two windows editing different drawings merge silently', async ({ page, browser, request }) => {
  await page.goto('/chart/HDFCBANK');
  await chartReady(page);
  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto('/chart/HDFCBANK');
  await chartReady(second);

  await drawTrendline(page, [0.2, 0.2], [0.35, 0.3]);
  await expect.poll(drawingCount(request, 'HDFCBANK')).toBe(1);
  await drawTrendline(second, [0.6, 0.2], [0.75, 0.3]); // based on the older revision
  await expect.poll(drawingCount(request, 'HDFCBANK')).toBe(2);
  await settled(second);
  await expect(second.getByRole('alert')).toHaveCount(0);
  await other.close();
});

test('two windows editing the same drawing get the conflict notice, and the choice is saved', async ({ page, browser, request }) => {
  await page.goto('/chart/HDFCBANK');
  await chartReady(page);
  await drawTrendline(page, [0.3, 0.2], [0.5, 0.3]);
  await expect.poll(drawingCount(request, 'HDFCBANK')).toBe(1);
  const original = (await serverDrawings(request, 'HDFCBANK'))[0];

  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto('/chart/HDFCBANK');
  await chartReady(second);

  await drag(page, [0.4, 0.25], [0.4, 0.15]); // window 1 moves it up
  await expect
    .poll(async () => (await serverDrawings(request, 'HDFCBANK'))[0].points[0].price)
    .toBeGreaterThan(original.points[0].price);
  await drag(second, [0.4, 0.25], [0.4, 0.45]); // window 2, still on the old revision, moves it down

  const notice = second.getByRole('alert');
  await expect(notice).toContainText('changed in another window');
  const theirs = (await serverDrawings(request, 'HDFCBANK'))[0];
  await notice.getByRole('button', { name: 'Apply mine' }).click();
  await expect(notice).toBeHidden();
  await expect
    .poll(async () => (await serverDrawings(request, 'HDFCBANK'))[0].points[0].price)
    .toBeLessThan(original.points[0].price); // window 2's version won
  expect(theirs.points[0].price).toBeGreaterThan(original.points[0].price);
  await other.close();
});

test('drawings saved in this browser before M11 are imported once; a server copy wins', async ({ browser, request }) => {
  const legacy = (price: number) =>
    JSON.stringify({
      timeframe: '1Y',
      activeMas: [50, 200],
      activePanes: [],
      drawings: [
        {
          id: `legacy-${price}`,
          kind: 'horizontal',
          color: '#6366f1',
          points: [{ date: '2026-06-01', price }],
        },
      ],
    });

  const first = await browser.newContext();
  await first.addInitScript((value) => {
    if (!localStorage.getItem('chart-prefs:ITC')) localStorage.setItem('chart-prefs:ITC', value);
  }, legacy(400));
  const page = await first.newPage();
  let puts = 0;
  page.on('request', (r) => {
    if (r.method() === 'PUT' && r.url().endsWith('/drawings/ITC')) puts += 1;
  });
  await page.goto('/about');
  await expect.poll(() => serverDrawings(request, 'ITC').then((d) => d.map((x) => x.id))).toEqual(['legacy-400']);
  await page.reload();
  await page.waitForLoadState('networkidle');
  expect(puts).toBe(1);
  expect(await page.evaluate(() => localStorage.getItem('chart-prefs:ITC'))).not.toBeNull();
  await first.close();

  const second = await browser.newContext();
  await second.addInitScript((value) => localStorage.setItem('chart-prefs:ITC', value), legacy(999));
  const other = await second.newPage();
  await other.goto('/about');
  await other.waitForLoadState('networkidle');
  expect((await serverDrawings(request, 'ITC')).map((x) => x.id)).toEqual(['legacy-400']);
  await second.close();
});

test('the existing research screens still save their charts (NFR-13)', async ({ page, request }) => {
  await page.goto('/stock/RELIANCE');
  await expect(chart(page).locator('canvas').first()).toBeVisible();
  await chart(page).scrollIntoViewIfNeeded();
  await page.getByRole('button', { name: 'Horizontal ray' }).click();
  await clickAt(page, 0.5, 0.3);
  await expect.poll(drawingCount(request, 'RELIANCE')).toBe(1);
  // Drawings belong to the symbol: the chart workspace shows the same one.
  await page.goto('/chart/RELIANCE');
  await chartReady(page);
  await expect(page.getByRole('button', { name: 'Clear' })).toBeVisible();
});

test('chart settings saved in this browser before M11 are imported once; a server copy wins', async ({ browser, request }) => {
  const prefs = (activeMas: number[]) => JSON.stringify({ timeframe: 'MAX', activeMas, activePanes: ['rsi'], drawings: [] });
  const overlays = JSON.stringify({ indicators: [{ uid: 'sma-a1b2c3', id: 'sma', params: { period: 30 } }], presetId: 'nope', showSignals: false, presetEdited: true });

  const first = await browser.newContext();
  await first.addInitScript(
    ([p, o]) => {
      if (localStorage.getItem('wickstreet:imported:presentation')) return;
      localStorage.setItem('chart-prefs:TCS', p);
      localStorage.setItem('chart-prefs:INFY', p);
      localStorage.setItem('chart-overlays:TCS', o);
    },
    [prefs([20, 50]), overlays],
  );
  const page = await first.newPage();
  await page.goto('/chart/ITC');
  await chartReady(page);
  await expect(checkbox(page, 'MA20')).toBeChecked();
  await expect(checkbox(page, 'RSI (14)')).toBeChecked();
  await expect(checkbox(page, 'MA200')).not.toBeChecked();

  const saved = async () => {
    const res = await request.get('/api/v1/workspaces/default');
    return res.ok() ? (await res.json()).body.charts : null;
  };
  await expect.poll(saved).toMatchObject({
    main: { symbol: 'ITC', range: 'MAX', mas: [20, 50], panes: ['rsi'] },
    stock: { range: 'MAX', mas: [20, 50] },
    analysis: { mas: [20, 50], indicators: [{ id: 'sma', uid: 'sma-1' }], show_signals: false, preset_edited: true },
  });
  let puts = 0;
  page.on('request', (r) => {
    if (r.method() === 'PUT' && r.url().includes('/workspaces/')) puts += 1;
  });
  await page.reload(); // the marker stops a second import
  await chartReady(page);
  await page.waitForLoadState('networkidle');
  expect(puts).toBe(0);
  await first.close();

  // A second browser with other old settings changes nothing: the server copy wins.
  const second = await browser.newContext();
  await second.addInitScript((p) => localStorage.setItem('chart-prefs:TCS', p), prefs([10]));
  const other = await second.newPage();
  await other.goto('/chart/ITC');
  await chartReady(other);
  await expect(other.getByLabel('MA20', { exact: true })).toBeChecked();
  expect((await saved()).stock.mas).toEqual([20, 50]);
  await second.close();
});

test('two windows changing different chart settings merge silently', async ({ page, browser, request }) => {
  await page.goto('/chart/TCS');
  await chartReady(page);
  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto('/chart/TCS');
  await chartReady(second);

  await changeStudy(page, 'MA20', true);
  await expect.poll(async () => (await serverChart(request))?.mas).toContain(20);
  await changeStudy(second, 'RSI (14)', true); // based on the older revision
  await expect.poll(() => serverChart(request)).toMatchObject({ mas: expect.arrayContaining([20, 50, 200]), panes: ['rsi'] });
  await settled(second);
  await expect(second.getByRole('alert')).toHaveCount(0);
  await other.close();
});

test('two windows changing the same chart setting get the conflict notice; nothing is overwritten silently', async ({ page, browser, request }) => {
  await page.goto('/chart/TCS');
  await chartReady(page);
  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto('/chart/TCS');
  await chartReady(second);

  await changeStudy(page, 'MA20', true); // window 1: mas [20, 50, 200]
  await expect.poll(async () => (await serverChart(request))?.mas).toContain(20);
  await changeStudy(second, 'MA50', false); // window 2, on the old revision: mas [200]

  const notice = second.getByRole('alert');
  await expect(notice).toContainText('Your chart settings changed in another window');
  expect((await serverChart(request))?.mas).toEqual(expect.arrayContaining([20, 50, 200])); // window 1's change still stands
  await notice.getByRole('button', { name: 'Keep theirs' }).click();
  await expect(notice).toBeHidden();
  await expect(second.getByLabel('MA20', { exact: true })).toBeChecked();
  await expect(second.getByLabel('MA50', { exact: true })).toBeChecked();
  await other.close();
});

test('a drawing conflict on a research screen shows the same notice', async ({ page, browser, request }) => {
  await page.goto('/chart/HDFCBANK');
  await chartReady(page);
  await drawTrendline(page, [0.3, 0.2], [0.5, 0.3]);
  await expect.poll(drawingCount(request, 'HDFCBANK')).toBe(1);
  const original = (await serverDrawings(request, 'HDFCBANK'))[0];

  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto('/stock/HDFCBANK');
  await second.getByTestId('price-chart').scrollIntoViewIfNeeded();
  await expect(second.getByRole('button', { name: 'Clear' })).toBeVisible();

  await drag(page, [0.4, 0.25], [0.4, 0.15]); // window 1 moves it
  await expect
    .poll(async () => (await serverDrawings(request, 'HDFCBANK'))[0].points[0].price)
    .toBeGreaterThan(original.points[0].price);
  await second.getByRole('button', { name: 'Clear' }).click(); // window 2, on the old revision, deletes it

  const notice = second.getByRole('alert');
  await expect(notice).toContainText('Your drawings on HDFCBANK changed in another window');
  expect(await drawingCount(request, 'HDFCBANK')()).toBe(1); // the move still stands
  await notice.getByRole('button', { name: 'Apply mine' }).click();
  await expect.poll(drawingCount(request, 'HDFCBANK')).toBe(0);
  await other.close();
});

test('drawings are saved at traded prices, so they stay on their bars across a split and a bonus', async ({ page, request }) => {
  // GOLDIAM: a 1:5 split went ex on 2022-03-28 and a 1:3 bonus on 2026-07-10.
  // Bars before the split carry factor 0.15; bars between the two carry 0.75.
  await page.goto('/chart/GOLDIAM');
  await chartReady(page);
  await page.getByRole('button', { name: 'MAX', exact: true }).click();
  await chartReady(page);

  // Both ends at the same height: the same adjusted price on two sides of the split.
  await drawTrendline(page, [0.15, 0.6], [0.6, 0.6]);
  await expect.poll(drawingCount(request, 'GOLDIAM')).toBe(1);
  const [line] = await serverDrawings(request, 'GOLDIAM');
  const [before, after] = line.points;
  expect(before.date < '2022-03-28' && after.date > '2022-03-28' && after.date < '2026-07-10').toBe(true);
  expect(before.price / after.price).toBeCloseTo(0.75 / 0.15, 6);

  // The line shows where it was drawn: a click on its middle selects it.
  await clickAt(page, 0.375, 0.6);
  await page.keyboard.press('Delete');
  await expect.poll(drawingCount(request, 'GOLDIAM')).toBe(0);
});
