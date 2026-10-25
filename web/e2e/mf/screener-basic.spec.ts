import { expect, test } from './fixtures';

const encodeView = (view: object) => Buffer.from(JSON.stringify({ v: 1, ...view })).toString('base64url');
const countLabel = (page: import('@playwright/test').Page) =>
  page.locator('[aria-live="polite"]').filter({ hasText: /funds?$/ }).first();

test('Basic metric selection shows real values without adding a filter', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const runs: import('@playwright/test').Response[] = [];
  page.on('response', (response) => {
    if (response.url().includes('/api/v1/mf/screener/run') && response.request().method() === 'POST') runs.push(response);
  });
  await page.goto('/mf/screen');
  await expect(page.getByRole('radio', { name: 'Basic' })).toBeChecked();
  const count = countLabel(page);
  await expect(count).not.toHaveText(/—/);
  const before = await count.innerText();
  const initialFilter = runs[0].request().postDataJSON().filter;
  const initial = await runs[0].json();

  let clicks = 0;
  await page.evaluate(() => {
    (window as Window & { __mfClicks?: number }).__mfClicks = 0;
    document.addEventListener('click', () => {
      const w = window as Window & { __mfClicks?: number };
      w.__mfClicks = (w.__mfClicks ?? 0) + 1;
    }, true);
  });
  const started = Date.now();
  const result = page.waitForResponse((response) =>
    response.url().includes('/api/v1/mf/screener/run') && response.request().method() === 'POST' &&
    JSON.stringify(response.request().postDataJSON().columns).includes('ret_1y'),
  );
  await page.getByRole('checkbox', { name: 'Show Return 1Y' }).click();
  clicks = await page.evaluate(() => (window as Window & { __mfClicks?: number }).__mfClicks ?? 0);
  const response = await result;
  const shown = await response.json();
  const responseMs = Date.now() - started;

  expect(clicks).toBe(1);
  expect(response.request().postDataJSON().filter).toEqual(initialFilter);
  expect(shown.matched).toBe(initial.matched);
  expect(typeof shown.as_of).toBe('string');
  expect(shown.rows.some((row: { values: Record<string, unknown> }) => typeof row.values.ret_1y === 'number')).toBe(true);
  expect(responseMs).toBeLessThan(2500);
  await expect(page.getByRole('columnheader', { name: /Return 1Y/ })).toBeVisible();
  await expect(page).toHaveURL(/v=/);
  await expect(count).toHaveText(before);
  const readyMs = Date.now() - started;
  console.info(`Basic Return 1Y: ${clicks} click, latest values displayed, matched count unchanged, ${responseMs} ms to API response, ${readyMs} ms to visible column.`);

  // Showing the metric opened its range: a threshold needs no further click.
  let rangeClicks = 0;
  await page.evaluate(() => {
    (window as Window & { __mfClicks?: number }).__mfClicks = 0;
  });
  await expect(page.getByRole('button', { name: 'Filter by Return 1Y' })).toHaveAttribute('aria-expanded', 'true');
  // The universe's range no longer sits beside it: it described 7,887 options, not this result (assessment 25 Oct).
  await expect(page.getByText(/plan options with a value run from/)).toHaveCount(0);
  // The range of the funds on screen, so a threshold relates to this result set.
  await expect(page.getByText(new RegExp(`The ${shown.matched} funds shown run from −?[\\d.,]+% to −?[\\d.,]+%`))).toBeVisible();
  const minimum = page.getByRole('spinbutton', { name: 'Minimum Return 1Y' });
  await expect(minimum).toBeVisible();
  const thresholdResult = page.waitForResponse((response) =>
    response.url().includes('/api/v1/mf/screener/run') && response.request().method() === 'POST' &&
    response.request().postDataJSON().filter.all?.some((condition: { field: string }) => condition.field === 'ret_1y'),
  );
  await minimum.fill('-10');
  const thresholdResponse = await thresholdResult;
  const thresholdRequest = thresholdResponse.request().postDataJSON();
  expect(thresholdRequest.filter.all).toContainEqual({ field: 'ret_1y', op: 'between', value: [-0.1, null] });
  const thresholdData = await thresholdResponse.json();
  expect(thresholdData.matched).toBeGreaterThan(0);
  expect(thresholdData.matched).toBeLessThan(initial.matched);
  await expect(count).not.toHaveText(before);
  rangeClicks = await page.evaluate(() => (window as Window & { __mfClicks?: number }).__mfClicks ?? 0);
  expect(rangeClicks).toBe(0);
  // The metric the user chose leads the table, after the fund and its NAV line.
  await expect(page.getByRole('region', { name: 'Screen results' }).locator('thead th').nth(2)).toHaveText(/Return 1Y/);
  console.info(`Basic Return 1Y threshold: no extra click, one value entry applied a minimum without a dialog; ${before} → ${await count.innerText()}.`);
});

