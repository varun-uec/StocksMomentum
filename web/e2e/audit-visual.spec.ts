import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chooseLayout, expect, openAppMenu, openPanelTab, resetDocuments, test } from './fixtures';

/** Browser-rendered evidence for the product audit; these tests do not mutate user data. */
const screenshots = resolve(process.cwd(), '../audit-evidence/screenshots');
mkdirSync(screenshots, { recursive: true });

test.beforeEach(() => resetDocuments());

const ROUTES: [string, string][] = [
  ['dashboard', '/'],
  ['chart-entry', '/chart'],
  ['chart', '/chart/RELIANCE'],
  ['stock-detail', '/stock/RELIANCE'],
  ['stock-analysis', '/stock/RELIANCE/analysis'],
  ['elliott-wave', '/stock/RELIANCE/elliott-wave'],
  ['watchlist', '/watchlist'],
  ['market', '/market'],
  ['strategies', '/strategies'],
  ['studio', '/studio'],
  ['validation', '/validation'],
  ['backtest', '/backtest'],
  ['historical', '/historical'],
  ['experiment', '/experiment'],
  ['analytics', '/analytics'],
  ['data', '/data'],
  ['learn', '/learn'],
  ['learn-momentum-investing', '/learn/momentum-investing'],
  ['learn-minervini-methodology', '/learn/minervini-methodology'],
  ['learn-momentum25-methodology', '/learn/momentum25-methodology'],
  ['learn-scoring-guide', '/learn/scoring-guide'],
  ['learn-rule-guide', '/learn/rule-guide'],
  ['learn-faq', '/learn/faq'],
  ['about', '/about'],
  ['chart-grid-diagnostic', '/lab/chart-grid?n=4&symbol=RELIANCE'],
  ['not-found', '/audit-missing-route'],
];

for (const [name, route] of ROUTES) {
  test(`audit screenshot: ${name}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(route);
    if (name === 'chart-grid-diagnostic') {
      await expect(page.getByTestId('chart-cell')).toHaveCount(4);
    } else {
      await expect(page.locator('h1').first()).toBeVisible();
    }
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: join(screenshots, `${name}-desktop.png`), fullPage: true });
  });
}

test('audit screenshots: chart search and indicator catalogue', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/chart/RELIANCE');
  await expect(page.getByTestId('price-chart').first()).toBeVisible();
  await page.keyboard.press('Control+k');
  const search = page.getByRole('dialog', { name: 'Search symbols' });
  await expect(search).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'chart-search-desktop.png') });
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: /^Indicators/ }).click();
  await expect(page.getByRole('dialog', { name: 'Indicators' })).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'chart-indicators-desktop.png') });
  await page.keyboard.press('Escape');
  await openPanelTab(page, /^Alerts/);
  await expect(page.getByRole('tabpanel', { name: 'Alerts' })).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'chart-alerts-desktop.png') });
});

test('audit screenshots: dark desktop and mobile navigation', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await expect(page.getByText('Ranked Universe')).toBeVisible();
  await page.locator('tbody tr').first().getByRole('button').first().click();
  await expect(page.getByText('Gate failures')).toBeVisible();
  await (await openAppMenu(page)).getByRole('button', { name: 'Dark theme' }).click();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await page.screenshot({ path: join(screenshots, 'dashboard-dark-desktop.png'), fullPage: true });

  await (await openAppMenu(page)).getByRole('button', { name: 'Light theme' }).click();
  await expect(page.locator('html')).not.toHaveClass(/dark/);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await expect(page.getByText('Ranked Universe')).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'dashboard-mobile.png'), fullPage: true });
  await page.getByRole('button', { name: 'More' }).click();
  await expect(page.getByRole('dialog', { name: 'More' })).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'mobile-more-menu.png') });
});

test('audit screenshots: 2 × 2 and 4 × 4 chart workspaces', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/chart/RELIANCE');
  await chooseLayout(page, '2x2');
  await expect(page.getByRole('region', { name: /^Chart / })).toHaveCount(4);
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length >= 4);
  await page.screenshot({ path: join(screenshots, 'chart-grid-4-desktop.png'), fullPage: true });
  await chooseLayout(page, '4x4');
  await expect(page.getByRole('region', { name: /^Chart / })).toHaveCount(16);
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length >= 16, undefined, { timeout: 60_000 });
  await page.screenshot({ path: join(screenshots, 'chart-grid-16-desktop.png'), fullPage: true });
});

test('audit screenshot: strategy studio on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/studio');
  await expect(page.getByRole('heading', { name: 'Families' })).toBeVisible();
  if (await page.getByText('No families yet').isVisible()) {
    await page.screenshot({ path: join(screenshots, 'studio-desktop.png'), fullPage: true });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/studio');
  await expect(page.locator('h1').first()).toBeVisible();
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('heading', { name: 'Families' })).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'studio-mobile.png'), fullPage: true });
  await page.screenshot({ path: join(screenshots, 'studio-mobile-viewport.png') });
});

test('audit screenshot: chart on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/chart/RELIANCE');
  await expect(page.getByTestId('price-chart').first()).toBeVisible();
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: join(screenshots, 'chart-mobile.png'), fullPage: true });
  await page.screenshot({ path: join(screenshots, 'chart-mobile-viewport.png') });
});

test('audit screenshot: mobile chart status clears the fixed navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/chart/RELIANCE');
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  const status = page.getByText(/daily bars from the stored NSE series/);
  await expect(status).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const primaryNav = page.getByRole('navigation', { name: 'Primary' });
  await expect.poll(async () => {
    const statusBox = await status.boundingBox();
    const navBox = await primaryNav.boundingBox();
    return !!statusBox && !!navBox && statusBox.y + statusBox.height <= navBox.y;
  }).toBe(true);
  await page.screenshot({ path: join(screenshots, 'chart-mobile-bottom-content.png') });
});
