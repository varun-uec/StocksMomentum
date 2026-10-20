import type { Page } from '@playwright/test';
import { ageAlerts, expect, openPanelTab, resetDocuments, test } from './fixtures';

/** B4 (plan 2026-10-19): "Alert on this line…" arms an EOD close alert on a saved ray, and it fires where the ADR rule says. */

test.beforeEach(() => resetDocuments());

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
}

/** The ADR-013 line amendment, restated as the test's oracle: first close cross of the line after arming. */
function firstCross(dates: string[], closes: number[], anchors: [number, number][], armedAfter: string): string | null {
  const [[ia, pa], [ib, pb]] = anchors;
  const level = (i: number) => (i >= ia ? pa + ((pb - pa) * (i - ia)) / (ib - ia) : null);
  for (let i = 1; i < dates.length; i += 1) {
    const [lp, lc] = [level(i - 1), level(i)];
    if (dates[i] > armedAfter && lp !== null && lc !== null && closes[i - 1] <= lp && closes[i] > lc) return dates[i];
  }
  return null;
}

test('Alert on this line… arms a ray alert from the drawing menu; it fires on the first close above the ray', async ({ page, request }) => {
  const ohlcv = await (await request.get('/api/v1/securities/TCS/ohlcv')).json();
  // TCS has no corporate action, so its traded and chart prices are one basis.
  expect(ohlcv.adjustments.every((s: { factor: string }) => Number(s.factor) === 1)).toBe(true);
  const dates: string[] = ohlcv.bars.map((b: { date: string }) => b.date);
  const closes: number[] = ohlcv.bars.map((b: { close: string }) => Number(b.close));
  // A ray rising more slowly than one recent up day, meeting the close the session before it.
  const j = dates.findIndex((_, i) => i > dates.length - 15 && closes[i] > closes[i - 1]);
  expect(j).toBeGreaterThan(0);
  const slope = Number(((closes[j] - closes[j - 1]) / 4).toFixed(4));
  const anchors: [number, number][] = [[j - 6, Number((closes[j - 1] - 5 * slope).toFixed(4))], [j - 1, closes[j - 1]]];
  expect((await request.put('/api/v1/drawings/TCS', {
    headers: { 'If-None-Match': '*' },
    data: { drawings: [{ id: 'watch-ray', kind: 'ray', color: '#6366f1', points: anchors.map(([i, price]) => ({ date: dates[i], price })) }] },
  })).status()).toBe(201);

  await page.goto('/chart/TCS'); await ready(page);
  await openPanelTab(page, 'Object tree');
  await page.getByRole('tabpanel', { name: 'Object tree' }).getByRole('button', { name: 'Ray', exact: true }).click();
  await page.getByRole('menu', { name: 'Drawing' }).getByRole('menuitem', { name: 'Alert on this line…' }).click();

  const panel = page.getByRole('tabpanel', { name: 'Alerts' });
  const form = panel.getByRole('form', { name: 'New alert' });
  await expect(form.getByLabel('Alert drawing')).toHaveValue('watch-ray');
  await expect(form.getByLabel('Condition')).toHaveValue('crosses_above');
  await expect(form).toContainText('A ray watches from its first anchor onward');
  await form.getByRole('button', { name: 'Add alert' }).click();
  const list = panel.getByRole('list', { name: 'Alerts' });
  await expect(list.getByText('TCS Close crosses above the ray · Daily')).toBeVisible();

  const [armed] = (await (await request.get('/api/v1/alerts')).json()).alerts;
  expect(armed.drawing).toMatchObject({ id: 'watch-ray', kind: 'ray', revision: 1 });

  // Snapshot freeze: moving the saved ray does not change the armed rule.
  expect((await request.put('/api/v1/drawings/TCS', {
    headers: { 'If-Match': '"1"' },
    data: { drawings: [{ id: 'watch-ray', kind: 'ray', color: '#6366f1', points: anchors.map(([i, price]) => ({ date: dates[i], price: price + 1000 })) }] },
  })).status()).toBe(200);

  ageAlerts(); // as if armed 30 days ago, so the stored bars can fire it
  const [aged] = (await (await request.get('/api/v1/alerts')).json()).alerts;
  const expected = firstCross(dates, closes, anchors, aged.armed_after);
  expect(expected).not.toBeNull();
  await openPanelTab(page, /^Watchlist/);
  await openPanelTab(page, /^Alerts/);
  await form.getByRole('button', { name: 'Check now' }).click();
  await expect(form.getByRole('status', { name: 'Alert evaluation' })).toHaveText('1 of 1 fired');
  const [fired] = (await (await request.get('/api/v1/alerts')).json()).alerts;
  expect(fired.triggered_on).toBe(expected);
  expect(Number(fired.trigger_value)).toBe(closes[dates.indexOf(expected!)]);
  expect(fired.drawing.points.map((p: { price: string }) => Number(p.price))).toEqual(anchors.map(([, price]) => price));
});
