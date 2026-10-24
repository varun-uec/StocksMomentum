// Cold mobile LCP, the acceptance review's exact profile (R-02): 390x844 mobile,
// reduced motion, cache disabled, 4x CPU, 150 ms latency, 200,000 B/s down,
// 93,750 B/s up, three cold runs per route. Workspace records are answered in
// memory, as in the review, so no real record is read or written.
// Usage (from web/): [ROUTES=/a,/b] node <this file> [base URL] [output JSON]
const {chromium} = require(process.cwd() + '/node_modules/playwright');
const fs = require('node:fs');

const base = process.argv[2] || 'http://localhost:8000';
const out = process.argv[3];
// ROUTES (comma-separated) measures other pages, such as the stock app's, the same way.
const routes = process.env.ROUTES ? process.env.ROUTES.split(',') : ['/mf', '/mf/funds/122639', '/mf/simulate?code=118987'];

async function measure(browser, route, run) {
  const c = await browser.newContext({
    viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, reducedMotion: 'reduce',
  });
  c.setDefaultTimeout(30000);
  await c.route('**/api/v1/mf/workspace/records**', (r) =>
    r.request().method() === 'GET'
      ? r.fulfill({status: 200, contentType: 'application/json', body: '[]'})
      : r.abort());
  await c.addInitScript(() => {
    window.vitals = {lcp: 0, lcpElement: null, cls: 0, longTasks: []};
    for (const type of ['largest-contentful-paint', 'layout-shift', 'longtask'])
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) {
          if (type === 'largest-contentful-paint') {
            window.vitals.lcp = e.startTime;
            const el = e.element;
            window.vitals.lcpElement = el ? `${el.tagName.toLowerCase()} "${(el.textContent || '').trim().slice(0, 60)}"` : null;
          }
          if (type === 'layout-shift' && !e.hadRecentInput) window.vitals.cls += e.value;
          if (type === 'longtask') window.vitals.longTasks.push(Math.round(e.duration));
        }
      }).observe({type, buffered: true});
  });
  const p = await c.newPage();
  const cdp = await c.newCDPSession(p);
  await cdp.send('Network.enable');
  await cdp.send('Network.setCacheDisabled', {cacheDisabled: true});
  await cdp.send('Emulation.setCPUThrottlingRate', {rate: 4});
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false, latency: 150, downloadThroughput: 200000, uploadThroughput: 93750,
  });
  await p.goto(base + route);
  await p.waitForLoadState('networkidle');
  await p.waitForTimeout(300);
  const perf = await p.evaluate(() => {
    const res = performance.getEntriesByType('resource');
    const js = res.filter((r) => new URL(r.name).pathname.endsWith('.js'));
    return {
      vitals: window.vitals,
      fcp: performance.getEntriesByName('first-contentful-paint')[0]?.startTime ?? null,
      jsDecoded: js.reduce((s, r) => s + r.decodedBodySize, 0),
      jsEncoded: js.reduce((s, r) => s + r.encodedBodySize, 0),
      transferBytes: res.reduce((s, r) => s + r.transferSize, 0),
      requests: res.map((r) => ({
        url: new URL(r.name).pathname + new URL(r.name).search,
        start: Math.round(r.startTime), end: Math.round(r.responseEnd),
        encoded: r.encodedBodySize, decoded: r.decodedBodySize,
      })),
    };
  });
  await c.close();
  console.log(route, run, `LCP ${Math.round(perf.vitals.lcp)} ms`, `CLS ${perf.vitals.cls.toFixed(3)}`,
    `JS ${perf.jsEncoded}/${perf.jsDecoded} B`, perf.vitals.lcpElement);
  return {route, run, ...perf};
}

(async () => {
  const browser = await chromium.launch();
  const results = [];
  for (const route of routes) for (let run = 1; run <= 3; run++) results.push(await measure(browser, route, run));
  await browser.close();
  const median = (xs) => xs.sort((a, b) => a - b)[Math.floor(xs.length / 2)];
  const summary = routes.map((route) => {
    const rs = results.filter((r) => r.route === route);
    return {
      route, lcp: rs.map((r) => Math.round(r.vitals.lcp)), medianLcp: Math.round(median(rs.map((r) => r.vitals.lcp))),
      maxCls: Math.max(...rs.map((r) => r.vitals.cls)), jsEncoded: rs[0].jsEncoded, jsDecoded: rs[0].jsDecoded,
    };
  });
  console.table(summary);
  const profile = '390x844 mobile, reduced motion, cache disabled, 4x CPU, 150 ms latency, 200000 B/s down, 93750 B/s up';
  if (out) fs.writeFileSync(out, JSON.stringify({base, profile, summary, results}, null, 2));
})();
