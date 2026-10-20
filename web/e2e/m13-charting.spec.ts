import type { APIRequestContext, Page } from '@playwright/test';
import { expect, openChartSettings, pickTool, resetDocuments, test } from './fixtures';

/** M13: professional charting. */

test.beforeEach(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ (daily|weekly|monthly) bars from the stored NSE series/)).toBeVisible();
}

async function mainChart(request: APIRequestContext): Promise<Record<string, unknown> | null> {
  const res = await request.get('/api/v1/workspaces/default');
  return res.ok() ? (await res.json()).body?.charts.main ?? null : null;
}

test('every chart type and price scale draws, and the choice is saved with the chart', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  const type = page.getByLabel('Chart type');
  for (const value of ['bars', 'line', 'area', 'heikin_ashi', 'candles']) {
    await type.selectOption(value);
    await expect(page.getByTestId('price-chart').locator('canvas').first()).toBeVisible();
  }
  await type.selectOption('heikin_ashi');
  await page.getByRole('button', { name: 'Log scale' }).click();
  await expect(page.getByRole('button', { name: 'Log scale' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => mainChart(request)).toMatchObject({ chart_type: 'heikin_ashi', scale: 'log' });

  await page.getByRole('button', { name: 'Percent scale' }).click();
  await expect(page.getByRole('button', { name: 'Log scale' })).toHaveAttribute('aria-pressed', 'false');
  await expect.poll(() => mainChart(request)).toMatchObject({ scale: 'percent' });

  await page.reload();
  await ready(page);
  await expect(page.getByLabel('Chart type')).toHaveValue('heikin_ashi');
  await expect(page.getByRole('button', { name: 'Percent scale' })).toHaveAttribute('aria-pressed', 'true');
});

type Drawing = { id: string; kind: string; color: string; width: number; text: string | null; points: { date: string; price: number }[] };

async function drawings(request: APIRequestContext, symbol: string): Promise<Drawing[]> {
  const res = await request.get(`/api/v1/drawings/${symbol}`);
  return res.ok() ? ((await res.json()).body?.drawings ?? []) : [];
}

async function clickAt(page: Page, fx: number, fy: number): Promise<void> {
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
}

test('every M13 tool draws and is saved', async ({ page, request }) => {
  await page.goto('/chart/INFY');
  await ready(page);
  const rail = page.getByRole('toolbar', { name: 'Drawing tools' });

  const tools: [string, [number, number][]][] = [
    ['Trendline', [[0.12, 0.12], [0.25, 0.25]]],
    ['Ray', [[0.2, 0.2], [0.3, 0.25]]],
    ['Extended line', [[0.2, 0.3], [0.3, 0.35]]],
    ['Horizontal ray', [[0.4, 0.2]]],
    ['Horizontal line', [[0.5, 0.15]]],
    ['Vertical line', [[0.45, 0.5]]],
    ['Cross line', [[0.55, 0.55]]],
    ['Parallel channel', [[0.6, 0.3], [0.8, 0.2], [0.7, 0.35]]],
    ['Rectangle', [[0.2, 0.65], [0.35, 0.8]]],
    ['Fib retracement', [[0.4, 0.65], [0.55, 0.8]]],
    ['Price range', [[0.62, 0.6], [0.7, 0.45]]],
    ['Text note', [[0.3, 0.6]]],
  ];
  for (const [name, clicks] of tools) {
    await pickTool(page, name);
    for (const [x, y] of clicks) await clickAt(page, x, y);
    if (name === 'Text note') { await page.getByLabel('Annotation text').fill('Base breakout'); await page.getByRole('button', { name: 'Save note' }).click(); }
    await expect(rail.getByRole('button', { name: 'Select' })).toHaveAttribute('aria-pressed', 'true'); // the tool finished
  }
  await expect.poll(async () => (await drawings(request, 'INFY')).map((d) => d.kind).sort()).toEqual(
    ['channel', 'crossline', 'extended', 'fib', 'hline', 'horizontal', 'price_range', 'ray', 'rectangle', 'text', 'trendline', 'vline'],
  );
  const saved = await drawings(request, 'INFY');
  expect(saved.find((d) => d.kind === 'channel')!.points).toHaveLength(3);
  expect(saved.find((d) => d.kind === 'text')!.text).toBe('Base breakout');
});

const DRAWING_LIFECYCLE_CASES: {
  name: string;
  clicks: [number, number][];
  body: [number, number];
}[] = [
  { name: 'Trendline', clicks: [[0.12, 0.12], [0.25, 0.25]], body: [0.185, 0.185] },
  { name: 'Ray', clicks: [[0.2, 0.2], [0.3, 0.25]], body: [0.25, 0.225] },
  { name: 'Extended line', clicks: [[0.2, 0.3], [0.3, 0.35]], body: [0.25, 0.325] },
  { name: 'Horizontal ray', clicks: [[0.4, 0.2]], body: [0.75, 0.2] },
  { name: 'Horizontal line', clicks: [[0.5, 0.15]], body: [0.8, 0.15] },
  { name: 'Vertical line', clicks: [[0.45, 0.5]], body: [0.45, 0.8] },
  { name: 'Cross line', clicks: [[0.55, 0.55]], body: [0.75, 0.55] },
  { name: 'Parallel channel', clicks: [[0.6, 0.3], [0.8, 0.2], [0.7, 0.35]], body: [0.7, 0.25] },
  { name: 'Rectangle', clicks: [[0.2, 0.65], [0.35, 0.8]], body: [0.275, 0.725] },
  { name: 'Fib retracement', clicks: [[0.4, 0.65], [0.55, 0.8]], body: [0.475, 0.725] },
  { name: 'Price range', clicks: [[0.62, 0.6], [0.7, 0.45]], body: [0.66, 0.525] },
  { name: 'Text note', clicks: [[0.3, 0.6]], body: [0.32, 0.59] },
];

for (const drawing of DRAWING_LIFECYCLE_CASES) {
  test(`${drawing.name} supports move, edit, delete, undo, redo and restore`, async ({ page, request }) => {
    await page.goto('/chart/INFY');
    await ready(page);

    await pickTool(page, drawing.name);
    for (const [x, y] of drawing.clicks) await clickAt(page, x, y);
    if (drawing.name === 'Text note') { await page.getByLabel('Annotation text').fill('Lifecycle note'); await page.getByRole('button', { name: 'Save note' }).click(); }
    await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(1);
    const original = (await drawings(request, 'INFY'))[0];

    await pickTool(page, 'Select');
    const box = (await page.getByTestId('price-chart').boundingBox())!;
    const [bodyX, bodyY] = drawing.body;
    const dragX = 0.035;
    const dragY = -0.035;
    await page.mouse.move(box.x + box.width * bodyX, box.y + box.height * bodyY);
    await page.mouse.down();
    await page.mouse.move(
      box.x + box.width * (bodyX + dragX),
      box.y + box.height * (bodyY + dragY),
      { steps: 5 },
    );
    await page.mouse.up();
    await expect.poll(async () => (await drawings(request, 'INFY'))[0].points).not.toEqual(original.points);
    const moved = (await drawings(request, 'INFY'))[0];

    await page.mouse.click(
      box.x + box.width * (bodyX + dragX),
      box.y + box.height * (bodyY + dragY),
      { button: 'right' },
    );
    const menu = page.getByRole('menu', { name: 'Drawing' });
    await menu.getByRole('menuitemradio', { name: 'Rose' }).click();
    await expect.poll(async () => (await drawings(request, 'INFY'))[0].color).toBe('#ef4444');
    const edited = (await drawings(request, 'INFY'))[0];
    await page.keyboard.press('Escape');
    await expect(menu).toBeHidden();
    const chart = page.getByTestId('price-chart');
    await expect(chart).toBeFocused();

    await page.keyboard.press('Control+z'); // undo the style edit
    await expect.poll(async () => (await drawings(request, 'INFY'))[0].color).toBe(moved.color);
    await page.keyboard.press('Control+Shift+z'); // redo it
    await expect.poll(async () => (await drawings(request, 'INFY'))[0].color).toBe('#ef4444');

    await page.keyboard.press('Shift+F10');
    await page.getByRole('menu', { name: 'Drawing' }).getByRole('menuitem', { name: 'Delete' }).click();
    await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(0);
    await page.keyboard.press('Control+z'); // restore deleted drawing
    await expect.poll(async () => (await drawings(request, 'INFY'))[0]).toMatchObject({
      id: edited.id,
      color: '#ef4444',
    });
    await page.keyboard.press('Control+Shift+z'); // redo deletion
    await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(0);
    await page.keyboard.press('Control+z');

    await page.reload();
    await ready(page);
    await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(1);
    await expect.poll(async () => (await drawings(request, 'INFY'))[0]).toMatchObject({
      id: edited.id,
      color: '#ef4444',
    });
  });
}

test('every visible range changes the saved chart window', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  for (const range of ['1W', '1M', '3M', '6M', '1Y', 'MAX']) {
    await page.getByRole('button', { name: range, exact: true }).click();
    await expect(page.getByRole('button', { name: range, exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect.poll(() => mainChart(request)).toMatchObject({ range });
  }
});

test('the drawing menu restyles a drawing; undo and redo step through edits; arrows move it', async ({ page, request }) => {
  await page.goto('/chart/INFY');
  await ready(page);
  await pickTool(page, 'Horizontal line');
  await clickAt(page, 0.5, 0.4);
  await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(1);
  const beforeDrag = (await drawings(request, 'INFY'))[0];
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.4);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.3);
  await page.mouse.up();
  await expect.poll(async () => (await drawings(request, 'INFY'))[0].points[0].price).not.toBe(
    beforeDrag.points[0].price,
  ); // select and drag the saved drawing
  const original = (await drawings(request, 'INFY'))[0];

  // Right-click the line: the menu opens on it.
  await page.mouse.click(box.x + box.width * 0.3, box.y + box.height * 0.3, { button: 'right' });
  const menu = page.getByRole('menu', { name: 'Drawing' });
  await menu.getByRole('menuitemradio', { name: 'Rose' }).click();
  await menu.getByRole('menuitemradio', { name: 'Width 4' }).click();
  await expect.poll(async () => (await drawings(request, 'INFY'))[0]).toMatchObject({ color: '#ef4444', width: 4 });
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();

  // Undo twice: width, then colour. Redo once: colour.
  await page.keyboard.press('Control+z');
  await page.keyboard.press('Control+z');
  await expect.poll(async () => (await drawings(request, 'INFY'))[0]).toMatchObject({ color: original.color, width: 2 });
  await page.keyboard.press('Control+Shift+z');
  await expect.poll(async () => (await drawings(request, 'INFY'))[0].color).toBe('#ef4444');

  // The line is still selected: ↑ raises it.
  await page.keyboard.press('ArrowUp');
  await page.keyboard.press('ArrowUp');
  await expect.poll(async () => (await drawings(request, 'INFY'))[0].points[0].price).toBeGreaterThan(original.points[0].price);

  // The menu deletes it, and undo brings it back.
  await page.keyboard.press('Shift+F10');
  await menu.getByRole('menuitem', { name: 'Delete' }).click();
  await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(0);
  await page.keyboard.press('Control+z');
  await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(1);
});

test('the mouse wheel zooms the chart and a pointer drag pans it', async ({ page }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  const chart = page.getByTestId('price-chart');
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.5);
  await page.waitForTimeout(100);
  const beforeZoom = await chart.screenshot();
  await page.mouse.wheel(0, -600);
  await page.waitForTimeout(150);
  const afterZoom = await chart.screenshot();
  expect(afterZoom.equals(beforeZoom)).toBe(false);

  const beforePan = afterZoom;
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.75, box.y + box.height * 0.5, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(150);
  const afterPan = await chart.screenshot();
  expect(afterPan.equals(beforePan)).toBe(false);
});

