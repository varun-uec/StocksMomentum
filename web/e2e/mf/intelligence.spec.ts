/**
 * Fund facts, benchmark, holdings, overlap and portfolio screens (doc 21 C12, C14–C16,
 * C25). Each test reads the live API first and checks the screen shows the same value.
 */
import { FUND, OTHER, expect, expectNoSideScroll, test } from './fixtures';

const pct = (v: number, digits = 1) => `${v < 0 ? '−' : ''}${Math.abs(v * 100).toFixed(digits)}%`;
const filedDate = (value: unknown) => {
  if (typeof value !== 'string') return '—';
  const [year, month, day] = value.slice(0, 10).split('-');
  return `${Number(day)} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][Number(month) - 1]} ${year}`;
};
const DSP_FLEXI = '119076'; // DSP Flexi Cap Fund Direct Growth: DSP files its portfolio monthly
const PRIOR_SNAPSHOT = 5891; // A retained method-v8 snapshot in the local research store.

test('Facts & costs shows AMFI’s TER and the fund managers as filed', async ({ page, request }) => {
  const metrics = await (await request.get(`/api/v1/mf/funds/${FUND}/metrics`)).json();
  const profile = await (await request.get(`/api/v1/mf/funds/${FUND}/profile`)).json();
  await page.goto(`/mf/funds/${FUND}?tab=facts`);
  await expect(page.getByText('Expense ratio', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(pct(metrics.values.ter, 2)).first()).toBeVisible();
  await expect(page.getByText(`AMFI as of ${filedDate(profile.summary.ter_as_of)}`, { exact: false })).toBeVisible();
  expect(Date.parse(profile.riskometer_as_of)).toBeGreaterThan(Date.parse(profile.riskometer.at(-1)[0]));
  await expect(page.getByText(`AMFI as of ${filedDate(profile.riskometer_as_of)}`, { exact: false })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Expense ratio over time' })).toBeVisible();
  await expect(page.getByText(profile.managers[0].name).first()).toBeVisible();
});

test('Compare includes TER and states the NAV snapshot date', async ({ page, request }) => {
  const comparison = await (await request.get(`/api/v1/mf/compare?code=${FUND}&code=${OTHER}`)).json();
  await page.goto(`/mf/compare?code=${FUND}&code=${OTHER}`);
  await expect(page.getByRole('region', { name: 'Metric comparison' })).toBeVisible();
  await page.getByText('Costs and size', { exact: true }).scrollIntoViewIfNeeded();
  const terRow = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'TER', exact: true }) });
  await expect(terRow).toContainText(pct(comparison.funds[0].values.ter, 2));
  await expect(terRow).toContainText(pct(comparison.funds[1].values.ter, 2));
  await expect(page.getByText(`NAV data as of ${filedDate(comparison.as_of)}`, { exact: false })).toBeVisible();
});

