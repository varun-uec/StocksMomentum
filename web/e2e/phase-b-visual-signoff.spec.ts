import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Page } from '@playwright/test';
import { expect, pickTool, resetDocuments, test } from './fixtures';

/** Opt-in captures for the Phase B sign-off, kept outside the working tree. */
const output = process.env.SIGNOFF_EVIDENCE_DIR;
test.skip(!output, 'set SIGNOFF_EVIDENCE_DIR for the Phase B visual sign-off');
test.beforeEach(() => resetDocuments());
test.afterAll(() => resetDocuments());

async function settled(page: Page) {
  await expect(page.getByText('Loading stored history…', { exact: true })).toHaveCount(0);
  await expect(page.getByTestId('price-chart')).toHaveAttribute('aria-label', /Price chart, [1-9]\d* /);
  const last = (await page.getByTestId('price-chart').getAttribute('aria-label'))!.match(/ to (\d{4}-\d{2}-\d{2})\./)![1];
  await expect(page.getByTestId('price-chart')).toHaveAttribute('data-visible-to', last);
  await page.mouse.move(0, 0);
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
}

async function shot(page: Page, name: string) {
  mkdirSync(output!, { recursive: true });
  await expect(page.getByText('Saving…', { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(2);
  await page.screenshot({ path: resolve(output!, `${name}.png`) });
}

test('representative synthetic candles after the axis fix: intervals, themes, phone and replay', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => localStorage.getItem('m25-theme') || localStorage.setItem('m25-theme', 'light'));
  await page.goto('/chart/E2ECANDLE');
  await settled(page);
  for (const [interval, range, name] of [
    ['Daily bars', '6M', 'candles-01-daily-6m-light'],
    ['Daily bars', '3M', 'candles-02-daily-3m-light'],
    ['Weekly bars', '1Y', 'candles-03-weekly-1y-light'],
    ['Monthly bars', 'MAX', 'candles-04-monthly-max-light'],
  ]) {
    await page.getByRole('button', { name: interval, exact: true }).click();
    await page.getByRole('button', { name: range, exact: true }).click();
    await settled(page);
    await shot(page, name);
  }
  await page.getByRole('button', { name: 'Daily bars', exact: true }).click();
  await page.getByRole('button', { name: '3M', exact: true }).click();
  await page.getByRole('button', { name: 'Replay', exact: true }).click();
  await page.getByRole('toolbar', { name: 'Bar replay' }).getByLabel('Replay date').fill('2026-06-12');
  await expect(page.getByTestId('price-chart')).toHaveAttribute('aria-label', /to 2026-06-12\./);
  await settled(page);
  await shot(page, 'candles-05-replay-before-split-light');
  await page.getByRole('toolbar', { name: 'Bar replay' }).getByRole('button', { name: 'Exit replay', exact: true }).click();
  // The menu theme controls exercise the same persisted preference as a user.
  await page.getByRole('button', { name: 'App menu', exact: true }).click();
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click();
  await page.keyboard.press('Escape');
  await settled(page);
  await shot(page, 'candles-06-daily-3m-dark');
  await page.getByRole('button', { name: 'Weekly bars', exact: true }).click();
  await page.getByRole('button', { name: '1Y', exact: true }).click();
  await settled(page);
  await shot(page, 'candles-07-weekly-1y-dark');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Daily bars', exact: true }).click();
  await page.getByRole('button', { name: '3M', exact: true }).click();
  await settled(page);
  await shot(page, 'candles-09-phone-3m-dark');
  await page.getByRole('button', { name: 'App menu', exact: true }).click();
  await page.getByRole('button', { name: 'Light theme', exact: true }).click();
  await page.keyboard.press('Escape');
  await settled(page);
  await shot(page, 'candles-08-phone-3m-light');
});

test('all nine new drawing tools use the representative synthetic chart in both themes', async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => localStorage.getItem('m25-theme') || localStorage.setItem('m25-theme', 'light'));
  await page.goto('/chart/E2ECANDLE');
  await settled(page);
  const tools: [string, [number, number][], boolean?][] = [
    ['Arrow', [[.05, .1], [.25, .25]]],
    ['Date range', [[.38, .1], [.6, .22]]],
    ['Date and price range', [[.7, .1], [.9, .25]]],
    ['Ellipse', [[.05, .4], [.25, .55]]],
    ['Triangle', [[.38, .55], [.6, .55], [.49, .38]]],
    ['Trend-based Fib extension', [[.68, .6], [.76, .4], [.82, .5]]],
    ['Pitchfork', [[.05, .8], [.15, .7], [.15, .9]]],
    ['Callout', [[.4, .9], [.48, .75]], true],
    ['Price label', [[.75, .85]]],
  ];
  for (const [name, points, note] of tools) {
    await pickTool(page, name);
    const box = (await page.getByTestId('price-chart').boundingBox())!;
    for (const [x, y] of points) await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
    if (note) {
      await page.getByLabel('Annotation text').fill('Synthetic drawing example');
      await page.getByRole('button', { name: 'Save note', exact: true }).click();
    }
  }
  await page.keyboard.press('Escape');
  await expect.poll(async () => {
    const response = await request.get('/api/v1/drawings/E2ECANDLE');
    if (response.status() === 404) return 0; // the first debounced save has not completed
    expect(response.ok()).toBe(true);
    return (await response.json()).body.drawings.length;
  }).toBe(9);
  await settled(page);
  await shot(page, '10-drawing-tools-light');
  await page.getByRole('button', { name: 'App menu', exact: true }).click();
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.reload();
  await settled(page);
  await shot(page, '12-drawing-tools-dark');
});
