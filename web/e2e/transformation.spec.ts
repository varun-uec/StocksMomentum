import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Page, APIRequestContext } from '@playwright/test';
import { chooseLayout, expect, openPanelTab, resetDocuments, test } from './fixtures';

const evidence = resolve(process.cwd(), '../audit-evidence/transformation/after');
async function ready(page: Page) {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText('Loading stored history…', { exact: true })).toHaveCount(0);
  await expect(page.getByTestId('price-chart').first()).toHaveAttribute('aria-label', /Price chart, [1-9]\d* daily bars/);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function savedDrawings(request: APIRequestContext, symbol = 'RELIANCE') {
  const response = await request.get(`/api/v1/drawings/${symbol}`);
  return response.ok() ? (await response.json()).body.drawings : [];
}
test.beforeEach(() => resetDocuments());
test.afterAll(() => resetDocuments());

test('range presets retain historical bars and allow panning into earlier sessions without refetching', async ({ page }) => {
  let requests = 0;
  page.on('request', (r) => { if (r.url().includes('/ohlcv')) requests++; });
  await page.goto('/chart/RELIANCE'); await ready(page);
  await page.getByRole('button', { name: '1M', exact: true }).click();
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const initialRequests = requests;
  const chart = page.getByTestId('price-chart');
  await chart.focus();
  for (let i = 0; i < 24; i++) await page.keyboard.press('ArrowLeft');
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * .5, box.y + 90);
  const readout = await page.getByTestId('crosshair-readout').textContent();
  expect(readout?.slice(0, 10)).toBeTruthy();
  expect(readout!.slice(0, 10) < '2026-07-08').toBe(true);
  expect(requests).toBe(initialRequests);
  await expect(chart).toHaveAttribute('aria-label', /2610 daily bars from 2016-08-08/);
});

test('study legends, custom parameters, colour, visibility and restore survive a session', async ({ page, request }) => {
  await page.goto('/chart/RELIANCE'); await ready(page);
  await page.getByRole('button', { name: 'Indicators', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Indicators' });
  await dialog.getByRole('button', { name: 'Bollinger Bands · browser', exact: true }).click();
  await dialog.getByRole('button', { name: 'RSI · configurable · browser', exact: true }).click();
  await dialog.getByLabel('Colour for Bollinger Bands').fill('#e11d48');
  const rsi = dialog.getByRole('listitem').filter({ has: page.getByText('RSI · configurable', { exact: true }) }).last();
  await rsi.getByRole('spinbutton', { name: 'Period' }).fill('21');
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('Study legend')).toContainText('Bollinger upper');
  await expect(page.getByLabel('Study legend')).toContainText('RSI · display');
  await page.getByRole('button', { name: /Indicators · 2/ }).click();
  await dialog.getByRole('button', { name: 'Hide Bollinger Bands', exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('Study legend')).not.toContainText('Bollinger upper');
  await expect.poll(async () => { const response = await request.get('/api/v1/workspaces/default'); return response.ok() ? (await response.json()).body?.charts?.main?.indicators?.[0]?.hidden : false; }).toBe(true);
  await page.reload(); await ready(page);
  await page.getByRole('button', { name: /Indicators · 2/ }).click();
  await expect(dialog.getByLabel('Colour for Bollinger Bands')).toHaveValue('#e11d48');
  await dialog.getByRole('button', { name: 'Show Bollinger Bands', exact: true }).click();
  await dialog.getByRole('button', { name: 'Remove', exact: true }).first().click();
  await dialog.getByRole('button', { name: 'Restore Bollinger Bands' }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('Study legend')).toContainText('Bollinger upper');
  await page.getByRole('button', { name: 'Percent scale', exact: true }).click();
  await expect(page.getByLabel('Study legend')).not.toContainText('Bollinger upper');
  await expect(page.getByLabel('Study legend')).toContainText('Price studies hidden on % scale');
});

test('inline notes and drawing lock, visibility, dash and restoration are persisted', async ({ page, request }) => {
  await page.goto('/chart/RELIANCE'); await ready(page);
  await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Text note' }).click();
  const chart = page.getByTestId('price-chart'); const box = (await chart.boundingBox())!;
  await page.mouse.click(box.x + box.width * .4, box.y + box.height * .3);
  await page.getByLabel('Annotation text').fill('Review the base after the close');
  await page.getByRole('button', { name: 'Save note' }).click();
  await chart.focus(); await page.keyboard.press('Shift+F10');
  const menu = page.getByRole('menu', { name: 'Drawing', exact: true });
  await menu.getByRole('menuitemradio', { name: 'dashed', exact: true }).click();
  await menu.getByRole('menuitem', { name: 'Lock', exact: true }).click();
  await page.keyboard.press('Escape');
  const points = (await savedDrawings(request))[0]?.points;
  await chart.focus(); await page.keyboard.press('ArrowUp');
  await page.locator('summary').filter({ hasText: 'Objects' }).click();
  await page.getByRole('button', { name: 'Hide Text note', exact: true }).click();
  await expect.poll(async () => (await savedDrawings(request))[0]).toMatchObject({ locked: true, hidden: true, dash: 'dashed', text: 'Review the base after the close' });
  if (points) expect((await savedDrawings(request))[0].points).toEqual(points);
  await page.reload(); await ready(page);
  await page.locator('summary').filter({ hasText: 'Objects' }).click();
  await page.getByRole('button', { name: 'Show Text note', exact: true }).click();
  await page.getByRole('button', { name: 'Unlock Text note', exact: true }).click();
  await page.keyboard.press('Escape');
});

test('unfinished annotations cannot follow a switch to a cached symbol', async ({ page, request }) => {
  await page.goto('/chart/TCS'); await ready(page);
  await page.getByLabel('Look up a symbol', { exact: true }).fill('RELIANCE');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'RELIANCE', exact: true })).toBeVisible();
  await ready(page);
  await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Text note' }).click();
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * .4, box.y + box.height * .2);
  await page.getByLabel('Annotation text').fill('This belongs only to RELIANCE');
  await page.getByLabel('Look up a symbol', { exact: true }).fill('TCS');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'TCS', exact: true })).toBeVisible();
  await expect(page.getByLabel('Annotation text')).toHaveCount(0);
  expect(await savedDrawings(request, 'TCS')).toEqual([]);
  expect(await savedDrawings(request, 'RELIANCE')).toEqual([]);
});