test('a second metric adds a value column without changing saved conditions', async ({ page }) => {
  const view = {
    mode: 'all',
    conditions: [
      { field: 'status', op: 'in', value: ['active'] },
      { field: 'plan', op: 'in', value: ['direct'] },
      { field: 'option', op: 'in', value: ['growth'] },
      { field: 'cagr_3y', op: '<=', value: 0.2 },
      { field: 'cagr_3y', op: '>=', value: 0.1 },
    ],
    sort: [{ field: 'cagr_3y', dir: 'desc' }],
    columns: ['cagr_3y'],
    formulas: {},
  };
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/mf/screen?v=${encodeView(view)}`);
  const count = countLabel(page);
  await expect(count).not.toHaveText(/—/);
  const before = await count.innerText();
  const responsePromise = page.waitForResponse((r) => r.url().includes('/api/v1/mf/screener/run') && r.request().method() === 'POST' && JSON.stringify(r.request().postDataJSON().columns).includes('ret_1y'));
  await page.getByRole('checkbox', { name: 'Show Return 1Y' }).click();
  const response = await responsePromise;
  expect(response.request().postDataJSON().filter.all).toContainEqual({ field: 'cagr_3y', op: '<=', value: 0.2 });
  expect(response.request().postDataJSON().filter.all).toContainEqual({ field: 'cagr_3y', op: '>=', value: 0.1 });
  await expect(count).toHaveText(before);
  await expect(page.getByRole('columnheader', { name: /Return 1Y/ })).toBeVisible();
});

test('TER selection also shows its AMFI filing date', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/mf/screen');
  const count = countLabel(page);
  await expect(count).not.toHaveText(/—/);
  const before = await count.innerText();
  const result = page.waitForResponse((r) => r.url().includes('/api/v1/mf/screener/run') && r.request().method() === 'POST' && JSON.stringify(r.request().postDataJSON().columns).includes('ter_as_of'));
  await page.getByRole('checkbox', { name: 'Show TER' }).click();
  const response = await result;
  const data = await response.json();
  expect(response.request().postDataJSON().columns).toEqual(expect.arrayContaining(['ter', 'ter_as_of']));
  expect(data.rows.some((row: { values: Record<string, unknown> }) => typeof row.values.ter === 'number' && typeof row.values.ter_as_of === 'string')).toBe(true);
  await expect(page.getByRole('columnheader', { name: 'TER', exact: true })).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'TER date', exact: true })).toBeVisible();
  await expect(count).toHaveText(before);
});

test('a saved Match any view explains its semantics and can reveal Advanced controls', async ({ page }) => {
  const view = {
    mode: 'any',
    conditions: [
      { field: 'status', op: 'in', value: ['active'] },
      { field: 'plan', op: 'in', value: ['direct'] },
      { field: 'option', op: 'in', value: ['growth'] },
      { field: 'cagr_3y', op: '>=', value: 0.1 },
    ],
    sort: [{ field: 'cagr_3y', dir: 'desc' }],
    columns: ['cagr_3y'],
    formulas: {},
  };
  await page.goto(`/mf/screen?v=${encodeView(view)}`);
  await expect(page.getByText(/Your active Direct Growth universe still applies/)).toBeVisible();
  await page.getByRole('complementary', { name: 'Filters' }).getByRole('button', { name: 'Show advanced logic' }).click();
  await expect(page.getByRole('radio', { name: 'Match any' })).toBeChecked();
  await expect(page.getByText(/still apply to every fund/)).toBeVisible();
});

test('phone filter sheet explains Match any after fixed universe gates', async ({ page }) => {
  const view = {
    mode: 'any',
    conditions: [
      { field: 'status', op: 'in', value: ['active'] },
      { field: 'plan', op: 'in', value: ['direct'] },
      { field: 'option', op: 'in', value: ['growth'] },
      { field: 'cagr_3y', op: '>=', value: 0.1 },
    ],
    sort: [{ field: 'cagr_3y', dir: 'desc' }],
    columns: ['cagr_3y'],
    formulas: {},
  };
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/mf/screen?v=${encodeView(view)}`);
  await page.getByRole('button', { name: /^Filters \(\d+\)$/ }).click();
  const sheet = page.getByRole('dialog', { name: 'Filters' });
  const notice = sheet.getByRole('note');
  await expect(notice).toContainText('active Direct Growth universe still applies');
  await expect(notice).toContainText('match at least one of the other conditions');
  await notice.getByRole('button', { name: 'Show advanced logic' }).click();
  await expect(page.getByRole('radio', { name: 'Match any' })).toBeVisible();
});

