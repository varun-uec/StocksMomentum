import { FUND, OTHER, expect, expectNoSideScroll, test } from './fixtures';

/** Display rule of format.ts pct(): one decimal, a true minus sign. */
const pct = (v: number, digits = 1) => `${v < 0 ? '−' : ''}${Math.abs(v * 100).toFixed(digits)}%`;

test.describe('MF workstation journeys against the live snapshot', () => {
  test('Discover shows real registry facts, collections and market context', async ({ page, request }) => {
    const fields = await (await request.get('/api/v1/mf/screener/fields')).json();
    await page.goto('/mf');
    await expect(page.getByRole('heading', { name: /Find better/ })).toBeVisible();
    await expect(page.getByText(`${fields.fields.length} fields · method v${fields.method_version}`)).toBeVisible();
    await expect(page.getByRole('complementary', { name: 'Market today' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Category leaders' }).first()).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Explore by category' })).toBeVisible();
    await expect(page.getByText(/median 3Y CAGR of \d+ funds with 3 years of NAVs/).first()).toBeVisible();
    await expect(page.getByRole('img', { name: '91-day T-bill yield over five years' })).toBeVisible();
    await expect(page.locator('main')).toHaveCount(1);
  });

  test('J1: a collection opens its screen, a fund, and Back restores the screen', async ({ page }) => {
    await page.goto('/mf');
    await page.getByRole('link', { name: 'Consistent large caps' }).first().click();
    await expect(page).toHaveURL(/\/mf\/screen\?preset=consistent_large_caps/);
    await expect(page.getByRole('button', { name: 'Category is Large Cap', exact: true })).toBeVisible();
    const first = page.getByRole('region', { name: 'Screen results' }).getByRole('link').first();
    const name = await first.innerText();
    await first.click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(name);
    await page.goBack();
    await expect(page).toHaveURL(/preset=consistent_large_caps/);
    await expect(page.getByRole('region', { name: 'Screen results' }).getByRole('link').first()).toHaveText(name);
  });

  test('screener: a quick filter writes the view to the URL, and zero matches offer relaxations', async ({ page }) => {
    await page.goto('/mf/screen');
    const count = page.locator('[aria-live="polite"]').filter({ hasText: 'funds' }).first();
    await expect(count).not.toHaveText(/—/);
    const before = await count.innerText();
    // The checkbox follows the URL, so its state settles a moment after the click.
    await page.getByRole('checkbox', { name: 'Sharpe 3Y at least' }).click();
    await expect(page.getByRole('checkbox', { name: 'Sharpe 3Y at least' })).toBeChecked();
    await expect(page).toHaveURL(/v=/);
    await expect(page.getByRole('button', { name: 'Sharpe 3Y ≥ 0.4', exact: true })).toBeVisible();
    await expect(count).not.toHaveText(before);
  });

  test('screener: the condition editor takes percent input and serialises a fraction', async ({ page }) => {
    await page.goto('/mf/screen');
    await page.getByLabel('Search filter fields').fill('cagr_3y');
    await page.getByRole('navigation', { name: 'All fields' }).getByRole('button', { name: /^CAGR 3Y\s?, / }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Value', { exact: true }).fill('500');
    await expect(dialog.getByText('Sent as 500.0%.')).toBeVisible();
    await dialog.getByRole('button', { name: 'Add condition' }).click();
    await expect(page.getByRole('button', { name: 'CAGR 3Y ≥ 500%', exact: true })).toBeVisible();
    await expect(page.getByText('No fund matches every condition')).toBeVisible();
    const relax = page.getByRole('button', { name: /Remove “CAGR 3Y ≥ 500%”/ });
    await expect(relax).toBeVisible();
    await relax.click();
    await expect(page.getByText('No fund matches every condition')).toHaveCount(0);
  });

  test('J2: the fund page agrees with /metrics and shows an open drawdown honestly', async ({ page, request }) => {
    const metrics = await (await request.get(`/api/v1/mf/funds/${FUND}/metrics`)).json();
    await page.goto(`/mf/funds/${FUND}`);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Parag Parikh Flexi Cap Fund');
    await expect(page.getByText(`${pct(metrics.values.cagr_3y)} a year over 3 years`)).toBeVisible();
    await expect(page.getByText(`${pct(metrics.values.ret_1y, 1).replace(/^(\d)/, '+$1')} over 1 year`)).toBeVisible();
    await page.getByRole('link', { name: 'Risk' }).click();
    await expect(page).toHaveURL(/tab=risk/);
    await expect(page.getByRole('heading', { name: 'How far below its peak' })).toBeVisible();
    await expect(page.getByRole('figure', { name: 'Drawdown from peak over time' })).toBeVisible();
    await expect(page.getByText(/Sharpe uses the RBI 91-day T-bill/)).toBeVisible();
    await page.getByRole('link', { name: 'Holdings' }).click();
    await expect(page.getByText('Planned').first()).toBeVisible();
    await expect(page.getByText(/E4, dated AMC portfolio disclosures/)).toBeVisible();
  });

  test('every chart can show its data as a table', async ({ page }) => {
    await page.goto(`/mf/funds/${FUND}?tab=performance`);
    const frame = page.getByRole('region', { name: 'Year by year' });
    await frame.getByRole('button', { name: 'Show data table' }).click();
    await expect(frame.getByRole('region', { name: 'Chart data' }).getByRole('row').nth(1)).toBeVisible();
  });

  test('J3: compare shows the common start and the service correlation', async ({ page, request }) => {
    const data = await (await request.get(`/api/v1/mf/compare?code=${FUND}&code=${OTHER}`)).json();
    await page.goto(`/mf/compare?code=${FUND}&code=${OTHER}`);
    await expect(page.getByText(/The growth chart starts on/)).toBeVisible();
    await expect(page.getByRole('figure', { name: 'Rebased growth of the selected funds' })).toBeVisible();
    await expect(page.getByText(data.correlations[0].correlation.toFixed(2)).first()).toBeVisible();
    await expect(page.getByText(/does not measure shared holdings/)).toBeVisible();
  });

  test('J4: a historical SIP shows the calculator summary on open and follows each input', async ({ page, request }) => {
    await page.goto(`/mf/simulate?code=${FUND}`);
    const start = await page.getByRole('textbox', { name: 'Start' }).inputValue();
    const end = await page.getByRole('textbox', { name: 'End' }).inputValue();
    const sip = async (amount: number) => (await (await request.post('/api/v1/mf/calculators/sip', { data: { code: FUND, amount, day: 1, start, end, step_up: 0, tax_class: 'equity' } })).json()).summary;
    const first = await sip(10000);
    // No button: the default scenario runs on open (audit U-01).
    await expect(page.getByText(pct(first.xirr, 2), { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tax estimate' })).toBeVisible();
    await page.getByRole('spinbutton', { name: 'Monthly instalment (₹)' }).fill('12000');
    const next = await sip(12000);
    await expect(page.getByText(`₹${Math.round(next.invested).toLocaleString('en-IN')}`, { exact: true })).toBeVisible();
    await expect(page.getByText('Result is up to date.')).toBeVisible();
  });

  test('F-12: the default SWP lasts the whole 5-year window', async ({ page }) => {
    await page.goto(`/mf/simulate?code=${FUND}&kind=swp`);
    await expect(page.getByText(/60 withdrawals/)).toBeVisible();
    await expect(page.getByText(/used up the investment/)).toHaveCount(0);
  });

  test('studio: frontier, persistence matrix and a hold-out backtest', async ({ page }) => {
    await page.goto(`/mf/studio?mode=frontier&code=${FUND}`);
    await expect(page.getByRole('img', { name: 'Risk-return scatter of peers' })).toBeVisible();
    await page.getByRole('link', { name: 'Rank persistence' }).click();
    await expect(page.getByRole('row', { name: /^Q1 · \d+/ })).toBeVisible();
    await page.getByRole('link', { name: 'Selection backtest' }).click();
    // The default test runs on open and states its verdict in words (audit F-18, U-01).
    await expect(page.getByTestId('backtest-verdict')).toContainText(/In-sample .* On the hold-out/);
    await expect(page.getByText(/Historical research — in-sample/)).toBeVisible();
    await expect(page.getByText(/Out-of-sample evaluation — from/)).toBeVisible();
  });

  test('unknown fund and unknown route give a way back', async ({ page }) => {
    await page.goto('/mf/funds/abc');
    await expect(page.getByText('We could not find that fund')).toBeVisible();
    await page.goto('/mf/nowhere');
    await expect(page.getByRole('link', { name: 'Back to Discover' })).toBeVisible();
  });
});

test.describe('workspace (in-memory mock; the real store is never written)', () => {
  test.use({ allowStatus: [412] });

  test('starring a fund saves a watchlist that the workspace lists', async ({ page, workspace }) => {
    await page.goto(`/mf/funds/${FUND}`);
    await page.getByRole('button', { name: 'Add to watchlist' }).click();
    await expect(page.getByRole('button', { name: 'Watching' })).toBeVisible();
    expect(workspace.records[0].body).toEqual({ codes: [FUND] });
    await page.goto('/mf/workspace?tab=watchlists');
    await expect(page.getByRole('link', { name: 'Parag Parikh Flexi Cap Fund' })).toBeVisible();
  });

  test('a note that lost a race keeps the draft and says so', async ({ page, workspace }) => {
    await page.goto('/mf/workspace?tab=notes');
    await page.getByLabel('New note title').fill('Why flexi cap');
    await page.getByRole('button', { name: 'Create' }).click();
    await page.getByRole('textbox', { name: 'Note', exact: true }).fill('Low churn, long record.');
    workspace.forceConflict = true;
    await page.getByRole('button', { name: 'Save note' }).click();
    await expect(page.getByText(/Another window saved this record first/)).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Note', exact: true })).toHaveValue('Low churn, long record.');
  });

  test('alerts are planned, never active', async ({ page }) => {
    await page.goto('/mf/workspace?tab=alerts');
    await expect(page.getByText('Planned').first()).toBeVisible();
    await expect(page.getByText(/active/i).filter({ hasText: /^Active$/ })).toHaveCount(0);
  });
});

test.describe('theme and layout', () => {
  test('dark mode and a second palette change tokens, not components', async ({ page }) => {
    await page.goto('/mf');
    await expect(page.locator('.mf-root')).toBeVisible();
    const brand = () => page.evaluate(() => getComputedStyle(document.querySelector('.mf-root')!).getPropertyValue('--mf-brand').trim());
    expect(await brand()).toBe('23 107 85');
    await page.getByRole('button', { name: 'Use dark theme' }).click();
    await expect(page.locator('html')).toHaveClass(/dark/);
    expect(await brand()).toBe('131 209 179');
    await page.getByRole('button', { name: 'Appearance', exact: true }).click();
    await page.getByRole('radio', { name: 'Monsoon' }).check();
    expect(await brand()).toBe('147 182 238');
  });

  for (const width of [390, 768, 1024, 1440]) {
    test(`no sideways page scroll at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      for (const path of ['/mf', '/mf/screen', `/mf/funds/${FUND}`, `/mf/funds/${FUND}?tab=risk`, '/mf/studio', `/mf/compare?code=${FUND}&code=${OTHER}`, '/mf/simulate', '/mf/workspace', '/mf/portfolio', '/mf/ask']) {
        await page.goto(path);
        await page.waitForLoadState('networkidle');
        await expectNoSideScroll(page);
      }
    });
  }

  test('phone: bottom navigation and the filter sheet work', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/mf/screen');
    await page.getByRole('button', { name: /^Filters \(\d+\)$/ }).click();
    const sheet = page.getByRole('dialog', { name: 'Filters' });
    await expect(sheet).toBeVisible();
    await sheet.getByRole('button', { name: 'Cancel' }).click();
    await expect(sheet).toBeHidden();
    await page.getByRole('navigation', { name: 'Mutual fund research' }).last().getByRole('link', { name: 'Compare' }).click();
    await expect(page).toHaveURL(/\/mf\/compare/);
  });
});
