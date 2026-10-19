import type { APIRequestContext, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/** M13: multi-chart layouts with symbol, interval and crosshair sync. */

test.beforeEach(() => resetDocuments());

async function workspace(request: APIRequestContext): Promise<Record<string, any> | null> {
  const res = await request.get('/api/v1/workspaces/default');
  return res.ok() ? (await res.json()).body : null;
}

const cell = (page: Page, id: string) => page.getByRole('region', { name: new RegExp(`^Chart ${id}: `) });

async function painted(page: Page, count: number): Promise<void> {
  await page.waitForFunction((n) => performance.getEntriesByName('wickstreet:chart-painted').length >= n, count);
}

test('a 2 × 2 layout keeps a symbol per chart, and the active chart follows the route', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await painted(page, 1);
  await page.getByLabel('Layout').selectOption('2x2');
  await expect(page.getByRole('region', { name: /^Chart / })).toHaveCount(4);
  await expect(cell(page, 'main')).toHaveAttribute('aria-current', 'true');
  await expect(cell(page, 'c2')).toHaveAccessibleName('Chart c2: TCS'); // a new slot shows the open symbol

  await cell(page, 'c2').getByTestId('price-chart').click({ position: { x: 40, y: 40 } });
  await expect(cell(page, 'c2')).toHaveAttribute('aria-current', 'true');
  await page.keyboard.press('Escape');
  await page.keyboard.type('INFY');
  await page.getByRole('dialog', { name: 'Search symbols' }).getByRole('option', { name: /INFY/ }).first().waitFor();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/chart\/INFY$/);
  await expect(cell(page, 'c2')).toHaveAccessibleName('Chart c2: INFY');
  await expect(cell(page, 'main')).toHaveAccessibleName('Chart main: TCS');
  await expect.poll(async () => {
    const ws = await workspace(request);
    return ws && { layout: ws.layout, main: ws.charts.main?.symbol, c2: ws.charts.c2?.symbol, active: ws.active_chart_id };
  }).toEqual({ layout: '2x2', main: 'TCS', c2: 'INFY', active: 'c2' });

  // Activating the other cell opens its symbol and changes nothing else.
  await cell(page, 'main').getByTestId('price-chart').click({ position: { x: 40, y: 40 } });
  await expect(page).toHaveURL(/\/chart\/TCS$/);
  await expect(cell(page, 'c2')).toHaveAccessibleName('Chart c2: INFY');

  await page.reload();
  await expect(page.getByRole('region', { name: /^Chart / })).toHaveCount(4);
  await expect(cell(page, 'c2')).toHaveAccessibleName('Chart c2: INFY');
  await expect.poll(async () => (await workspace(request))?.charts.main?.symbol).toBe('TCS');
});

test('sync shares the symbol and the interval, and turns off again', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await painted(page, 1);
  await page.getByLabel('Layout').selectOption('2x1');
  await cell(page, 'c2').getByTestId('price-chart').click({ position: { x: 40, y: 40 } });
  await page.keyboard.press('Escape');
  await page.keyboard.type('INFY');
  await page.getByRole('dialog', { name: 'Search symbols' }).getByRole('option', { name: /INFY/ }).first().waitFor();
  await page.keyboard.press('Enter');
  await expect(cell(page, 'main')).toHaveAccessibleName('Chart main: TCS');

  const sync = page.getByRole('group', { name: 'Sync' });
  await sync.getByLabel('Symbol').check();
  await expect(cell(page, 'main')).toHaveAccessibleName('Chart main: INFY');
  await sync.getByLabel('Symbol').uncheck();
  await expect(cell(page, 'main')).toHaveAccessibleName('Chart main: TCS'); // its own symbol was kept

  await sync.getByLabel('Interval').check();
  await cell(page, 'c2').getByRole('button', { name: 'Weekly bars' }).click();
  await expect(cell(page, 'main').getByRole('button', { name: 'Weekly bars' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(async () => (await workspace(request))?.sync).toEqual({ symbol: false, interval: true, crosshair: true });
});

test('the crosshair moves on every chart of the layout', async ({ page }) => {
  await page.goto('/chart/TCS');
  await painted(page, 1);
  await page.getByLabel('Layout').selectOption('2x1');
  await painted(page, 2);
  const main = cell(page, 'main').getByTestId('price-chart');
  const box = (await main.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.5);
  const readout = (id: string) => cell(page, id).getByText(/^\d{4}-\d{2}-\d{2} · C \d/);
  await expect(readout('main')).toBeVisible();
  const date = (await readout('main').textContent())!.slice(0, 10);
  await expect(readout('c2')).toHaveText(new RegExp(`^${date} · C `)); // c2 follows main's crosshair
});

test('all documented workspace layouts mount the expected number of charts', async ({ page }) => {
  await page.goto('/chart/RELIANCE');
  await painted(page, 1);
  const layouts = [
    ['1x1', 1],
    ['2x1', 2],
    ['2x2', 4],
    ['3x3', 9],
    ['4x4', 16],
  ] as const;
  for (const [layout, count] of layouts) {
    await page.getByLabel('Layout').selectOption(layout);
    if (count === 1) {
      // The single-chart view renders the active chart directly, without a grid-cell region.
      await expect(page.getByTestId('price-chart')).toHaveCount(1);
    } else {
      await expect(page.getByRole('region', { name: /^Chart / })).toHaveCount(count);
    }
  }
});
