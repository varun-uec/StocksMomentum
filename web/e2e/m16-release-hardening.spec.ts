import { expect, test } from './fixtures';

test('the default data screen explains the authorized offline import workflow', async ({ page, request }) => {
  const policy = await (await request.get('/api/v1/market-data/status')).json();
  expect(policy).toEqual({
    direct_exchange_downloads_enabled: false,
    authorized_csv_import_supported: true,
  });

  await page.goto('/data');
  await expect(page.getByRole('heading', { name: 'Market Data', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Authorized CSV import' })).toBeVisible();
  await expect(page.getByText('Direct exchange downloads are disabled.')).toBeVisible();
  await expect(page.getByText('source ../.env')).toBeVisible();
  await expect(page.getByText(/momentum25 import-eod bars.csv --actions corporate-actions.csv/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Refresh Latest Market Data' })).toHaveCount(0);
  await page.screenshot({
    path: '../audit-evidence/screenshots/data-authorized-import-desktop.png',
    fullPage: true,
  });
});