test('changing chart type preserves the price pane and drawings with only an oscillator enabled', async ({ page, request }) => {
  await page.goto('/chart/RELIANCE'); await ready(page);
  await page.getByText('Studies', { exact: true }).click();
  await page.getByLabel('MA50', { exact: true }).uncheck();
  await page.getByLabel('MA200', { exact: true }).uncheck();
  await page.getByLabel('RSI (14)', { exact: true }).check();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('price-chart').locator('canvas')).toHaveCount(11);
  const count = await page.getByTestId('price-chart').locator('canvas').count();
  for (const type of ['line', 'heikin_ashi', 'candles']) {
    await page.getByLabel('Chart type', { exact: true }).selectOption(type);
    await expect(page.getByTestId('price-chart').locator('canvas')).toHaveCount(count);
  }
  await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Horizontal line', exact: true }).click();
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * .4, box.y + box.height * .2);
  await expect.poll(async () => (await savedDrawings(request)).length).toBe(1);
});

test('grid activation keeps charts mounted and exposes one active drawing rail', async ({ page }) => {
  await page.goto('/chart/RELIANCE'); await ready(page);
  await chooseLayout(page, '2x2');
  await expect(page.getByTestId('price-chart')).toHaveCount(4);
  await page.waitForLoadState('networkidle');
  const marks = await page.evaluate(() => performance.getEntriesByName('wickstreet:chart-painted').length);
  await page.getByRole('region', { name: 'Chart c2: RELIANCE', exact: true }).getByTestId('price-chart').click({ position: { x: 100, y: 50 } });
  await expect(page.getByRole('region', { name: 'Chart c2: RELIANCE', exact: true })).toHaveAttribute('aria-current', 'true');
  await expect(page.getByRole('toolbar', { name: 'Drawing tools' })).toHaveCount(1);
  expect(await page.evaluate(() => performance.getEntriesByName('wickstreet:chart-painted').length)).toBe(marks);
  await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Horizontal line', exact: true }).click();
  await page.getByRole('region', { name: 'Chart c2: RELIANCE', exact: true }).getByTestId('price-chart').click({ position: { x: 100, y: 60 } });
});

test('armed alert editing and rectangular drawing snapshots form one chart workflow', async ({ page, request }) => {
  const response = await request.put('/api/v1/drawings/RELIANCE', { headers: { 'If-None-Match': '*' }, data: { price_basis: 'traded', drawings: [{ id: 'zone-one', kind: 'rectangle', points: [{ date: '2026-08-03', price: 270 }, { date: '2026-08-07', price: 290 }], color: '#278c76' }] } });
  expect(response.ok()).toBe(true);
  await page.goto('/chart/RELIANCE'); await ready(page);
  await openPanelTab(page, 'Alerts');
  await page.getByLabel('Threshold', { exact: true }).fill('300');
  await page.getByRole('button', { name: 'Add alert', exact: true }).click();
  await expect(page.getByRole('list', { name: 'Alerts', exact: true })).toContainText('crosses above 300');
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByLabel('Threshold', { exact: true }).fill('310');
  await page.getByRole('button', { name: 'Save alert', exact: true }).click();
  await expect(page.getByRole('list', { name: 'Alerts', exact: true })).toContainText('crosses above 310');
  await page.getByLabel('Alert drawing').selectOption('zone-one');
  await page.getByRole('button', { name: 'Add alert', exact: true }).click();
  await expect(page.getByRole('list', { name: 'Alerts', exact: true })).toContainText('leaves zone');
  const alerts = (await (await request.get('/api/v1/alerts')).json()).alerts;
  expect(alerts.find((a: { drawing: unknown }) => a.drawing)?.drawing.points.map((p: { price: string }) => Number(p.price))).toEqual([270, 290]);
  await expect(page.getByText(/EOD only · last stored session 2026-08-07/)).toBeVisible();
});

