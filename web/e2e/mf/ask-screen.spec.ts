import { expect, test } from './fixtures';

const QUESTION = 'Diversified equity funds with consistent five-year performance, relatively low drawdowns and TER below 1%';

test('a plain-language screen shows its reading and only funds that meet it', async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/mf/ask');
  await page.getByLabel('Describe the funds you want').fill(QUESTION);
  const ran = page.waitForResponse((r) => r.url().includes('/api/v1/mf/screener/run') && JSON.stringify(r.request().postDataJSON().filter).includes('consistency_3y'));
  await page.getByRole('button', { name: 'Screen', exact: true }).click();
  const response = await ran;
  const filter = response.request().postDataJSON().filter.all as { field: string; op: string; value: unknown }[];
  expect(filter).toContainEqual({ field: 'ter', op: '<', value: 0.01 });
  expect(filter).toContainEqual({ field: 'consistency_3y', op: '>=', value: 0.6 });

  const panel = page.getByRole('region', { name: 'Describe the funds you want' });
  for (const text of ['Category: Diversified equity', 'Consistent:', 'Worst 3Y fall in the shallower half', 'TER below 1%']) await expect(panel.getByText(text).first()).toBeVisible();
  await expect(page).toHaveURL(/v=/);

  // Each fund shown meets every stated condition when read back from its own metrics.
  const body = await response.json();
  expect(body.rows.length).toBeGreaterThan(0);
  for (const row of body.rows.slice(0, 10)) {
    const metrics = await (await request.get(`/api/v1/mf/funds/${row.amfi_code}/metrics?data_revision=${body.data_revision}`)).json();
    const v = metrics.values;
    expect(v.ter).toBeLessThan(0.01);
    expect(v.consistency_3y).toBeGreaterThanOrEqual(0.6);
    expect(v.cagr_5y_cat_pct).toBeGreaterThanOrEqual(50);
    expect(v.mdd_3y_cat_pct).toBeGreaterThanOrEqual(50);
    expect(v.category).toMatch(/^Equity Scheme - /);
    expect(v.category).not.toMatch(/Sectoral/);
    expect([v.plan, v.option, v.status]).toEqual(['direct', 'growth', 'active']);
  }

  // A follow-up refines the same screen.
  const refined = page.waitForResponse((r) => r.url().includes('/api/v1/mf/screener/run') && JSON.stringify(r.request().postDataJSON().filter).includes('0.008'));
  await page.getByLabel('Refine this screen in plain words').fill('TER under 0.8% and remove the drawdown limit');
  await page.getByRole('button', { name: 'Refine' }).click();
  const next = (await refined).request().postDataJSON().filter.all as { field: string }[];
  expect(next.map((c) => c.field)).not.toContain('mdd_3y_cat_pct');
  expect(next.map((c) => c.field)).toContain('consistency_3y');
});

test('words the screener cannot use are named, not guessed', async ({ page }) => {
  await page.goto('/mf/screen');
  await page.getByLabel('Describe a screen in plain words').fill('funds my uncle likes');
  await page.getByRole('button', { name: 'Screen', exact: true }).click();
  await expect(page.getByText(/Not used, because no screen field matches: “my uncle likes”/)).toBeVisible();
});
