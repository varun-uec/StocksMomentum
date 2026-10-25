import { expect, test } from './fixtures';

const LEGAL = 'HDFC Asset Management Company Limited';
const CANONICAL = 'HDFC Mutual Fund';
const view = {
  mode: 'all',
  conditions: [
    { field: 'status', op: 'in', value: ['active'] },
    { field: 'plan', op: 'in', value: ['direct'] },
    { field: 'option', op: 'in', value: ['growth'] },
    { field: 'category', op: 'in', value: ['Equity Scheme - Flexi Cap Fund'] },
    { field: 'amc', op: 'in', value: [LEGAL] },
  ],
  columns: ['amc', 'cagr_3y'], sort: [{ field: 'amc', dir: 'asc' }], formulas: {},
};

for (const width of [1440, 390]) {
  test(`saved legal-name AMC filter remains selected and clears at ${width}px`, async ({ page, workspace, request }) => {
    await page.setViewportSize({ width, height: 900 });
    const id = '00000000-0000-4000-8000-000000000099';
    workspace.records.push({ id, kind: 'screen', name: 'HDFC saved research', body: { view }, schema_version: 1, version: 1, archived: false, created_at: '2026-10-25T00:00:00Z', updated_at: '2026-10-25T00:00:00Z' });
    const run = await request.post('/api/v1/mf/screener/run', { data: { filter: { all: view.conditions }, columns: view.columns, sort: view.sort } });
    expect(run.ok()).toBeTruthy();
    const expected = await run.json();
    expect(expected.matched).toBeGreaterThan(0);
    await page.goto(`/mf/screen?screen=${id}`);
    const count = page.locator('[aria-live="polite"]').filter({ hasText: /funds?$/ }).first();
    await expect(count).toHaveText(new RegExp(`^${expected.matched} funds?$`));
    if (width < 768) {
      await page.getByRole('button', { name: /^Filters/ }).click();
      await page.getByRole('textbox', { name: 'Search metrics', exact: true }).fill('Fund house');
      await page.getByRole('button', { name: 'Filter by Fund house', exact: true }).click();
    } else {
      await page.getByRole('button', { name: `Fund house is ${CANONICAL}`, exact: true }).click();
    }
    const selected = page.getByRole('checkbox', { name: CANONICAL, exact: true });
    await expect(selected).toBeChecked();
    const cleared = page.waitForResponse((r) => r.url().endsWith('/api/v1/mf/screener/run') && r.request().method() === 'POST' && !JSON.stringify(r.request().postDataJSON().filter).includes('"amc"'));
    await selected.click();
    expect((await (await cleared).json()).matched).toBeGreaterThan(expected.matched);
    await expect(selected).not.toBeChecked();
    expect((workspace.records[0].body as { view: typeof view }).view.conditions.at(-1)?.value).toEqual([LEGAL]);
  });
}
