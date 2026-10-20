import type { APIRequestContext, Page } from '@playwright/test';
import { expect, resetDocuments, test } from './fixtures';

/** B1 (plan 2026-10-19): range and category filters over the whole run, and saved screens. */

const STRATEGY = 'minervini_trend_template';

test.beforeEach(() => resetDocuments());

interface Row {
  symbol: string;
  rank: number;
  rs_rating: number | null;
  momentum_score: string;
  sector: string | null;
}

/** The whole run, paged 50 at a time: a different page size from the app's, so the two cross-check. */
async function wholeRun(request: APIRequestContext) {
  const latest = await (await request.get(`/api/v1/runs/latest?strategy=${STRATEGY}`)).json();
  const items: Row[] = [];
  for (let offset = 0; ; offset += 50) {
    const page = await (await request.get(`/api/v1/rankings/runs/${latest.id}?limit=50&offset=${offset}`)).json();
    items.push(...page.items);
    if (items.length >= page.total) return { id: latest.id as number, items, total: page.total as number };
  }
}

/** The symbols the screener table shows, in order, at 100 rows per page. */
async function shownSymbols(page: Page): Promise<string[]> {
  const table = page.getByRole('region', { name: 'Ranked stock results' });
  await page.getByLabel('Rows per page').selectOption('100');
  return table.locator('table').evaluate((el) => {
    const column = [...el.querySelectorAll('thead th')].findIndex((th) => th.textContent?.trim().startsWith('Symbol'));
    return [...el.querySelectorAll('tbody tr')].map((tr) => tr.querySelectorAll('td')[column]?.textContent?.trim() ?? '');
  });
}

const filters = (page: Page) => page.getByRole('group', { name: 'Filters' });

async function setBound(page: Page, label: string, bound: 'Minimum' | 'Maximum', value: string) {
  await filters(page).getByRole('button', { name: label, exact: true }).click();
  await page.getByLabel(`${bound} ${label}`).fill(value);
  await page.keyboard.press('Escape');
}

test('range, sector and qualification filters equal a reference filter over the whole run', async ({ page, request }) => {
  const run = await wholeRun(request);
  expect(new Set(run.items.map((r) => r.symbol)).size).toBe(run.total);
  await page.goto('/');
  const count = page.getByTestId('screen-count');
  await expect(count).toHaveText(`Matches: ${run.total} of ${run.total}`);

  const rs = run.items.map((r) => r.rs_rating).filter((v): v is number => v !== null).sort((a, b) => a - b);
  const rsMin = rs[Math.floor(rs.length / 2)] ?? 0;
  const scores = run.items.map((r) => Number(r.momentum_score)).sort((a, b) => a - b);
  const momentumMax = scores[Math.floor(scores.length * 0.9)];
  await setBound(page, 'RS', 'Minimum', String(rsMin));
  await setBound(page, 'Momentum', 'Maximum', String(momentumMax));
  await expect(filters(page).getByRole('button', { name: `RS ≥ ${rsMin}`, exact: true })).toBeVisible();

  let reference = run.items.filter((r) => r.rs_rating !== null && r.rs_rating >= rsMin && Number(r.momentum_score) <= momentumMax);
  const sector = reference.find((r) => r.sector)?.sector;
  if (sector) {
    await filters(page).getByLabel('Sector').selectOption(sector);
    reference = reference.filter((r) => r.sector === sector);
  }
  expect(reference.length).toBeGreaterThan(0);
  await expect(count).toHaveText(`Matches: ${reference.length} of ${run.total}`);
  expect(await shownSymbols(page)).toEqual(reference.slice(0, 100).map((r) => r.symbol));

  await filters(page).getByRole('button', { name: 'Not qualified' }).click();
  const unqualified = reference.filter((r) => r.rank === 0);
  await expect(count).toHaveText(`Matches: ${unqualified.length} of ${run.total}`);

  await filters(page).getByRole('button', { name: 'Clear filters' }).click();
  await expect(count).toHaveText(`Matches: ${run.total} of ${run.total}`);
});

test('a saved screen persists, reopens after a reload, marks edits and is shared with the chart panel', async ({ page, request }) => {
  await page.goto('/');
  await filters(page).getByRole('button', { name: 'Qualified', exact: true }).click();
  await setBound(page, 'RS', 'Minimum', '50');
  await page.getByRole('group', { name: 'Column set' }).getByRole('button', { name: 'Scores' }).click();

  await page.getByRole('button', { name: 'Screen: Unsaved screen' }).click();
  await page.getByLabel('New screen name').fill('Leaders');
  const created = page.waitForResponse((r) => r.url().endsWith('/api/v1/screens/default') && r.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Save screen' }).click();
  expect((await created).status()).toBe(201);

  await page.reload();
  const menu = page.getByRole('button', { name: 'Screen: Leaders' });
  await expect(menu).toBeVisible();
  await expect(filters(page).getByRole('button', { name: 'Qualified', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(filters(page).getByRole('button', { name: 'RS ≥ 50', exact: true })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Column set' }).getByRole('button', { name: 'Scores' })).toHaveAttribute('aria-pressed', 'true');

  await filters(page).getByRole('button', { name: 'Trend pass' }).click();
  await page.getByRole('button', { name: 'Screen: Leaders, changed' }).click();
  const saved = page.waitForResponse((r) => r.url().endsWith('/api/v1/screens/default') && r.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Save changes to “Leaders”' }).click();
  expect((await saved).status()).toBe(200);
  const stored = (await (await request.get('/api/v1/screens/default')).json()).body.screens;
  expect(stored).toHaveLength(1);
  expect(stored[0]).toMatchObject({ name: 'Leaders', column_set: 'Scores', filters: { qualified: true, trend: true, ranges: { rs_rating: { min: 50, max: null } } } });

  // The chart's bottom panel opens the same screen.
  await page.goto('/chart/TCS');
  const bottom = page.getByRole('region', { name: 'Bottom panel' });
  await bottom.getByRole('button', { name: 'Stock Screener' }).click();
  await expect(bottom.getByRole('button', { name: 'Screen: Leaders' })).toBeVisible();
  await expect(bottom.getByRole('group', { name: 'Filters' }).getByRole('button', { name: 'Trend pass' })).toHaveAttribute('aria-pressed', 'true');

  // A duplicate name is refused; deleting returns to an unsaved screen.
  await bottom.getByRole('button', { name: 'Screen: Leaders' }).click();
  await page.getByLabel('New screen name').fill('leaders');
  await expect(page.getByText('A screen with this name exists.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save screen' })).toBeDisabled();
  await page.getByRole('button', { name: 'Delete “Leaders”' }).click();
  await expect(bottom.getByRole('button', { name: 'Screen: Unsaved screen' })).toBeVisible();
  await expect.poll(async () => (await (await request.get('/api/v1/screens/default')).json()).body.screens.length).toBe(0);
});
