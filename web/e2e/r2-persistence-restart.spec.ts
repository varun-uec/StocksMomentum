import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, openPanelTab, resetDocuments, test } from './fixtures';

const evidence = resolve(process.cwd(), '../audit-evidence/r2');
mkdirSync(evidence, { recursive: true });

test('R2 phase 1 writes chart, drawing and alert state before the isolated database restart', async ({ page, request }) => {
  resetDocuments();
  await page.goto('/chart/TCS');
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
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

  await openPanelTab(page, /^Alerts/);
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
  await page.screenshot({ path: resolve(evidence, 'database-restart-before.png') });
});

test('R2 phase 2 restores state after PostgreSQL and API process restart', async ({ page, request }) => {
  await page.goto('/chart/TCS');
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);

  const workspace = await (await request.get('/api/v1/workspaces/default')).json();
  expect(workspace.body.charts.main).toMatchObject({ symbol: 'TCS', interval: '1W', range: '3M' });
  await expect(page.getByRole('button', { name: 'Weekly bars' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: '3M', exact: true })).toHaveAttribute('aria-pressed', 'true');

  const drawings = await (await request.get('/api/v1/drawings/TCS')).json();
  expect(drawings.body.drawings).toHaveLength(1);
  expect(drawings.body.drawings[0].kind).toBe('hline');
  await expect(page.getByTestId('price-chart').locator('canvas').first()).toBeVisible();

  const alerts = await (await request.get('/api/v1/alerts')).json();
  expect(alerts.alerts).toHaveLength(1);
  expect(alerts.alerts[0]).toMatchObject({ symbol: 'TCS', status: 'active' });
  await openPanelTab(page, /^Alerts/);
  await expect(page.getByRole('list', { name: 'Alerts' }).getByText('TCS Close is above 1 · Daily')).toBeVisible();
  await page.screenshot({ path: resolve(evidence, 'database-restart-restored.png') });
});
