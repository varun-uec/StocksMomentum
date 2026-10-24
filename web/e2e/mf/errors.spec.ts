import { expect, test } from '@playwright/test';

test('a stale mutual-fund route chunk has a Wickstreet recovery screen', async ({ page }) => {
  const failed: string[] = [];
  page.on('requestfailed', (request) => failed.push(request.url()));
  await page.route('**/assets/discover-*.js', (route) => route.abort());
  await page.goto('/mf');
  await expect(page.getByRole('heading', { name: 'Wickstreet was updated' })).toBeVisible();
  expect(failed.some((url) => url.includes('/assets/discover-'))).toBe(true);
  await expect(page.getByRole('button', { name: 'Reload Wickstreet' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Momentum25 Stocks' })).toBeVisible();
  await expect(page.getByText('Unexpected Application Error!')).toHaveCount(0);
});

test('a stale stock route chunk has the same recovery screen', async ({ page }) => {
  const failed: string[] = [];
  page.on('requestfailed', (request) => failed.push(request.url()));
  await page.route('**/assets/page-*.js', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Wickstreet was updated' })).toBeVisible();
  expect(failed.some((url) => url.includes('/assets/page-'))).toBe(true);
  await expect(page.getByRole('button', { name: 'Reload Wickstreet' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mutual-fund Discover' })).toBeVisible();
  await expect(page.getByText('Unexpected Application Error!')).toHaveCount(0);
});