test('Alt+I opens the indicator list; an overlay and a pane draw and are saved with the chart', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await page.keyboard.press('Alt+KeyI');
  const dialog = page.getByRole('dialog', { name: 'Indicators' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: /Bollinger Bands/ }).click();
  await dialog.getByRole('button', { name: /^CCI/ }).click();
  await expect(dialog.getByText('Legend · latest value')).toBeVisible(); // the overlay computed values
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect.poll(async () => ((await mainChart(request))?.indicators as { id: string }[] | undefined)?.map((i) => i.id)).toEqual([
    'bollinger',
    'cci',
  ]);

  await page.reload();
  await ready(page);
  await expect(page.getByRole('button', { name: 'Indicators · 2' })).toBeVisible();
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.3);
  await expect(page.getByText(/^CCI \(20\): -?\d/)).toBeVisible(); // the browser pane has values under the crosshair
});

test('the chart menu resets the view, sets the scale and opens the indicators', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.4, { button: 'right' });
  const menu = page.getByRole('menu', { name: 'Chart' });
  await expect(menu.getByRole('menuitemradio', { name: /Normal scale/ })).toHaveAttribute('aria-checked', 'true');
  await menu.getByRole('menuitemradio', { name: /Log scale/ }).click();
  await expect(menu).toBeHidden();
  await expect(page.getByRole('button', { name: 'Log scale' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => mainChart(request)).toMatchObject({ scale: 'log' });

  await page.getByTestId('price-chart').focus();
  await page.keyboard.press('Shift+F10'); // the keyboard way in, with no drawing selected
  await expect(menu.getByRole('menuitem', { name: 'Reset view' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();

  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.4, { button: 'right' });
  await menu.getByRole('menuitem', { name: 'Indicators…' }).click();
  await expect(page.getByRole('dialog', { name: 'Indicators' })).toBeVisible();
});

test('monthly bars draw with monthly indicators and are saved with the chart', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await page.getByRole('button', { name: 'MAX', exact: true }).click();
  const daily = page.getByText(/^(\d+) daily bars from the stored NSE series/);
  await expect(daily).toBeVisible();
  const sessions = Number((await daily.textContent())!.split(' ')[0]);

  await openChartSettings(page);
  await page.getByLabel('RSI (14)', { exact: true }).check();
  await page.keyboard.press('Escape');
  const monthlySeries = page.waitForResponse(
    (r) => r.url().includes('/indicators/series') && r.url().includes('interval=1M') && r.ok(),
  );
  await page.getByRole('button', { name: 'Monthly bars' }).click();
  const monthly = page.getByText(/^(\d+) monthly bars from the stored NSE series/);
  await expect(monthly).toBeVisible();
  const months = Number((await monthly.textContent())!.split(' ')[0]);
  expect(months).toBeGreaterThan(sessions / 25); // about 21 sessions a month
  expect(months).toBeLessThan(sessions / 18);
  const series = await (await monthlySeries).json();
  expect(series.interval).toBe('1M');
  expect(series.bars.at(-1).rsi14).not.toBeNull();
  await expect.poll(() => mainChart(request)).toMatchObject({ interval: '1M' });

  await page.reload();
  await expect(page.getByRole('button', { name: 'Monthly bars' })).toHaveAttribute('aria-pressed', 'true');
  await expect(monthly).toBeVisible();
});

test('a compared symbol draws as a rebased line, is saved with the chart, and can be removed', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Compare with' });
  await dialog.getByRole('combobox').fill('INFY');
  await expect(dialog.getByRole('option', { name: /INFY/ }).first()).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page.getByText(/^INFY [+-]\d+\.\d{2}%$/)).toBeVisible(); // the change since the first shared bar
  await expect(page).toHaveURL(/\/chart\/TCS$/); // comparing does not open the symbol
  await expect.poll(() => mainChart(request)).toMatchObject({ compare: ['INFY'] });

  await page.reload();
  await ready(page);
  await expect(page.getByText(/^INFY [+-]\d+\.\d{2}%$/)).toBeVisible();
  await page.getByRole('button', { name: 'Stop comparing INFY' }).click();
  await expect.poll(() => mainChart(request)).toMatchObject({ compare: [] });
});
