import type { Page } from '@playwright/test';
import { ageAlerts, expect, resetDocuments, test } from './fixtures';

/** M15: daily alerts, set from the chart and listed in the side panel. */

test.beforeEach(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
}

test('an alert set at a chart price is listed, checked, fires, and is seen', async ({ page }) => {
  await page.goto('/chart/TCS');
  await ready(page);
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.3, { button: 'right' });
  await page.getByRole('menuitem', { name: 'Alert at this price…' }).click();

  const panel = page.getByRole('tabpanel', { name: 'Alerts' });
  const form = panel.getByRole('form', { name: 'New alert' });
  await expect(form.getByLabel('Value')).toHaveValue('close');
  await expect(form.getByLabel('Threshold')).toHaveValue(/^\d+\.\d{2}$/); // the price under the menu

  await form.getByLabel('Condition').selectOption('above');
  await form.getByLabel('Threshold').fill('1');
  await form.getByRole('button', { name: 'Add alert' }).click();
  const list = panel.getByRole('list', { name: 'Alerts' });
  await expect(list.getByText('TCS Close is above 1 · Daily')).toBeVisible();
  await expect(list.getByText(/^Watching bars after \d{4}-\d{2}-\d{2}$/)).toBeVisible();

  await form.getByRole('button', { name: 'Check now' }).click();
  await expect(form.getByRole('status')).toHaveText('0 of 1 fired'); // no bar after the last stored session yet

  ageAlerts(); // as if the alert had been set 30 days ago
  await page.getByRole('tab', { name: /^Watchlist/ }).click();
  await page.getByRole('tab', { name: /^Alerts/ }).click();
  await form.getByRole('button', { name: 'Check now' }).click();
  await expect(form.getByRole('status')).toHaveText('1 of 1 fired');
  await expect(list.getByText(/^Fired on \d{4}-\d{2}-\d{2} at \d+\.\d{2}$/)).toBeVisible();
  // The list is open, so the alert is seen at once and no count stays on the tab.
  await expect(page.getByRole('tab', { name: /^Alerts/ }).getByLabel(/new$/)).toHaveCount(0);

  await list.getByRole('button', { name: 'Re-arm' }).click();
  await expect(list.getByText(/^Watching bars after/)).toBeVisible();
  await list.getByRole('button', { name: /^Delete alert/ }).click();
  await expect(panel.getByText('No alerts yet.')).toBeVisible();
});

test('an alert that fired while the list was closed shows a count until it is opened', async ({ page, request }) => {
  const res = await request.post('/api/v1/alerts', {
    data: { symbol: 'INFY', source: 'rsi14', condition: 'above', threshold: '0' },
  });
  expect(res.status()).toBe(201);
  ageAlerts();
  expect((await (await request.post('/api/v1/alerts/evaluate')).json()).fired).toBe(1);

  await page.goto('/chart/INFY');
  await ready(page);
  const tab = page.getByRole('tab', { name: /^Alerts/ });
  await expect(tab.getByLabel('1 new')).toBeVisible();
  await tab.click();
  await expect(page.getByRole('list', { name: 'Alerts' }).getByText('INFY RSI (14) is above 0 · Daily')).toBeVisible();
  await expect(tab.getByLabel('1 new')).toHaveCount(0);
  await expect.poll(async () => (await (await request.get('/api/v1/alerts')).json()).unseen).toBe(0);
});
