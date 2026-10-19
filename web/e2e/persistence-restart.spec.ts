import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';

async function chartReady(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
}

test('phase 1 writes chart, drawing and alert state in the browser', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await chartReady(page);
  await page.getByRole('button', { name: 'Weekly bars' }).click();
  await page.getByRole('button', { name: '3M', exact: true }).click();

  const chart = page.getByTestId('price-chart');
  const box = (await chart.boundingBox())!;
  await page.getByRole('toolbar', { name: 'Drawing tools' }).getByRole('button', { name: 'Horizontal line', exact: true }).click();
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.4);
  await expect.poll(async () => {
    const response = await request.get('/api/v1/drawings/TCS');
    return response.ok() ? (await response.json()).body.drawings.length : -1;
  }).toBe(1);

  await page.getByRole('tab', { name: /^Alerts/ }).click();
  const form = page.getByRole('form', { name: 'New alert' });
  await form.getByLabel('Value').selectOption('close');
  await form.getByLabel('Condition').selectOption('above');
  await form.getByLabel('Threshold').fill('1');
  await form.getByRole('button', { name: 'Add alert' }).click();
  await expect(page.getByRole('list', { name: 'Alerts' }).getByText('TCS Close is above 1 · Daily')).toBeVisible();

  const workspace = await (await request.get('/api/v1/workspaces/default')).json();
  expect(workspace.body.charts.main).toMatchObject({ symbol: 'TCS', interval: '1W', range: '3M' });
  const alerts = await (await request.get('/api/v1/alerts')).json();
  expect(alerts.alerts).toHaveLength(1);
  expect(alerts.alerts[0]).toMatchObject({ symbol: 'TCS', status: 'active' });
});

test('phase 2 recovers chart, drawing and alert state after database and app restarts', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await chartReady(page);

  const workspace = await (await request.get('/api/v1/workspaces/default')).json();
  expect(workspace.body.charts.main).toMatchObject({ symbol: 'TCS', interval: '1W', range: '3M' });
  const drawings = await (await request.get('/api/v1/drawings/TCS')).json();
  expect(drawings.body.drawings).toHaveLength(1);
  expect(drawings.body.drawings[0].kind).toBe('hline');
  const alerts = await (await request.get('/api/v1/alerts')).json();
  expect(alerts.alerts).toHaveLength(1);
  expect(alerts.alerts[0]).toMatchObject({ symbol: 'TCS', status: 'active' });
});
