/**
 * Fund facts, benchmark, holdings, overlap and portfolio screens (doc 21 C12, C14–C16,
 * C25). Each test reads the live API first and checks the screen shows the same value.
 */
import { FUND, OTHER, expect, test } from './fixtures';

const pct = (v: number, digits = 1) => `${v < 0 ? '−' : ''}${Math.abs(v * 100).toFixed(digits)}%`;
const filedDate = (value: unknown) => {
  if (typeof value !== 'string') return '—';
  const [year, month, day] = value.slice(0, 10).split('-');
  return `${Number(day)} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][Number(month) - 1]} ${year}`;
};
const DSP_FLEXI = '119076'; // DSP Flexi Cap Fund Direct Growth: DSP files its portfolio monthly

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
