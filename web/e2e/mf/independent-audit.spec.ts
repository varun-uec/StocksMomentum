/**
 * Regression tests for the independent audit of 23 Oct 2026
 * (docs/plans/wickstreet-2/ui-ux/independent-audit-2026-10-23/REPORT.md, section 6).
 * Each test names its finding. Reads use the live snapshot; workspace writes go to
 * the in-memory mock, and failures are injected only in the browser.
 */
import type { Page } from '@playwright/test';
import { FUND, expect, test } from './fixtures';

const pct = (v: number, digits = 1) => `${v < 0 ? '−' : ''}${Math.abs(v * 100).toFixed(digits)}%`;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const day = (iso: string) => `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}`;
const DEBT_FUND = '118987'; // HDFC Corporate Bond Fund Direct Growth
const UNIVERSE = [
  { field: 'status', op: 'in', value: ['active'] },
  { field: 'plan', op: 'in', value: ['direct'] },
  { field: 'option', op: 'in', value: ['growth'] },
];
const encodeView = (view: object) => Buffer.from(JSON.stringify({ v: 1, ...view })).toString('base64url');

test('A-02: the risk chart, its zoom and its table keep the deepest fall', async ({ page, request }) => {
  const uw = await (await request.get(`/api/v1/mf/funds/${FUND}/underwater`)).json();
  const [troughDate, trough] = (uw.series as [string, number][]).reduce((a, b) => (b[1] < a[1] ? b : a));
  await page.goto(`/mf/funds/${FUND}?tab=risk`);
  const frame = page.getByRole('region', { name: 'How far below its peak' });
  await expect(frame).toContainText(`Deepest ${pct(trough)} on ${day(troughDate)}`);
  const chart = frame.getByRole('figure', { name: 'Drawdown from peak over time' });
  await expect(chart.getByText(`Deepest ${pct(trough, 1)} · ${day(troughDate)}`)).toBeVisible();
  // Zoom with the keyboard: the start handle names a date, never a pixel.
  const start = chart.getByRole('slider', { name: /start date$/ });
  await start.focus();
  await page.keyboard.press('PageUp');
  await expect(start).toHaveAttribute('aria-valuetext', /^\d{1,2} [A-Z][a-z]{2} \d{4}$/);
  await expect(chart.getByRole('button', { name: 'Show all dates' })).toBeVisible();
  await frame.getByRole('button', { name: 'Show data table' }).click();
  await expect(frame.getByRole('region', { name: 'Chart data' })).toContainText(day(troughDate));
  await expect(frame.getByRole('region', { name: 'Chart data' })).toContainText(pct(trough));
});

test('A-03: a sale on the 12-month anniversary is short term', async ({ request }) => {
  const run = await (
    await request.post('/api/v1/mf/calculators/lumpsum', { data: { code: FUND, amount: 1_000_000, start: '2023-07-24', end: '2024-07-24', tax_class: 'equity' } })
  ).json();
  const year = run.tax.years[0];
  expect(year.long_term).toBe(0);
  expect(run.tax.total).toBeCloseTo(year.short_term * 0.2 * 1.04, 2);
  expect(run.tax.total).toBeCloseTo(78_245.97, 0);
  const after = await (
    await request.post('/api/v1/mf/calculators/lumpsum', { data: { code: FUND, amount: 1_000_000, start: '2023-07-24', end: '2024-07-25', tax_class: 'equity' } })
  ).json();
  expect(after.tax.years[0].short_term).toBe(0);
});

test('A-04: the lab never taxes a debt fund as equity by default', async ({ page, request }) => {
  const sent = page.waitForRequest((r) => r.url().includes('/calculators/sip') && r.method() === 'POST');
  await page.goto(`/mf/simulate?code=${DEBT_FUND}`);
  const card = page.getByRole('region', { name: 'Tax estimate' });
  await expect(card).toContainText('Debt-oriented · from the fund’s category');
  await expect(card).toContainText('Slab 30%');
  const req = (await sent).postDataJSON();
  expect(req.tax_class).toBeUndefined();
  const api = await (await request.post('/api/v1/mf/calculators/sip', { data: req })).json();
  expect(api.tax.tax_class).toBe('debt');
  await expect(card).toContainText(`₹${Math.round(api.tax.total).toLocaleString('en-IN')}`);
});

