import { expect, test } from './fixtures';

test('the dashboard shows qualified ranks first and marks filtered names as unranked', async ({ page }) => {
  await page.goto('/');
  const rows = page.getByRole('table').locator('tbody tr');
  await expect(rows).toHaveCount(22);
  await expect(rows.first().locator('td').first()).toHaveText('1');
  await expect(rows.last().locator('td').first()).toHaveText('—');
  await expect(rows.last().locator('td').first().locator('[title="Did not qualify for a rank"]')).toBeVisible();
});

test('the narrow dashboard explains and exposes its horizontally scrollable stock table', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const tableRegion = page.getByRole('region', { name: 'Ranked stock results' });
  await expect(tableRegion).toBeVisible();
  await expect(tableRegion).toHaveAttribute('tabindex', '0');
  await expect(page.getByText('Scroll horizontally to see all columns.')).toBeVisible();
  expect(await tableRegion.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
});
