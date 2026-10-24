// Before/after screens for the premium transformation: 7 routes × desktop/phone × light/dark.
// Run from web/: node ../docs/plans/wickstreet-2/ui-ux/premium-2026-10-24/scripts/capture.cjs <before|after> [route-filter]
// Workspace records are mocked empty, so no personal record appears.
const { chromium } = require(process.cwd() + '/node_modules/playwright');
const path = require('node:path');
const fs = require('node:fs');
const variant = process.argv[2] ?? 'after';
const only = process.argv[3];
const out = path.resolve(__dirname, '..', 'screens', variant);
fs.mkdirSync(out, { recursive: true });
const base = process.env.MF_BASE_URL ?? 'http://localhost:8000';
const ROUTES = [
  ['discover', '/mf'],
  ['screener', '/mf/screen'],
  ['fund', '/mf/funds/122639'],
  ['compare', '/mf/compare?code=122639&code=118955'],
  ['portfolio', '/mf/portfolio'],
  ['studio', '/mf/studio?code=122639'],
  ['lab', '/mf/simulate?code=122639'],
];
const VIEWS = [['d', { width: 1440, height: 1000 }], ['m', { width: 390, height: 844 }]];
(async () => {
  const b = await chromium.launch();
  for (const [name, url] of ROUTES.filter(([n]) => !only || n === only))
    for (const [v, viewport] of VIEWS)
      for (const theme of ['light', 'dark']) {
        const c = await b.newContext({ viewport, reducedMotion: 'reduce', deviceScaleFactor: v === 'm' ? 2 : 1 });
        await c.addInitScript((mode) => localStorage.setItem('m25-theme', mode), theme);
        await c.route('**/api/v1/mf/workspace/records**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '[]' }));
        const p = await c.newPage();
        await p.goto(base + url);
        await p.waitForLoadState('networkidle');
        await p.waitForTimeout(400);
        await p.evaluate(() => scrollTo(0, 0));
        await p.screenshot({ path: path.join(out, `${v}-${name}-${theme}.png`) });
        await c.close();
      }
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
