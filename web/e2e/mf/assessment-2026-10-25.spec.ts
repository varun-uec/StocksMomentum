/**
 * The 25 October live assessment's P0 defects, as investor journeys on the live API:
 * threshold count, no clipped screener column, phone bars and sources, Compare peers.
 */
import { FUND, expect, expectNoSideScroll, test } from './fixtures';

const FLEXI_UNIVERSE = [
  { field: 'status', op: 'in', value: ['active'] },
  { field: 'plan', op: 'in', value: ['direct'] },
  { field: 'option', op: 'in', value: ['growth'] },
  { field: 'category', op: 'in', value: ['Equity Scheme - Flexi Cap Fund'] },
];
const count = (page: import('@playwright/test').Page) => page.locator('p[aria-live=polite]', { hasText: 'funds' }).first();

test('Return 1Y ≥ −10% shows the metric, then narrows to the API count with no dialog', async ({ page, request }) => {
  const run = async (extra: object[]) => (await (await request.post('/api/v1/mf/screener/run', { data: { filter: { all: [...FLEXI_UNIVERSE, ...extra] }, sort: [], columns: [], page: { size: 1 } } })).json()).matched as number;
  const all = await run([]);
  const kept = await run([{ field: 'ret_1y', op: 'between', value: [-0.1, null] }]);
  expect(kept).toBeLessThan(all);
  await page.goto('/mf/screen');
  await expect(count(page)).toContainText(`${all} funds`);
  const rail = page.getByRole('complementary', { name: 'Filters' });
  await rail.getByRole('checkbox', { name: 'Show Return 1Y' }).click();
  await expect(page.locator('thead')).toContainText('Return');
  await expect(count(page)).toContainText(`${all} funds`);
  const sent = page.waitForRequest((r) => r.url().includes('/screener/run') && (r.postData() ?? '').includes('"ret_1y","op":"between","value":[-0.1,null]'));
  await rail.getByLabel('Minimum Return 1Y').fill('-10');
  await sent;
  await expect(count(page)).toContainText(`${kept} funds`);
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

for (const width of [1280, 1440]) {
  test(`at ${width} px every default screener column is fully visible`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/mf/screen');
    const region = page.getByRole('region', { name: 'Screen results' });
    await expect(region.locator('tbody tr').first()).toBeVisible();
    const clipped = await region.evaluate((el) => {
      const right = el.getBoundingClientRect().right;
      return [...el.querySelectorAll('thead th')].filter((th) => getComputedStyle(th).display !== 'none' && th.getBoundingClientRect().right > right + 1).map((th) => th.textContent);
    });
    expect(clipped).toEqual([]);
  });
}

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

  test('the compare count lives in the bottom bar, which leaves while the reader scrolls down', async ({ page }) => {
    await page.goto('/mf/screen');
    await page.getByRole('button', { name: /^Add .* to comparison$/ }).first().click();
    await expect(page.getByRole('complementary', { name: 'Compare tray' })).toHaveCount(0);
    const nav = page.getByRole('navigation', { name: 'Mutual fund research' });
    await expect(nav.getByRole('link', { name: /Compare/ })).toContainText('1');
    await page.mouse.wheel(0, 600);
    await expect.poll(() => nav.evaluate((el) => el.getBoundingClientRect().top)).toBeGreaterThanOrEqual(844);
    await page.mouse.wheel(0, -200);
    await expect.poll(() => nav.evaluate((el) => el.getBoundingClientRect().top)).toBeLessThan(844);
    await expectNoSideScroll(page);
  });

  test('each of the six key facts keeps its source', async ({ page }) => {
    await page.goto(`/mf/funds/${FUND}`);
    const facts = page.getByRole('link', { name: /^Key facts/ });
    await expect(facts).toContainText(/TER.+AMFI \d+ \w{3}/s);
    await expect(facts).toContainText(/AUM.+AMFI \d+ \w{3}/s);
    await expect(facts).toContainText('Scheme doc');
    await expect(facts).toContainText('AMC filing');
  });
});

test('Compare peers opens PPFAS with its two largest Flexi Cap peers in one click', async ({ page, request }) => {
  const peers = (await (await request.post('/api/v1/mf/screener/run', { data: { filter: { all: FLEXI_UNIVERSE }, sort: [{ field: 'aum_cr', dir: 'desc' }], columns: [], page: { size: 3 } } })).json()).rows
    .map((r: { amfi_code: string }) => r.amfi_code)
    .filter((c: string) => c !== FUND)
    .slice(0, 2);
  await page.goto(`/mf/funds/${FUND}`);
  await page.getByRole('link', { name: 'Compare peers' }).click();
  await expect(page).toHaveURL(new RegExp(`code=${FUND}&code=${peers[0]}&code=${peers[1]}$`));
  for (const row of ['TER', 'AUM', 'Benchmark', 'CAGR 3Y', 'Max drawdown 3Y']) await expect(page.getByRole('rowheader', { name: row, exact: true })).toBeVisible();
  await expect(page.getByText(/Largest Flexi Cap peers by AUM/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Do they own the same securities?' })).toBeVisible();
});
