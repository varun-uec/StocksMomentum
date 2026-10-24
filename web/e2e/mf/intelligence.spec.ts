/**
 * Fund facts, benchmark, holdings, overlap and portfolio screens (doc 21 C12, C14–C16,
 * C25). Each test reads the live API first and checks the screen shows the same value.
 */
import { FUND, expect, test } from './fixtures';

const pct = (v: number, digits = 1) => `${v < 0 ? '−' : ''}${Math.abs(v * 100).toFixed(digits)}%`;
const DSP_FLEXI = '119076'; // DSP Flexi Cap Fund Direct Growth: DSP files its portfolio monthly

test('Facts & costs shows AMFI’s TER and the fund managers as filed', async ({ page, request }) => {
  const metrics = await (await request.get(`/api/v1/mf/funds/${FUND}/metrics`)).json();
  const profile = await (await request.get(`/api/v1/mf/funds/${FUND}/profile`)).json();
  await page.goto(`/mf/funds/${FUND}?tab=facts`);
  await expect(page.getByText('Expense ratio', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(pct(metrics.values.ter, 2)).first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Expense ratio over time' })).toBeVisible();
  await expect(page.getByText(profile.managers[0].name).first()).toBeVisible();
});

test('Benchmark labels its proxy and links to the index fund behind it', async ({ page, request }) => {
  const bench = await (await request.get(`/api/v1/mf/funds/${FUND}/benchmark`)).json();
  await page.goto(`/mf/funds/${FUND}?tab=benchmark`);
  await expect(page.getByText(`Against ${bench.benchmark}`)).toBeVisible();
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

test('Portfolio offers a local CAS import', async ({ page }) => {
  await page.goto('/mf/portfolio');
  await expect(page.getByText('Import a consolidated account statement')).toBeVisible();
});