test('responsive workspace evidence in both themes and dense layouts', async ({ page }) => {
  mkdirSync(evidence, { recursive: true });
  const measurements: object[] = [];
  for (const [width, height, theme] of [[1440, 900, 'light'], [1440, 900, 'dark'], [768, 1024, 'light'], [390, 844, 'light'], [720, 450, 'dark']] as const) {
    await page.setViewportSize({ width, height });
    await page.goto('/chart/RELIANCE');
    await page.evaluate((value) => localStorage.setItem('m25-theme', value), theme);
    await page.reload(); await ready(page);
    const chart = (await page.getByTestId('price-chart').boundingBox())!;
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(2);
    if (width === 390) { expect(chart.y).toBeLessThan(260); expect(chart.y + chart.height).toBeLessThanOrEqual(790); }
    measurements.push({ width, height, theme, chart, overflow });
    await page.screenshot({ path: resolve(evidence, `chart-${width}-${theme}.png`) });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await chooseLayout(page, '4x4');
  await expect(page.getByTestId('price-chart')).toHaveCount(16);
  await page.waitForLoadState('networkidle');
  await expect(page.getByLabel('Side panel', { exact: true })).toHaveCount(0);
  await page.screenshot({ path: resolve(evidence, 'chart-grid-16.png') });
  writeFileSync(resolve(evidence, 'geometry.json'), JSON.stringify(measurements, null, 2));
});

test.describe('touch workspace', () => {
  test.use({ hasTouch: true, isMobile: true, viewport: { width: 390, height: 844 } });
  test('touch controls retain a usable chart and open contextual analysis', async ({ page, request }) => {
    await page.goto('/chart/RELIANCE'); await ready(page);
    const box = (await page.getByTestId('price-chart').boundingBox())!;
    expect(box.y).toBeLessThan(280);
    expect(box.y + box.height).toBeLessThanOrEqual(790);
    await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Horizontal line', exact: true }).tap();
    await page.getByTestId('price-chart').tap({ position: { x: box.width * .4, y: 100 } });
    await expect.poll(async () => (await savedDrawings(request)).length).toBe(1);
    await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Trendline', exact: true }).tap();
    await page.getByTestId('price-chart').tap({ position: { x: 80, y: 130 } });
    expect((await savedDrawings(request)).length).toBe(1);
    await page.getByTestId('price-chart').tap({ position: { x: 180, y: 180 } });
    await expect.poll(async () => (await savedDrawings(request)).length).toBe(2);
    await page.getByRole('button', { name: 'Panel', exact: true }).tap();
    await page.getByRole('tab', { name: 'Details', exact: true }).tap();
    await expect(page.getByRole('tabpanel', { name: 'Details', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Close panel', exact: true }).tap();
    await expect(page.getByLabel('Side panel', { exact: true })).toBeHidden();
  });
});

test('global command search keeps a security connected to research and its chart', async ({ page }) => {
  await page.goto('/studio');
  await page.keyboard.press('Control+k');
  const search = page.getByRole('dialog', { name: 'Search symbols', exact: true });
  await search.getByRole('combobox').fill('INFY');
  await expect(search.getByRole('option', { name: /INFY/ }).first()).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/stock\/INFY$/);
  await page.getByRole('link', { name: 'Open in chart', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'INFY', exact: true })).toBeVisible();
});

test('drawing menu arrows navigate and a style edit retains keyboard focus', async ({ page, request }) => {
  await page.goto('/chart/RELIANCE'); await ready(page);
  await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Horizontal line', exact: true }).click();
  const chart = page.getByTestId('price-chart'); const box = (await chart.boundingBox())!;
  await page.mouse.click(box.x + box.width * .4, box.y + box.height * .2);
  await chart.focus(); await page.keyboard.press('Shift+F10');
  const menu = page.getByRole('menu', { name: 'Drawing', exact: true });
  await expect(menu.getByRole('menuitemradio', { name: 'Indigo', exact: true })).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await expect(menu.getByRole('menuitemradio', { name: 'Sky', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect.poll(async () => (await savedDrawings(request))[0]?.color).toBe('#0ea5e9');
  await expect(menu.getByRole('menuitemradio', { name: 'Sky', exact: true })).toBeFocused();
  await page.keyboard.press('End');
  await expect(menu.getByRole('menuitem', { name: 'Delete', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(chart).toBeFocused();
});