test('A-04: a fund whose category does not settle its tax asks for a class', async ({ page, request }) => {
  const hit = (await (await request.get('/api/v1/mf/funds?q=uti%20nifty%2050%20index&limit=5')).json()).funds.find((f: { plan: string; option: string; status: string }) => f.plan === 'direct' && f.option === 'growth' && f.status === 'active');
  await page.goto(`/mf/simulate?code=${hit.amfi_code}`);
  const card = page.getByRole('region', { name: 'Tax estimate' });
  await expect(card).toContainText('Tax class needed');
  await expect(card).toContainText('Choose a tax class');
  await page.getByRole('combobox', { name: 'Tax class' }).selectOption('equity');
  await expect(card).toContainText('Equity-oriented · your choice');
  // A new fund needs its own decision.
  await page.getByRole('button', { name: 'Change fund' }).click();
  await page.getByRole('combobox', { name: 'Fund', exact: true }).fill('122639');
  await page.getByRole('listbox').getByRole('option').first().click();
  await expect(page.getByRole('combobox', { name: 'Tax class' })).toHaveValue('');
});

test('A-05: a saved scenario reopens with every input, on its snapshot or the latest', async ({ page, workspace, request }) => {
  const revision = (await (await request.get('/api/v1/mf/screener/fields')).json()).data_revision;
  expect(typeof revision).toBe('number');
  workspace.records.push({
    id: '00000000-0000-4000-8000-000000000101',
    kind: 'scenario',
    name: 'SIP · step-up test',
    body: {
      kind: 'sip',
      request: { code: FUND, amount: 25_000, day: 15, start: '2019-04-15', end: '2025-10-15', step_up: 0.1, tax_class: 'equity' },
      summary: { invested: 1, value: 2, gain: 1, xirr: 0.1 },
      provenance: { data_revision: revision, method_version: 5, as_of: '2026-10-22', calculator_version: 1, tax_class: 'equity', tax_class_source: 'chosen' },
    },
    schema_version: 1,
    version: 1,
    created_at: '2026-10-23T00:00:00Z',
    updated_at: '2026-10-23T00:00:00Z',
    archived: false,
  });
  await page.goto('/mf/workspace?tab=scenarios');
  await expect(page.getByText(`Ran on snapshot ${revision}`)).toBeVisible();
  await page.getByRole('link', { name: 'Rerun on the latest snapshot' }).click();
  const scenario = page.getByRole('region', { name: 'Scenario' });
  await expect(scenario.getByRole('spinbutton', { name: /Monthly instalment/ })).toHaveValue('25000');
  await expect(scenario.getByRole('spinbutton', { name: 'Day of month' })).toHaveValue('15');
  await expect(scenario.getByRole('spinbutton', { name: 'Yearly step-up (%)' })).toHaveValue('10');
  await expect(scenario.locator('input[type="date"]').first()).toHaveValue('2019-04-15');
  await expect(scenario.locator('input[type="date"]').last()).toHaveValue('2025-10-15');
  await expect(scenario.getByRole('combobox', { name: 'Tax class' })).toHaveValue('equity');
  await page.goBack();
  const replay = page.waitForRequest((r) => r.url().includes('/calculators/sip'));
  await page.getByRole('link', { name: 'Replay on that snapshot' }).click();
  await expect(page.getByText(`Replaying a saved scenario on snapshot ${revision}`)).toBeVisible();
  expect((await replay).postDataJSON().data_revision).toBe(revision);
});

test('A-06: an older query’s results cannot be chosen while the new one is pending', async ({ page }) => {
  await page.route(/\/api\/v1\/mf\/funds\?q=sbi/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    await route.continue();
  });
  await page.goto('/mf');
  const box = page.getByRole('combobox', { name: 'Search funds from the home page' });
  await box.fill('parag');
  await expect(page.getByRole('option').first()).toContainText('Parag Parikh');
  await box.fill('sbi smallcap');
  await page.waitForTimeout(400);
  await expect(page.getByRole('listbox')).toHaveAttribute('aria-busy', 'true');
  await box.press('Enter');
  await page.getByRole('option').first().click({ force: true });
  await expect(page).toHaveURL(/\/mf$/);
  await expect(page.getByRole('option').first()).toContainText('SBI Small Cap', { timeout: 10_000 });
  await box.press('Enter');
  await expect(page).toHaveURL(/\/mf\/funds\/\d+/);
});