test('Compare preserves its window and pinned snapshot through browser navigation', async ({ page, request }) => {
  const codes = [FUND, OTHER, DSP_FLEXI];
  const codeQuery = codes.map((code) => `code=${code}`).join('&');
  const latest = await (await request.get(`/api/v1/mf/compare?${codeQuery}`)).json();
  const prior = await (await request.get(`/api/v1/mf/compare?${codeQuery}&data_revision=${PRIOR_SNAPSHOT}`)).json();
  const revision = prior.data_revision as number;
  expect(revision).toBe(PRIOR_SNAPSHOT);
  expect(latest.data_revision).toBeGreaterThan(revision);
  const pinnedRequest = page.waitForRequest((r) => {
    const url = new URL(r.url());
    return url.pathname.endsWith('/api/v1/mf/compare') && url.searchParams.get('data_revision') === String(revision);
  });
  const pinnedOverlapRequest = page.waitForRequest((r) => {
    const url = new URL(r.url());
    return url.pathname.endsWith('/api/v1/mf/holdings/overlap') && url.searchParams.get('data_revision') === String(revision);
  });
  await page.goto(`/mf/compare?${codeQuery}&rev=${revision}`);
  await Promise.all([pinnedRequest, pinnedOverlapRequest]);
  await expect(page.getByText(`snapshot ${revision}`, { exact: false })).toBeVisible();

  const window = page.getByRole('radiogroup', { name: 'Window' });
  await expect(window.getByRole('radio', { name: 'All' })).toHaveAttribute('aria-checked', 'true');
  await window.getByRole('radio', { name: '3Y' }).click();
  await expect(page).toHaveURL(new RegExp(`period=3Y.*rev=${revision}|rev=${revision}.*period=3Y`));
  await window.getByRole('radio', { name: '5Y' }).click();
  await expect(window.getByRole('radio', { name: '5Y' })).toHaveAttribute('aria-checked', 'true');

  await page.goBack();
  await expect(window.getByRole('radio', { name: '3Y' })).toHaveAttribute('aria-checked', 'true');
  expect(new URL(page.url()).searchParams.get('rev')).toBe(String(revision));
  await page.goForward();
  await expect(window.getByRole('radio', { name: '5Y' })).toHaveAttribute('aria-checked', 'true');
  expect(new URL(page.url()).searchParams.get('rev')).toBe(String(revision));
  await page.reload();
  await expect(window.getByRole('radio', { name: '5Y' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByText(`snapshot ${revision}`, { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Remove condition' }).nth(2).click();
  const afterRemoval = new URL(page.url());
  expect(afterRemoval.searchParams.getAll('code')).toEqual(codes.slice(0, 2));
  expect(afterRemoval.searchParams.get('period')).toBe('5Y');
  expect(afterRemoval.searchParams.get('rev')).toBe(String(revision));

  const end = prior.series[FUND].at(-1)[0] as string;
  const start = `${Number(end.slice(0, 4)) - 5}${end.slice(4)}`;
  const labLink = page.getByRole('link', { name: 'Test an investment' });
  const href = await labLink.getAttribute('href');
  expect(href).not.toBeNull();
  const handoff = new URL(href!, 'http://localhost');
  expect(handoff.pathname).toBe('/mf/simulate');
  expect(handoff.searchParams.get('code')).toBe(FUND);
  expect(handoff.searchParams.get('rev')).toBe(String(revision));
  expect(handoff.searchParams.get('start')).toBe(start);
  expect(handoff.searchParams.get('end')).toBe(end);

  const pinnedMetrics = page.waitForRequest((r) => {
    const url = new URL(r.url());
    return url.pathname.endsWith(`/api/v1/mf/funds/${FUND}/metrics`) && url.searchParams.get('data_revision') === String(revision);
  });
  const pinnedCalculation = page.waitForRequest((r) => {
    const url = new URL(r.url());
    return url.pathname.endsWith('/api/v1/mf/calculators/sip') && r.method() === 'POST' && r.postDataJSON()?.data_revision === revision;
  });
  await labLink.click();
  await Promise.all([pinnedMetrics, pinnedCalculation]);
  await expect(page).toHaveURL(new RegExp(`/mf/simulate\\?code=${FUND}.*rev=${revision}`));
  const dateInputs = page.locator('input[type="date"]');
  await expect(dateInputs.nth(0)).toHaveValue(start);
  await expect(dateInputs.nth(1)).toHaveValue(end);
});

test('Compare default funds do not discard a URL period or snapshot pin', async ({ page }) => {
  await page.goto(`/mf/compare?period=5Y&rev=${PRIOR_SNAPSHOT}`);
  const window = page.getByRole('radiogroup', { name: 'Window' });
  await expect(window.getByRole('radio', { name: '5Y' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByText(`snapshot ${PRIOR_SNAPSHOT}`, { exact: false })).toBeVisible();
  const resolved = new URL(page.url());
  expect(resolved.searchParams.getAll('code').length).toBeGreaterThanOrEqual(2);
  expect(resolved.searchParams.get('period')).toBe('5Y');
  expect(resolved.searchParams.get('rev')).toBe(String(PRIOR_SNAPSHOT));
});

test('Benchmark labels its proxy and links to the index fund behind it', async ({ page, request }) => {
  const bench = await (await request.get(`/api/v1/mf/funds/${FUND}/benchmark`)).json();
  await page.goto(`/mf/funds/${FUND}?tab=benchmark`);
  await expect(page.getByText(`Against ${bench.benchmark}`)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('Proxy', { exact: true })).toBeVisible();
  expect(bench.proxy, 'the Nifty 500 TRI has index funds with 3 years of NAVs').not.toBeNull();
  await page.getByRole('link', { name: bench.proxy.name }).click();
  await expect(page).toHaveURL(new RegExp(`/mf/funds/${bench.proxy.code}`));
});

test('Holdings shows the latest filed portfolio, largest line first', async ({ page, request }) => {
  const holdings = await (await request.get(`/api/v1/mf/funds/${FUND}/holdings`)).json();
  await page.goto(`/mf/funds/${FUND}?tab=holdings`);
  await expect(page.getByText(/^Portfolio of /)).toBeVisible();
  await expect(page.getByText(holdings.lines[0].name).first()).toBeVisible();
  await expect(page.getByText('What changed')).toBeVisible();
});

test('Compare shows the weighted overlap of two filed portfolios', async ({ page, request }) => {
  const overlap = await (await request.get(`/api/v1/mf/holdings/overlap?code=${FUND}&code=${DSP_FLEXI}`)).json();
  const share = overlap.pairs[0].weighted_overlap as number;
  await page.goto(`/mf/compare?code=${FUND}&code=${DSP_FLEXI}`);
  const card = page.getByText('Do they own the same securities?');
  await card.scrollIntoViewIfNeeded();
  await expect(page.getByText(`${pct(share)}`, { exact: true })).toBeVisible();
});

test('Portfolio offers a local CAS import and is not marked planned', async ({ page }) => {
  await page.goto('/mf/portfolio');
  await expect(page.getByText('Import a consolidated account statement')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Portfolio', exact: true })).toBeVisible();
});

test.describe('on a phone', () => {
  test.use({ viewport: { width: 375, height: 812 } });

  for (const [tab, code, text] of [
    ['facts', FUND, 'Expense ratio over time'],
    ['benchmark', FUND, 'Risk against the benchmark'],
    ['holdings', DSP_FLEXI, 'What changed'],
  ] as const) {
    test(`the ${tab} tab does not scroll sideways`, async ({ page }) => {
      await page.goto(`/mf/funds/${code}?tab=${tab}`);
      await expect(page.getByText(text).first()).toBeVisible({ timeout: 20_000 });
      const [scroll, client] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
      expect(scroll).toBeLessThanOrEqual(client);
    });
  }
});

test.describe('at the 390 px investor viewport', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

  test('Overview keeps identity and actions while showing the primary plot above the action bar', async ({ page }) => {
    await page.goto(`/mf/funds/${FUND}?tab=overview`);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('img', { name: /^Score \d+ of 100$/ })).toBeInViewport();
    await expect(page.getByRole('heading', { name: 'Growth of ₹10,000' })).toBeInViewport();
    const bar = page.getByRole('group', { name: 'Fund actions' });
    await expect(bar.getByRole('button', { name: 'Add to watchlist' })).toBeInViewport();
    const chart = page.getByRole('figure', { name: 'Growth of ₹10,000 chart' });
    await expect(chart).toBeVisible();
    const figureTop = await chart.evaluate((element) => element.getBoundingClientRect().top);
    const actionsTop = await bar.evaluate((element) => element.getBoundingClientRect().top);
    expect(actionsTop - figureTop, 'show a useful portion of the NAV plot above the fixed action bar').toBeGreaterThanOrEqual(80);
    await expectNoSideScroll(page);
  });
});

test.describe('at 320 px', () => {
  test.use({ viewport: { width: 320, height: 720 } });

  test('Fund Overview keeps its research actions reachable without horizontal overflow', async ({ page }) => {
    await page.goto(`/mf/funds/${FUND}?tab=overview`);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    const actions = page.getByRole('group', { name: 'Fund actions' });
    await expect(actions).toBeVisible();
    await expect(actions).toHaveAttribute('tabindex', '0');
    await actions.focus();
    for (let i = 0; i < 20; i++) await actions.press('ArrowRight');
    await expect(page.getByRole('link', { name: 'Test an investment' })).toBeInViewport();
    await expect(actions.getByRole('button', { name: 'Notes' })).toBeInViewport({ ratio: 1 });
    await expectNoSideScroll(page);
  });
});
