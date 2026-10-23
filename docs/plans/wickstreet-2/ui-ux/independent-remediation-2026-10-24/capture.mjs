// Captures the served app at port 8000 for the remediation report. Workspace
// calls are answered empty in the browser, so no personal record is read or shown.
import { fileURLToPath, pathToFileURL } from 'node:url';

// Run from web/: node ../docs/.../capture.mjs (Playwright resolves from web/node_modules).
const { chromium } = await import(pathToFileURL(`${process.cwd()}/node_modules/@playwright/test/index.mjs`).href);

const OUT = fileURLToPath(new URL('./screens/', import.meta.url));
const BASE = process.env.BASE ?? 'http://localhost:8000';
const shots = [
  ['discover', '/mf'],
  ['fund-overview', '/mf/funds/122639'],
  ['fund-risk', '/mf/funds/122639?tab=risk'],
  ['fund-performance', '/mf/funds/122639?tab=performance'],
  ['screen', '/mf/screen'],
  ['studio-frontier', '/mf/studio?mode=frontier&code=122639'],
  ['studio-backtest', '/mf/studio?mode=backtest&code=122639'],
  ['compare', '/mf/compare'],
  ['lab-debt', '/mf/simulate?code=118987'],
  ['lab-tax-boundary', '/mf/simulate?kind=lumpsum&code=122639&amount=1000000&start=2023-07-24&end=2024-07-24&tax=equity'],
];
const browser = await chromium.launch();
for (const [mode, viewport] of [['d', { width: 1440, height: 1000 }], ['m', { width: 390, height: 844 }]]) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: mode === 'm' ? 2 : 1, isMobile: mode === 'm', hasTouch: mode === 'm' });
  const page = await context.newPage();
  await page.route('**/api/v1/mf/workspace/records**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '[]' }));
  for (const [name, path] of shots) {
    await page.goto(BASE + path);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}${mode}-${name}-viewport.png` });
    if (mode === 'd') await page.screenshot({ path: `${OUT}${mode}-${name}.png`, fullPage: true });
  }
  await context.close();
}
await browser.close();
