import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from './fixtures';

const EVIDENCE = resolve(process.cwd(), '../audit-evidence/final-stabilisation');

test('primary dashboard, chart and studio views have no WCAG A/AA axe violations', async ({ page }) => {
  mkdirSync(EVIDENCE, { recursive: true });
  await page.addInitScript({
    path: resolve(process.cwd(), 'node_modules/axe-core/axe.min.js'),
  });
  const reports: { path: string; violations: unknown[] }[] = [];

  for (const path of ['/', '/chart/RELIANCE', '/studio']) {
    for (const theme of ['light', 'dark'] as const) {
      await page.goto(path);
      await page.evaluate((mode) => localStorage.setItem('m25-theme', mode), theme);
      await page.reload();
      await page.evaluate(
        (dark) => document.documentElement.classList.toggle('dark', dark),
        theme === 'dark',
      );
      if (path === '/chart/RELIANCE') {
        await page.waitForFunction(
          () => performance.getEntriesByName('wickstreet:chart-painted').length > 0,
        );
      } else {
        await expect(page.getByRole('main')).toBeVisible();
      }
      const violations = await page.evaluate(async () => {
        const axe = (window as unknown as {
          axe: {
            run: (
              doc: Document,
              options: object,
            ) => Promise<{ violations: unknown[] }>;
          };
        }).axe;
        const result = await axe.run(document, {
          runOnly: {
            type: 'tag',
            values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'],
          },
        });
        return result.violations;
      });
      reports.push({ path: `${path} (${theme})`, violations });
    }
  }

  writeFileSync(resolve(EVIDENCE, 'accessibility-axe.json'), JSON.stringify(reports, null, 2));
  expect(reports, 'axe violations by primary route').toEqual(
    reports.map((report) => ({ ...report, violations: [] })),
  );
});

test('keyboard-only chart controls expose focus, names, and Escape recovery', async ({ page }) => {
  await page.goto('/chart/RELIANCE');
  await page.waitForFunction(
    () => performance.getEntriesByName('wickstreet:chart-painted').length > 0,
  );

  const chart = page.getByTestId('price-chart').first();
  await chart.focus();
  await page.keyboard.press('Alt+t');
  const tools = page.getByRole('toolbar', { name: 'Drawing tools' });
  await expect(tools.getByRole('button', { name: 'Trendline' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.keyboard.press('Escape');
  await expect(tools.getByRole('button', { name: 'Select' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );

  await page.keyboard.press('?');
  const dialog = page.getByRole('dialog', { name: 'Keyboard shortcuts' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('rowheader', { name: 'Alt+W' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Close' })).toBeFocused();
  const focusRing = await dialog
    .getByRole('button', { name: 'Close' })
    .evaluate((element) => getComputedStyle(element).boxShadow);
  expect(focusRing).not.toBe('none');
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(chart).toBeFocused();
});