test('A-07: a broad AMC query opens on current plans; historical ones are labelled', async ({ page, request }) => {
  const funds = (await (await request.get('/api/v1/mf/funds?q=nippon%20india&limit=8')).json()).funds;
  expect(funds.every((f: { status: string }) => f.status === 'active')).toBe(true);
  expect([funds[0].plan, funds[0].option]).toEqual(['direct', 'growth']);
  await page.goto('/mf');
  const box = page.getByRole('combobox', { name: 'Search funds from the home page' });
  await box.fill('INDIA OPPORTUNITIES FUND SERIES A');
  await expect(page.getByText('Historical plans · no longer published')).toBeVisible();
  await expect(page.getByRole('option').filter({ hasText: 'Historical · last NAV' }).first()).toBeVisible();
});

test('A-08: Match any on a saved nested group keeps a valid filter', async ({ page }) => {
  const view = {
    mode: 'all',
    conditions: [...UNIVERSE, { any: [{ field: 'cagr_3y', op: '>', value: 0.15 }, { field: 'vol_3y', op: '<', value: 0.12 }] }],
    sort: [{ field: 'cagr_3y', dir: 'desc' }],
    columns: ['cagr_3y', 'vol_3y'],
    formulas: {},
  };
  await page.goto(`/mf/screen?v=${encodeView(view)}`);
  const runs: unknown[] = [];
  page.on('request', (r) => r.url().includes('/screener/run') && runs.push(r.postDataJSON().filter));
  await page.getByRole('radio', { name: 'Advanced' }).click();
  await page.getByRole('radio', { name: 'Match any' }).click();
  await expect.poll(() => runs.length).toBeGreaterThan(0);
  const depth = (n: Record<string, unknown>): number => ('field' in n ? 0 : 1 + Math.max(...((n.all ?? n.any) as Record<string, unknown>[]).map(depth)));
  for (const f of runs) expect(depth(f as Record<string, unknown>)).toBeLessThanOrEqual(2);
  await expect(page.getByRole('alert')).toHaveCount(0);
});

const note = (id: string, name: string, text: string) => ({
  id,
  kind: 'note',
  name,
  body: { text },
  schema_version: 1,
  version: 1,
  created_at: '2026-10-23T00:00:00Z',
  updated_at: `2026-10-23T00:00:0${id.slice(-1)}Z`,
  archived: false,
});

test.describe('rename conflict', () => {
  // The lost race is the point of the test: the mock answers 412 once.
  test.use({ allowStatus: [412] });
test('A-09: a rename that loses a race keeps the proposed name', async ({ page, workspace }) => {
  workspace.records.push(note('00000000-0000-4000-8000-000000000201', 'Original name', 'Body'));
  await page.goto('/mf/workspace?tab=notes');
  const name = page.getByRole('textbox', { name: 'Name' });
  await name.fill('My proposed name');
  workspace.forceConflict = true;
  await page.getByRole('button', { name: 'Rename' }).click();
  await expect(page.getByRole('alert')).toContainText('Their version');
  await expect(page.getByRole('button', { name: 'Copy my name' })).toBeVisible();
  await expect(name).toHaveValue('My proposed name');
  await page.getByRole('button', { name: 'Save mine over theirs' }).click();
  await expect(page.getByText(/^Saved · version 3/)).toBeVisible();
  expect(workspace.records[0].name).toBe('My proposed name');
});
});

test.describe('watchlist failure', () => {
  test.use({ allowStatus: [503] });
  test('A-10: a failed watchlist change is shown and can be retried', async ({ page, workspace }) => {
    workspace.records.push({ ...note('00000000-0000-4000-8000-000000000301', 'Core', ''), kind: 'watchlist', body: { codes: [FUND] } });
    let fail = true;
    await page.route('**/api/v1/mf/workspace/records/*', async (route) => {
      if (route.request().method() === 'PUT' && fail) return route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"down"}' });
      return route.fallback();
    });
    await page.goto('/mf/workspace?tab=watchlists');
    await page.getByRole('button', { name: /^Remove / }).click();
    const alert = page.getByRole('alert');
    await expect(alert).toContainText(`Could not remove AMFI ${FUND}`);
    await expect(page.getByText(`Not saved: removing AMFI ${FUND}`)).toBeVisible();
    fail = false;
    await alert.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByText('No funds yet.')).toBeVisible();
  });
});

