import type { APIRequestContext, Page } from '@playwright/test';
import { chooseLayout, expect, openPanelTab, resetDocuments, test } from './fixtures';

const BUILTIN = 'minervini_trend_template';
const EVIDENCE = '../audit-evidence/strategy-integration/screenshots';
const workstationCard = (page: Page) => page.locator('section').filter({ has: page.getByRole('heading', { name: 'Workstation screening' }) });
const provenance = (page: Page) => page.getByTestId('provenance').first();

type StudioFamily = {
  id: number;
  hypothesis: string;
  members: Array<{ name: string; version: number; config_hash: string; config: Record<string, any> }>;
};
type Run = { id: number; status: string; strategy: string; config_hash: string; run_date: string; data_version: string };

let saved: { familyId: number; name: string; hash: string; unrunHash: string; hypothesis: string } | null = null;
let completed: { run: Run; symbol: string; rank: number } | null = null;

test.beforeEach(() => resetDocuments());

async function chartReady(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByTestId('price-chart').first()).toBeVisible();
  await expect(page.getByText('Loading stored history…')).toHaveCount(0);
  await expect(page.getByText('Loading price series…')).toHaveCount(0);
}

async function latest(request: APIRequestContext, strategy: string, hash?: string): Promise<Run | null> {
  const params = new URLSearchParams({ strategy });
  if (hash) params.set('config_hash', hash);
  const response = await request.get(`/api/v1/runs/latest?${params}`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function selectCellSymbol(page: Page, id: string, symbol: string): Promise<void> {
  const cell = page.getByRole('region', { name: new RegExp(`^Chart ${id}:`) });
  await cell.getByTestId('price-chart').click({ position: { x: 55, y: 35 } });
  await expect(cell).toHaveAttribute('aria-current', 'true');
  await page.keyboard.press('Escape');
  await page.keyboard.type(symbol);
  const search = page.getByRole('dialog', { name: 'Search symbols' });
  await expect(search.getByRole('option', { name: new RegExp(`^${symbol}`) }).first()).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(cell).toHaveAccessibleName(`Chart ${id}: ${symbol}`);
}

test('authoring saves an immutable second version, reloads it, and keeps invalid and duplicate saves visible', async ({ page, request }) => {
  const stamp = Date.now();
  const name = `ws-${stamp}`;
  const hypothesis = `A stricter trend quality gate changes the qualified set (${stamp}).`;
  await page.goto('/studio?from=%2Fchart%2FRELIANCE');
  await expect(page.getByRole('heading', { name: 'Strategy Studio' })).toBeVisible();
  await page.getByLabel('Hypothesis, in one sentence').fill(hypothesis);
  await page.getByLabel('Start from').selectOption(BUILTIN);
  await page.getByLabel('Name of the first config').fill(name);
  await page.getByRole('button', { name: 'Create family' }).click();

  const lineage = page.getByRole('list', { name: 'Lineage' });
  const v1 = lineage.getByRole('button', { name: new RegExp(`^${name} v1`) });
  await expect(v1).toBeVisible();
  await expect(workstationCard(page)).toBeVisible();

  const rule = page.getByRole('group', { name: 'tt_rs_rating_min' });
  const min = rule.getByRole('textbox', { name: /^min/ });
  await min.fill('100');
  await expect(page.getByRole('button', { name: 'Save as new version' })).toBeDisabled();
  await expect(rule.getByText(/Allowed: 1–99/)).toBeVisible();
  await min.fill('99');
  await page.getByRole('button', { name: 'Save as new version' }).click();
  const v2 = lineage.getByRole('button', { name: new RegExp(`^└ ${name} v2`) });
  await expect(v2).toBeVisible();

  const family = (await (await request.get('/api/v1/studio/families')).json() as StudioFamily[])
    .find((item) => item.hypothesis === hypothesis)!;
  expect(family.members.map((member) => member.version)).toEqual([1, 2]);
  const [first, second] = family.members;
  expect(first.config_hash).not.toBe(second.config_hash);
  expect(Number(first.config.engines.find((engine: any) => engine.id === 'trend_template')
    .rules.find((item: any) => item.id === 'tt_rs_rating_min').params.min)).toBe(70);
  expect(Number(second.config.engines.find((engine: any) => engine.id === 'trend_template')
    .rules.find((item: any) => item.id === 'tt_rs_rating_min').params.min)).toBe(99);

  const builtInDetail = await request.get(`/api/v1/strategies/${BUILTIN}`).then((response) => response.json());
  const duplicate = await request.post('/api/v1/studio/families', {
    data: {
      hypothesis: ` ${hypothesis.toUpperCase()} `,
      parent_config_hash: builtInDetail.config_hash,
      config: { ...second.config, name: `duplicate-${stamp}` },
    },
  });
  expect(duplicate.status()).toBe(409);
  const nameConflict = await request.post('/api/v1/studio/families', {
    data: { hypothesis: `A separate family name conflict (${stamp}).`, parent_config_hash: builtInDetail.config_hash, config: { ...second.config, name: BUILTIN } },
  });
  expect(nameConflict.status()).toBe(409);

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Strategy Studio' })).toBeVisible();
  await page.getByRole('button', { name: new RegExp(hypothesis.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click();
  await expect(page.getByRole('list', { name: 'Lineage' }).getByRole('button', { name: new RegExp(`^└ ${name} v2`) })).toBeVisible();

  const options = await request.get('/api/v1/strategies?workspace=true');
  expect(options.ok()).toBeTruthy();
  expect((await options.json()).filter((strategy: any) => strategy.name === name).sort((a: any, b: any) => a.version - b.version).map((strategy: any) => strategy.config_hash))
    .toEqual([first.config_hash, second.config_hash]);
  expect(await latest(request, name, second.config_hash)).toBeNull();
  const completedOptions = await request.get('/api/v1/strategies?workspace=true&with_runs=true');
  expect((await completedOptions.json()).some((strategy: any) => strategy.config_hash === second.config_hash)).toBe(false);

  await workstationCard(page).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${EVIDENCE}/01-strategy-studio-versions.png`, fullPage: false });
  saved = { familyId: family.id, name, hash: second.config_hash, unrunHash: first.config_hash, hypothesis };
});

test('a saved config runs through the real screener engine and differs from the predefined strategy', async ({ page, request }) => {
  test.skip(!saved, 'The preceding authoring workflow must create the saved test config.');
  test.setTimeout(180_000);
  const initial = await latest(request, BUILTIN);
  expect(initial?.status).toBe('COMPLETED');
  const customBefore = await latest(request, saved!.name, saved!.hash);
  expect(customBefore).toBeNull();

  await page.goto('/studio');
  await page.getByRole('button', { name: new RegExp(saved!.hypothesis.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click();
  const card = workstationCard(page);
  await expect(card).toContainText(`config ${saved!.hash.slice(0, 12)}`);
  await card.getByRole('button', { name: 'Run this strategy' }).click();
  await expect(card.getByRole('link', { name: /View run #\d+ rankings/ })).toBeVisible({ timeout: 150_000 });
  const run = await latest(request, saved!.name, saved!.hash);
  expect(run).toMatchObject({ status: 'COMPLETED', strategy: saved!.name, config_hash: saved!.hash });
  expect(run!.run_date).toBe(initial!.run_date);
  expect(run!.data_version).toBe(initial!.data_version);

  const [builtinRanks, customRanks] = await Promise.all([
    request.get(`/api/v1/rankings/runs/${initial!.id}?limit=200&offset=0`).then((response) => response.json()),
    request.get(`/api/v1/rankings/runs/${run!.id}?limit=200&offset=0`).then((response) => response.json()),
  ]);
  expect(builtinRanks.run.config_hash).not.toBe(customRanks.run.config_hash);
  expect(customRanks.run.strategy).toBe(saved!.name);
  expect(customRanks.total).toBeGreaterThan(0);
  expect(customRanks.items.map((item: any) => item.symbol)).not.toEqual(builtinRanks.items.map((item: any) => item.symbol));

  const paged = await Promise.all([0, 10, 20].map((offset) => request.get(
    `/api/v1/rankings/runs/${run!.id}?limit=10&offset=${offset}`,
  ).then((response) => response.json())));
  expect(paged.reduce((total: number, item: any) => total + item.items.length, 0)).toBe(customRanks.total);
  expect(paged.flatMap((item: any) => item.items.map((row: any) => row.symbol)))
    .toEqual(customRanks.items.map((row: any) => row.symbol));

  const top = customRanks.items.find((item: any) => item.rank > 0);
  expect(top).toBeTruthy();
  const explanationResponse = await request.get(`/api/v1/stocks/${top.symbol}?run_id=${run!.id}`);
  expect(explanationResponse.ok()).toBeTruthy();
  const explanation = await explanationResponse.json();
  const gate = explanation.rule_explanations.find((item: any) => item.rule_id === 'tt_rs_rating_min');
  expect(gate).toBeTruthy();
  expect(gate.passed).toBe(true);
  expect(Number(gate.actual_value)).toBeGreaterThanOrEqual(99);
  expect(String(gate.threshold)).toContain('99');

  const ruleReference: Array<{ symbol: string; passed: boolean; rank: number }> = [];
  for (const item of customRanks.items as Array<{ symbol: string; rank: number }>) {
    const response = await request.get(`/api/v1/stocks/${item.symbol}?run_id=${run!.id}`);
    expect(response.ok()).toBeTruthy();
    const result = await response.json();
    const configuredGate = result.rule_explanations.find((rule: any) => rule.rule_id === 'tt_rs_rating_min');
    expect(configuredGate).toBeTruthy();
    expect(Boolean(configuredGate.passed)).toBe(Number(configuredGate.actual_value) >= 99);
    if (!configuredGate.passed) expect(item.rank).toBe(0);
    ruleReference.push({ symbol: item.symbol, passed: configuredGate.passed, rank: item.rank });
  }
  expect(ruleReference.some((item) => item.passed && item.rank > 0)).toBe(true);
  expect(ruleReference.some((item) => !item.passed && item.rank === 0)).toBe(true);

  await card.getByRole('link', { name: new RegExp(`View run #${run!.id} rankings`) }).click();
  await expect(page).toHaveURL(new RegExp(`run=${run!.id}`));
  await expect(provenance(page)).toContainText(`cfg ${saved!.hash.slice(0, 8)}`);
  await page.reload();
  await expect(page.getByLabel('Strategy', { exact: true })).toHaveValue(saved!.hash);
  await expect(provenance(page)).toContainText(`run #${run!.id}`);
  const rowsPerPage = page.getByLabel('Rows per page');
  await rowsPerPage.selectOption('10');
  await expect(page.getByText('Page 1 of 3')).toBeVisible();
  const bodyRows = page.getByRole('table').locator('tbody tr');
  const pageSymbols = async () => bodyRows.evaluateAll((rows) => rows.map((row) => row.querySelector('td:nth-child(2) button')?.textContent?.trim()));
  expect(await pageSymbols()).toEqual(customRanks.items.slice(0, 10).map((item: any) => item.symbol));
  await page.getByRole('button', { name: 'Next page' }).click();
  await expect(page.getByText('Page 2 of 3')).toBeVisible();
  expect(await pageSymbols()).toEqual(customRanks.items.slice(10, 20).map((item: any) => item.symbol));
  await page.getByRole('button', { name: 'Next page' }).click();
  await expect(page.getByText('Page 3 of 3')).toBeVisible();
  expect(await pageSymbols()).toEqual(customRanks.items.slice(20).map((item: any) => item.symbol));
  await rowsPerPage.selectOption('25');
  await page.getByRole('columnheader', { name: 'Symbol' }).click();
  await expect(page.getByRole('columnheader', { name: 'Symbol' })).toHaveAttribute('aria-sort', 'ascending');
  const sortedSymbols = (await pageSymbols()).filter((symbol): symbol is string => Boolean(symbol));
  const naturalSort = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
  expect(sortedSymbols).toEqual(customRanks.items.map((item: any) => item.symbol).sort(naturalSort.compare));
  const searchResults = page.getByPlaceholder('Search symbol or name…');
  await searchResults.fill(top.symbol);
  await expect(page.getByText('Showing 1 of 1')).toBeVisible();
  await expect(bodyRows).toHaveCount(1);
  await searchResults.clear();
  await expect(page.getByText(`Showing ${customRanks.total} of ${customRanks.total}`)).toBeVisible();
  const firstRow = page.getByRole('table').locator('tbody tr').filter({ has: page.getByRole('button', { name: top.symbol, exact: true }) });
  await firstRow.getByRole('button', { name: top.symbol, exact: true }).click();
  const assessment = page.getByRole('tabpanel', { name: 'Assessment' });
  await expect(assessment.getByTestId('assessment-symbol')).toHaveText(top.symbol);
  await expect(assessment.getByTestId('provenance')).toContainText(`run #${run!.id}`);
  await expect(assessment.getByTestId('provenance')).toContainText(`cfg ${saved!.hash.slice(0, 8)}`);
  const unranked = customRanks.items.find((item: any) => item.rank === 0);
  expect(unranked).toBeTruthy();
  await page.getByRole('table').getByRole('button', { name: unranked.symbol, exact: true }).click();
  await expect(page.getByRole('region', { name: 'Why it is not ranked' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Why it ranks' })).toHaveCount(0);
  await page.getByRole('table').getByRole('button', { name: top.symbol, exact: true }).click();
  await expect(page.getByRole('region', { name: 'Why it ranks' })).toBeVisible();
  await page.screenshot({ path: `${EVIDENCE}/02-screening-rankings-assessment.png`, fullPage: true });
  completed = { run: run!, symbol: top.symbol, rank: top.rank };
});

test('strategy switching is run-specific and never borrows another strategy’s completed data', async ({ page, request }) => {
  test.skip(!saved || !completed, 'The preceding strategy screening must complete first.');
  await page.goto('/');
  const selector = page.getByLabel('Strategy', { exact: true });
  const strategies = await request.get('/api/v1/strategies?workspace=true').then((response) => response.json());
  const registered = await request.get('/api/v1/strategies').then((response) => response.json());
  expect(registered).toHaveLength(7);
  expect(registered.filter((strategy: any) => strategy.kind === 'research')).toHaveLength(6);
  const productionStrategies = strategies.filter((strategy: any) => strategy.kind === 'production');
  expect(productionStrategies.map((strategy: any) => strategy.name)).toEqual([BUILTIN]);
  const productionRuns = await Promise.all(productionStrategies.map((strategy: any) => latest(request, strategy.name)));
  expect(productionRuns.filter((run) => run?.status === 'COMPLETED')).toHaveLength(1);
  const runPage = await request.get('/api/v1/runs?limit=200').then((response) => response.json());
  expect(runPage.items.some((run: any) => run.strategy === 'benchmark_a_pure_momentum')).toBe(true);
  const builtIn = strategies.find((strategy: any) => strategy.name === BUILTIN);
  const userVersion = strategies.find((strategy: any) => strategy.config_hash === saved!.hash);
  await expect(selector).toHaveValue(builtIn.config_hash);
  await selector.selectOption(saved!.unrunHash);
  await expect(selector).toHaveValue(saved!.unrunHash);
  await expect(provenance(page)).toContainText('no completed run');
  await expect(page.getByText('No completed screening run for this strategy version yet.')).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Run screening now' })).toBeVisible();
  await selector.selectOption(saved!.hash);
  await expect(selector).toHaveValue(userVersion.config_hash);
  await expect(provenance(page)).toContainText(`run #${completed!.run.id}`);

  await selector.selectOption(builtIn.config_hash);
  await expect(provenance(page)).toContainText(`run #${(await latest(request, BUILTIN))!.id}`);
  await expect(provenance(page)).not.toContainText(saved!.name);
  await page.goto('/strategies?from=%2Fchart%2FINFY');
  await expect(page.getByRole('heading', { name: 'Strategy Research' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Saved strategy research' })).toHaveCount(0);

  await page.goto('/');
  await selector.selectOption(saved!.hash);
  await expect(provenance(page)).toContainText(`run #${completed!.run.id}`);
  const unresolvedHash = 'f'.repeat(64);
  const notFound = await request.get(`/api/v1/runs/latest?strategy=${saved!.name}&config_hash=${unresolvedHash}`);
  expect(notFound.status()).toBe(404);
});

test('the exact custom run follows the selected chart cell and watchlist, and return navigation preserves other cells', async ({ page, request }) => {
  test.skip(!saved || !completed, 'The preceding strategy screening must complete first.');
  await request.delete('/api/v1/watchlist/INFY');
  await page.addInitScript(({ name, hash }) => {
    localStorage.setItem('momentum25.selectedStrategy', name);
    localStorage.setItem('momentum25.selectedStrategyHash', hash);
  }, { name: saved!.name, hash: saved!.hash });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto('/chart/RELIANCE');
  await chartReady(page);
  await chooseLayout(page, '2x2');
  await selectCellSymbol(page, 'c2', 'TCS');
  await selectCellSymbol(page, 'c3', 'INFY');
  await selectCellSymbol(page, 'c4', 'ITC');
  await page.getByRole('region', { name: /^Chart c3:/ }).getByTestId('price-chart').click({ position: { x: 50, y: 35 } });

  await openPanelTab(page, 'Assessment');
  await expect(page.getByTestId('assessment-symbol')).toHaveText('INFY');
  await expect(provenance(page)).toContainText(`cfg ${saved!.hash.slice(0, 8)}`);
  await expect(page.getByTestId('save-state')).toBeVisible({ timeout: 15_000 });
  await page.screenshot({ path: `${EVIDENCE}/03-multichart-assessment.png`, fullPage: false });
  await openPanelTab(page, 'Watchlist');
  const watchlist = page.getByRole('tabpanel', { name: 'Watchlist' });
  await watchlist.getByRole('button', { name: 'Add INFY' }).click();
  await expect(watchlist.getByRole('button', { name: 'Remove INFY' })).toBeVisible();
  const details = await (await request.get(`/api/v1/watchlist/detail?strategy=${saved!.name}&config_hash=${saved!.hash}`)).json();
  expect(details.run_id).toBe(completed!.run.id);
  expect(details.config_hash).toBe(saved!.hash);
  expect(details.items.some((item: any) => item.symbol === 'INFY')).toBe(true);

  await page.getByRole('region', { name: 'Bottom panel' }).getByRole('link', { name: 'Research in Studio' }).click();
  await expect(page).toHaveURL(/\/studio\?from=/);
  await expect(page.getByRole('heading', { name: 'Strategy Studio' })).toBeVisible();
  const card = workstationCard(page);
  await expect(card).toContainText(`config ${saved!.hash.slice(0, 12)}`);
  await expect(page.getByRole('heading', { name: 'Judge this config' })).toBeVisible();
  await card.getByRole('link', { name: 'Return to chart' }).click();
  await expect(page).toHaveURL(/\/chart\/INFY$/);
  await chartReady(page);
  await expect(page.locator('main.chart-page')).toHaveAttribute('data-layout', '2x2');
  await expect(page.getByRole('region', { name: /^Chart main: RELIANCE/ })).toBeVisible();
  await expect(page.getByRole('region', { name: /^Chart c2: TCS/ })).toBeVisible();
  await expect(page.getByRole('region', { name: /^Chart c3: INFY/ })).toBeVisible();
  await expect(page.getByRole('region', { name: /^Chart c4: ITC/ })).toBeVisible();
  await expect(page.getByTestId('save-state')).toBeVisible({ timeout: 15_000 });
  await page.reload();
  await chartReady(page);
  await expect(page.locator('main.chart-page')).toHaveAttribute('data-layout', '2x2');
  await expect(page.getByRole('region', { name: /^Chart main: RELIANCE/ })).toBeVisible();
  await expect(page.getByRole('region', { name: /^Chart c2: TCS/ })).toBeVisible();
  await expect(page.getByRole('region', { name: /^Chart c3: INFY/ })).toBeVisible();
  await expect(page.getByRole('region', { name: /^Chart c4: ITC/ })).toBeVisible();

  await page.goto('/strategies?from=%2Fchart%2FINFY');
  const researchBoundary = page.getByRole('region', { name: 'Saved strategy research' });
  await expect(researchBoundary).toBeVisible();
  await expect(researchBoundary.getByRole('link', { name: 'Research this config in Strategy Studio' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Strategy Research' })).toHaveCount(0);
  await researchBoundary.getByRole('link', { name: 'Research this config in Strategy Studio' }).click();
  await expect(page.getByRole('heading', { name: 'Judge this config' })).toBeVisible();
  await workstationCard(page).getByRole('link', { name: 'Return to chart' }).click();
  await expect(page).toHaveURL(/\/chart\/INFY$/);
  await openPanelTab(page, 'Watchlist');
  await expect(page.getByRole('tabpanel', { name: 'Watchlist' }).getByRole('button', { name: 'Remove INFY' })).toBeVisible();
  await expect(page.getByTestId('save-state')).toBeVisible({ timeout: 15_000 });
  await page.screenshot({ path: `${EVIDENCE}/04-multichart-watchlist-return.png`, fullPage: false });
});

test('saved screener views stay independent from strategy definitions and their run selection', async ({ page, request }) => {
  test.skip(!saved || !completed, 'The preceding strategy screening must complete first.');
  await page.goto('/');
  const filters = page.getByRole('group', { name: 'Filters' });
  await filters.getByRole('button', { name: 'Qualified', exact: true }).click();
  await page.getByRole('button', { name: /Screen: Unsaved screen/ }).click();
  await page.getByLabel('New screen name').fill(`Qualified ${Date.now()}`);
  const savedScreen = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/screens/default') && response.request().method() === 'PUT',
  );
  await page.getByRole('button', { name: 'Save screen' }).click();
  expect((await savedScreen).status()).toBe(201);
  const beforeDocument = await request.get('/api/v1/screens/default').then((response) => response.json());
  const before = beforeDocument.body;
  expect(before.screens).toHaveLength(1);
  expect(Object.keys(before.screens[0]).sort()).toEqual(['column_set', 'filters', 'id', 'name']);
  expect(before.screens[0].filters.qualified).toBe(true);

  const selector = page.getByLabel('Strategy', { exact: true });
  await selector.selectOption(saved!.hash);
  await expect(provenance(page)).toContainText(`run #${completed!.run.id}`);
  await expect(page.getByRole('button', { name: /Screen: Qualified/ })).toBeVisible();
  await expect(filters.getByRole('button', { name: 'Qualified', exact: true })).toHaveAttribute('aria-pressed', 'true');
  const after = await request.get('/api/v1/screens/default').then((response) => response.json());
  expect(after.body).toEqual(before);
});

test('point-in-time research results keep their original config hash when a later version is saved', async ({ request }) => {
  test.skip(!saved, 'The authoring workflow must create a saved config first.');
  test.setTimeout(120_000);
  const liveRunsBefore = await request.get('/api/v1/runs?limit=200').then((response) => response.json());
  const queued = await request.post(`/api/v1/studio/families/${saved!.familyId}/evaluations`, {
    data: { config_hash: saved!.hash, result_class: 'screening' },
  });
  expect(queued.status()).toBe(202);
  let evaluation = await queued.json();
  await expect.poll(async () => {
    const current = await request.get(`/api/v1/studio/evaluations/${evaluation.id}`).then((response) => response.json());
    evaluation = current;
    return current.status;
  }, { timeout: 110_000 }).toBe('completed');
  expect(evaluation.config_hash).toBe(saved!.hash);
  expect(evaluation.result_class).toBe('screening');
  expect(evaluation.result.label).toContain('Screening Result');
  const liveRunsAfter = await request.get('/api/v1/runs?limit=200').then((response) => response.json());
  expect(liveRunsAfter.total).toBe(liveRunsBefore.total);

  const family = await request.get('/api/v1/studio/families').then((response) => response.json() as Promise<StudioFamily[]>);
  const member = family.find((item) => item.id === saved!.familyId)!.members.at(-1)!;
  const config = structuredClone(member.config);
  const gate = config.engines.find((engine: any) => engine.id === 'trend_template')
    .rules.find((item: any) => item.id === 'tt_rs_rating_min');
  gate.params.min = 98;
  const savedAgain = await request.post(`/api/v1/studio/families/${saved!.familyId}/strategies`, {
    data: { parent_config_hash: member.config_hash, config },
  });
  expect(savedAgain.status()).toBe(201);
  const newVersion = await savedAgain.json();
  expect(newVersion.config_hash).not.toBe(saved!.hash);
  const evaluations = await request.get(`/api/v1/studio/families/${saved!.familyId}/evaluations`).then((response) => response.json());
  expect(evaluations.find((item: any) => item.id === evaluation.id)).toMatchObject({
    config_hash: saved!.hash,
    result_class: 'screening',
    status: 'completed',
  });
  expect(evaluations.some((item: any) => item.config_hash === newVersion.config_hash)).toBe(false);
});

test('mobile screener keeps the first result row above the fixed navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const table = page.getByRole('region', { name: 'Ranked stock results' });
  await expect(table).toBeVisible();
  const filterDisclosure = page.locator('details').filter({ hasText: 'Filters · 22 matches' });
  const filterSummary = filterDisclosure.locator('summary');
  await expect(filterSummary).toBeVisible();
  // The paired before image reproduces the previous always-expanded mobile
  // controls using the same fixture and implementation revision.
  await filterSummary.click();
  await expect(filterDisclosure).toHaveAttribute('open', '');
  await page.screenshot({ path: `${EVIDENCE}/before-mobile-screener.png`, fullPage: false });
  await filterSummary.click();
  await expect(filterDisclosure).not.toHaveAttribute('open', '');
  const firstRow = page.getByRole('table').locator('tbody tr').first();
  const bounds = await firstRow.boundingBox();
  expect(bounds).toBeTruthy();
  expect(bounds!.y).toBeLessThan(844 - 64);
  await page.screenshot({ path: `${EVIDENCE}/05-mobile-screener.png`, fullPage: false });
});
