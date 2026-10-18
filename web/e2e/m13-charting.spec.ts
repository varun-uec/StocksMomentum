import type { APIRequestContext, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/** M13: professional charting. */

test.beforeEach(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ (daily|weekly|monthly) bars from the stored NSE series/)).toBeVisible();
}

async function mainChart(request: APIRequestContext): Promise<Record<string, unknown> | null> {
  const res = await request.get('/api/v1/workspaces/default');
  return res.ok() ? (await res.json()).body.charts.main ?? null : null;
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
  return res.ok() ? (await res.json()).body.drawings : [];
}

async function clickAt(page: Page, fx: number, fy: number): Promise<void> {
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
}

test('every M13 tool draws and is saved', async ({ page, request }) => {
  await page.goto('/chart/INFY');
  await ready(page);
  const rail = page.getByRole('toolbar', { name: 'Drawing tools' });
  page.on('dialog', (d) => void d.accept('Base breakout'));
  const tools: [string, [number, number][]][] = [
    ['Ray', [[0.2, 0.2], [0.3, 0.25]]],
    ['Extended line', [[0.2, 0.3], [0.3, 0.35]]],
    ['Horizontal line', [[0.5, 0.15]]],
    ['Vertical line', [[0.45, 0.5]]],
    ['Cross line', [[0.55, 0.55]]],
    ['Parallel channel', [[0.6, 0.3], [0.8, 0.2], [0.7, 0.35]]],
    ['Price range', [[0.62, 0.6], [0.7, 0.45]]],
    ['Text note', [[0.3, 0.6]]],
  ];
  for (const [name, clicks] of tools) {
    await rail.getByRole('button', { name, exact: true }).click();
    for (const [x, y] of clicks) await clickAt(page, x, y);
    await expect(rail.getByRole('button', { name: 'Select' })).toHaveAttribute('aria-pressed', 'true'); // the tool finished
  }
  await expect.poll(async () => (await drawings(request, 'INFY')).map((d) => d.kind).sort()).toEqual(
    ['channel', 'crossline', 'extended', 'hline', 'price_range', 'ray', 'text', 'vline'],
  );
  const saved = await drawings(request, 'INFY');
  expect(saved.find((d) => d.kind === 'channel')!.points).toHaveLength(3);
  expect(saved.find((d) => d.kind === 'text')!.text).toBe('Base breakout');
});

test('the drawing menu restyles a drawing; undo and redo step through edits; arrows move it', async ({ page, request }) => {
  await page.goto('/chart/INFY');
  await ready(page);
  await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Horizontal line', exact: true }).click();
  await clickAt(page, 0.5, 0.4);
  await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(1);
  const original = (await drawings(request, 'INFY'))[0];

  // Right-click the line: the menu opens on it.
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.3, box.y + box.height * 0.4, { button: 'right' });
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

  await page.getByLabel('RSI (14)', { exact: true }).check();
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