test('phone Basic metrics update results immediately; Advanced retains the full editor', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/mf/screen');
  const count = countLabel(page);
  await expect(count).not.toHaveText(/—/);
  const before = await count.innerText();
  await page.getByRole('button', { name: /^Filters \(\d+\)$/ }).click();
  const sheet = page.getByRole('dialog', { name: 'Filters' });
  await expect(sheet.getByRole('radio', { name: 'Basic' })).toBeChecked();
  const result = page.waitForResponse((response) =>
    response.url().includes('/api/v1/mf/screener/run') && response.request().method() === 'POST' &&
    JSON.stringify(response.request().postDataJSON().columns).includes('ret_1y'),
  );
  await sheet.getByRole('checkbox', { name: 'Show Return 1Y' }).click();
  const response = await result;
  const returned = await response.json();
  expect(returned.matched).toBe(Number(before.replace(/[^\d]/g, '')));
  await expect(sheet.getByRole('checkbox', { name: 'Show Return 1Y' })).toBeChecked();
  await expect(sheet.getByRole('button', { name: 'Apply filters' })).toHaveCount(0);
  await expect(sheet.getByRole('button', { name: 'Cancel' })).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
  await expect(page.getByRole('list', { name: 'Screen results' }).getByText('Return 1Y').first()).toBeVisible();
  await expect(count).toHaveText(before);

  await page.getByRole('button', { name: /^Filters \(\d+\)$/ }).click();
  await expect(sheet).toBeVisible();
  const phoneMinimum = sheet.getByRole('spinbutton', { name: 'Minimum Return 1Y' });
  const phoneRange = page.waitForResponse((response) =>
    response.url().includes('/api/v1/mf/screener/run') && response.request().method() === 'POST' &&
    response.request().postDataJSON().filter.all?.some((condition: { field: string }) => condition.field === 'ret_1y'),
  );
  await phoneMinimum.fill('-10');
  const phoneRangeResponse = await phoneRange;
  expect(phoneRangeResponse.request().postDataJSON().filter.all).toContainEqual({ field: 'ret_1y', op: 'between', value: [-0.1, null] });
  await expect(count).toHaveText('37 funds');

  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
  await page.getByRole('button', { name: /^Filters \(\d+\)$/ }).click();
  await expect(sheet).toBeVisible();
  await sheet.getByRole('radio', { name: 'Advanced' }).click();
  await expect(page.getByRole('radio', { name: 'Match all' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Formula/ })).toBeVisible();
  await sheet.getByLabel('Search filter fields').fill('ter');
  await sheet.getByRole('navigation', { name: 'All fields' }).getByRole('button', { name: /^TER/ }).first().click();
  await expect(page.getByRole('dialog', { name: /Add condition:/ })).toBeVisible();
  await expect(page.getByLabel('Condition', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add condition' })).toBeVisible();
});

test('a preset minimum and maximum show as one range and an edit keeps both', async ({ page }) => {
  const view = {
    mode: 'all',
    conditions: [
      { field: 'status', op: 'in', value: ['active'] },
      { field: 'plan', op: 'in', value: ['direct'] },
      { field: 'option', op: 'in', value: ['growth'] },
      { field: 'cagr_3y', op: '>=', value: 0.1 },
      { field: 'cagr_3y', op: '<=', value: 0.2 },
    ],
    sort: [{ field: 'cagr_3y', dir: 'desc' }],
    columns: ['cagr_3y'],
    formulas: {},
  };
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/mf/screen?v=${encodeView(view)}`);
  await expect(countLabel(page)).not.toHaveText(/—/);
  // The chip opens the inline range, not a dialog.
  await page.getByRole('region', { name: 'Conditions' }).getByRole('button', { name: /^CAGR 3Y ≥ 10%/ }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const rail = page.getByRole('complementary', { name: 'Filters' });
  await expect(rail.getByRole('spinbutton', { name: 'Minimum CAGR 3Y' })).toHaveValue('10');
  await expect(rail.getByRole('spinbutton', { name: 'Maximum CAGR 3Y' })).toHaveValue('20');
  const edited = page.waitForResponse((r) => r.url().includes('/api/v1/mf/screener/run') && JSON.stringify(r.request().postDataJSON().filter).includes('0.25'));
  await rail.getByRole('spinbutton', { name: 'Maximum CAGR 3Y' }).fill('25');
  const conditions = (await edited).request().postDataJSON().filter.all.filter((c: { field: string }) => c.field === 'cagr_3y');
  expect(conditions).toEqual([{ field: 'cagr_3y', op: 'between', value: [0.1, 0.25] }]);
});

test('an enum filters from an inline checklist with no operator', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/mf/screen');
  const count = countLabel(page);
  await expect(count).not.toHaveText(/—/);
  const before = await count.innerText();
  const rail = page.getByRole('complementary', { name: 'Filters' });
  await rail.getByLabel('Search metrics').fill('fund house');
  await rail.getByRole('checkbox', { name: 'Show Fund house' }).click();
  const group = rail.getByRole('group', { name: 'Fund house filter' });
  await group.getByLabel('Find a Fund house value').fill('PPFAS');
  const narrowed = page.waitForResponse((r) => r.url().includes('/api/v1/mf/screener/run') && JSON.stringify(r.request().postDataJSON().filter).includes('"amc"'));
  await group.getByRole('checkbox').first().click();
  const request = (await narrowed).request().postDataJSON();
  expect(request.filter.all).toContainEqual(expect.objectContaining({ field: 'amc', op: 'in' }));
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(count).not.toHaveText(before);
  // Untick to keep every fund again.
  await group.getByRole('checkbox').first().click();
  await expect(count).toHaveText(before);
});

test('a condition Basic cannot show opens the full editor', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/mf/screen?preset=ten_year_compounders');
  await expect(countLabel(page)).not.toHaveText(/—/);
  await page.getByRole('region', { name: 'Conditions' }).getByRole('button', { name: /^CAGR 10Y in top 25%/ }).click();
  await expect(page.getByRole('dialog', { name: /Edit condition: CAGR 10Y/ })).toBeVisible();
});