test('A-11: an unsaved note survives opening another note', async ({ page, workspace }) => {
  workspace.records.push(note('00000000-0000-4000-8000-000000000401', 'Note A', 'Saved A'), note('00000000-0000-4000-8000-000000000402', 'Note B', 'Saved B'));
  await page.goto('/mf/workspace?tab=notes');
  const list = page.getByRole('complementary').filter({ has: page.getByRole('button', { name: /Note A/ }) });
  await list.getByRole('button', { name: /Note A/ }).click();
  await expect(page.getByRole('textbox', { name: 'Note', exact: true })).toHaveValue('Saved A');
  await page.getByRole('textbox', { name: 'Note', exact: true }).fill('Draft A, not saved');
  await list.getByRole('button', { name: /Note B/ }).click();
  await expect(page.getByRole('textbox', { name: 'Note', exact: true })).toHaveValue('Saved B');
  await expect(list.getByRole('button', { name: /Note A/ })).toContainText('Unsaved draft');
  await list.getByRole('button', { name: /Note A/ }).click();
  await expect(page.getByRole('textbox', { name: 'Note', exact: true })).toHaveValue('Draft A, not saved');
});

test('A-12: chart focus is visible to keyboard users', async ({ page }) => {
  await page.goto(`/mf/funds/${FUND}?tab=performance`);
  const surface = page.locator('.recharts-surface[tabindex="0"]').first();
  await surface.focus();
  await page.keyboard.press('ArrowRight');
  expect(await surface.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none');
});

test('A-13: the comparison table uses the chart’s rupees', async ({ page }) => {
  await page.goto('/mf/compare');
  const frame = page.getByRole('region', { name: /^Growth of ₹10,000/ });
  await frame.getByRole('button', { name: 'Show data table' }).click();
  const first = frame.getByRole('region', { name: 'Chart data' }).locator('tbody tr').first();
  await expect(first).toContainText('₹10,000');
  await expect(first).not.toContainText(/\b100\.0\b/);
});

test('A-14: backtest growth starts at 100 and books each month at its realised end', async ({ page }) => {
  await page.goto(`/mf/studio?mode=backtest&code=${FUND}`);
  const frame = page.getByRole('region', { name: /Growth of 100/ });
  await frame.getByRole('button', { name: 'Show data table' }).click();
  const row = frame.getByRole('region', { name: 'Chart data' }).locator('tbody tr').first();
  const cells = await row.locator('td').allTextContents();
  const [mon, year] = cells[0].split(' ');
  const next = new Date(Date.UTC(Number(year), MONTHS.indexOf(mon) + 2, 0)).toISOString().slice(0, 10);
  expect(cells[1]).toBe(day(next));
});

test('A-15: sections from two snapshots raise a warning', async ({ page }) => {
  await page.route(`**/api/v1/mf/funds/${FUND}/score**`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, data_revision: body.data_revision - 1 } });
  });
  await page.goto(`/mf/funds/${FUND}`);
  const banner = page.getByRole('alert').filter({ hasText: 'New data was published while this page loaded' });
  await expect(banner).toBeVisible();
  await page.unroute(`**/api/v1/mf/funds/${FUND}/score**`);
  await banner.getByRole('button', { name: 'Refresh every section' }).click();
  await expect(banner).toHaveCount(0);
});

async function firstViewportShows(page: Page, name: RegExp | string) {
  await expect(page.getByRole('heading', { name }).first()).toBeInViewport();
}

test('Discover answers a question in the first desktop viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/mf');
  await firstViewportShows(page, 'Ideas to research');
  await expect(page.getByRole('complementary', { name: 'Market today' })).toBeInViewport();
});

test.describe('phone', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

  test('the lab shows its result before the form on a phone', async ({ page }) => {
    await page.goto(`/mf/simulate?code=${FUND}`);
    await expect(page.getByText('XIRR', { exact: true }).first()).toBeInViewport();
    await expect(page.getByRole('link', { name: /Edit inputs/ })).toBeVisible();
  });

  test('fund tabs other than Overview use a compact header', async ({ page }) => {
    await page.goto(`/mf/funds/${FUND}?tab=risk`);
    await expect(page.getByRole('heading', { name: 'How far below its peak' })).toBeInViewport();
  });

  test('information buttons have a 44 px touch area', async ({ page }) => {
    await page.goto(`/mf/funds/${FUND}`);
    const tip = page.getByRole('button', { name: /^About / }).first();
    const size = await tip.evaluate((el) => {
      const r = getComputedStyle(el, '::before');
      return el.getBoundingClientRect().height - parseFloat(r.top) - parseFloat(r.bottom);
    });
    expect(size).toBeGreaterThanOrEqual(44);
  });
});
