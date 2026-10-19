import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, resetDocuments, test } from './fixtures';

const evidence = resolve(process.cwd(), '../audit-evidence/r2');
mkdirSync(evidence, { recursive: true });

test('R2 reduced-motion preference disables smooth scrolling and long CSS transitions', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByRole('navigation').first()).toBeVisible();
  const motion = await page.evaluate(() => ({
    scrollBehavior: getComputedStyle(document.documentElement).scrollBehavior,
    navTransition: getComputedStyle(document.querySelector('nav')!).transitionDuration,
  }));
  expect(motion.scrollBehavior).toBe('auto');
  expect(motion.navTransition.split(',').every((duration) => parseFloat(duration) < 0.01)).toBe(true);
});

test('R2 mobile More menu opens and closes from the keyboard with focus restored', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const more = page.getByRole('button', { name: 'More' });
  await more.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'More' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Close More' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Market' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(more).toBeFocused();
});

test('R2 200% desktop-equivalent reflow keeps core workflows in the viewport', async ({ page }) => {
  resetDocuments(); // an earlier spec can leave the chart on weekly bars or in a grid
  await page.setViewportSize({ width: 720, height: 450 }); // 1440 × 900 desktop at 200% zoom
  for (const [path, heading] of [
    ['/', 'Stock Screener'],
    ['/chart/RELIANCE', 'RELIANCE'],
    ['/studio', 'Strategy Studio'],
  ]) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: heading }).first()).toBeVisible();
    await page.waitForLoadState('networkidle');
    const widths = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(widths.document, `${path} horizontal document overflow at 200% equivalent`).toBeLessThanOrEqual(
      widths.viewport + 2,
    );
    if (path === '/chart/RELIANCE') {
      await expect(page.getByText(/daily bars from the stored NSE series/)).toBeVisible();
      await page.screenshot({ path: resolve(evidence, 'zoom-equivalent-chart-720x450.png') });
    }
  }
});
