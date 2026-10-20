import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import type { APIRequestContext, Page } from '@playwright/test';
import { allowOneInjectedNetworkFailure, expect, pickTool, resetDocuments, test } from './fixtures';

const evidence = resolve(process.cwd(), '../audit-evidence/r2');
mkdirSync(evidence, { recursive: true });

test.beforeEach(() => resetDocuments());

async function chartReady(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
}

async function drawings(request: APIRequestContext, symbol: string): Promise<Record<string, any>[]> {
  const response = await request.get(`/api/v1/drawings/${symbol}`);
  if (response.status() === 404) return [];
  expect(response.ok()).toBe(true);
  return (await response.json()).body?.drawings ?? [];
}

async function clickChart(page: Page, x: number, y: number): Promise<void> {
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
}

test('R2 negative API cases stay JSON, reject hostile origins and never serve .env', async ({ request }) => {
  const missing = await request.get('/api/v1/r2-route-that-does-not-exist');
  expect(missing.status()).toBe(404);
  expect(missing.headers()['content-type']).toContain('json');
  expect(await missing.text()).not.toContain('<div id="root">');

  const unsupported = await request.post('/api/v1/health/live', { data: { unexpected: true } });
  expect(unsupported.status()).toBe(405);
  expect(unsupported.headers()['content-type']).toContain('json');

  const hostileHost = await request.get('/api/v1/health/live', {
    headers: { Host: 'evil.example' },
  });
  expect(hostileHost.status()).toBe(421);
  expect(hostileHost.headers()['content-type']).toContain('json');

  const hostileWrite = await request.post('/api/v1/alerts', {
    headers: { Origin: 'https://evil.example' },
    data: { symbol: 'RELIANCE', source: 'close', condition: 'above', threshold: '1' },
  });
  expect(hostileWrite.status()).toBe(403);
  expect((await (await request.get('/api/v1/alerts')).json()).alerts).toHaveLength(0);

  const malformed = await request.post('/api/v1/alerts', {
    headers: { 'Content-Type': 'application/json' },
    data: '{"source":',
  });
  expect(malformed.status()).toBeGreaterThanOrEqual(400);
  expect(malformed.headers()['content-type']).toContain('json');
  expect((await (await request.get('/api/v1/alerts')).json()).alerts).toHaveLength(0);

  const traversal = await request.get('/%2e%2e/.env');
  const traversalBody = await traversal.text();
  expect(traversalBody).not.toContain('M25_DATABASE_URL=');
  expect(traversalBody).not.toContain('POSTGRES_PASSWORD=');
});

test('R2 a drawing save interrupted by network loss stays local and can be retried', async ({ page, request }) => {
  await page.goto('/chart/INFY');
  await chartReady(page);
  await pickTool(page, 'Horizontal line');
  await clickChart(page, 0.5, 0.4);
  await expect.poll(async () => (await drawings(request, 'INFY')).length).toBe(1);
  const savedColor = (await drawings(request, 'INFY'))[0].color;

  await page.route('**/api/v1/drawings/INFY', async (route) => {
    if (route.request().method() === 'PUT') return route.abort('internetdisconnected');
    return route.continue();
  });
  allowOneInjectedNetworkFailure(page);
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.4, { button: 'right' });
  const menu = page.getByRole('menu', { name: 'Drawing' });
  await menu.getByRole('menuitemradio', { name: 'Rose' }).click();
  const saveStatus = page.getByRole('status').filter({ hasText: 'Not saved' });
  await expect(saveStatus).toBeVisible();
  await page.screenshot({ path: resolve(evidence, 'drawing-save-failed.png') });
  expect((await drawings(request, 'INFY'))[0].color).toBe(savedColor);

  await page.unroute('**/api/v1/drawings/INFY');
  await saveStatus.getByRole('button', { name: 'Retry' }).click();
  await expect.poll(async () => (await drawings(request, 'INFY'))[0].color).toBe('#ef4444');
  await expect(page.getByTestId('save-state')).toContainText('Saved');
});

test('R2 delete versus edit across two windows requires a choice and preserves the chosen copy', async ({
  page,
  browser,
  request,
}) => {
  await page.goto('/chart/TCS');
  await chartReady(page);
  await pickTool(page, 'Horizontal line');
  await clickChart(page, 0.5, 0.4);
  await expect.poll(async () => (await drawings(request, 'TCS')).length).toBe(1);

  const other = await browser.newContext();
  const second = await other.newPage();
  try {
    await second.goto('/chart/TCS');
    await chartReady(second);

    const box = (await page.getByTestId('price-chart').boundingBox())!;
    await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.4, { button: 'right' });
    await page.getByRole('menu', { name: 'Drawing' }).getByRole('menuitem', { name: 'Delete' }).click();
    await expect.poll(async () => (await drawings(request, 'TCS')).length).toBe(0);

    const secondBox = (await second.getByTestId('price-chart').boundingBox())!;
    await second.mouse.click(secondBox.x + secondBox.width * 0.5, secondBox.y + secondBox.height * 0.4, {
      button: 'right',
    });
    await second.getByRole('menu', { name: 'Drawing' }).getByRole('menuitemradio', { name: 'Rose' }).click();
    const conflict = second.getByRole('alert');
    await expect(conflict).toContainText('changed in another window');
    await conflict.getByRole('button', { name: 'Apply mine' }).click();
    await expect(conflict).toHaveCount(0);
    await expect.poll(async () => (await drawings(request, 'TCS')).length).toBe(1);
    expect((await drawings(request, 'TCS'))[0].color).toBe('#ef4444');
  } finally {
    await other.close();
  }
});

test('R2 Studio versions reopen together with immutable screening results for comparison', async ({
  page,
  request,
}) => {
  const stamp = Date.now();
  const hypothesis = `R2 compare immutable configs ${stamp}.`;
  await page.goto('/studio');
  await expect(page.getByRole('heading', { name: 'Strategy Studio' })).toBeVisible();
  await page.getByLabel('Hypothesis, in one sentence').fill(hypothesis);
  await page.getByLabel('Start from').selectOption('minervini_trend_template');
  await page.getByLabel('Name of the first config').fill(`r2-${stamp}`);
  const created = page.waitForResponse((response) =>
    response.request().method() === 'POST' && response.url().endsWith('/api/v1/studio/families'),
  );
  await page.getByRole('button', { name: 'Create family' }).click();
  const createResponse = await created;
  expect(createResponse.status()).toBe(201);
  const family = await createResponse.json();
  expect(family).toBeTruthy();
  const lineage = page.getByRole('list', { name: 'Lineage' });
  const v1 = lineage.getByRole('button', { name: new RegExp(`^r2-${stamp} v1`) });
  await expect(v1).toBeVisible();
  const v1Hash = family.members[0].config_hash as string;

  const rule = page.getByRole('group', { name: 'tt_rs_rating_min' });
  await rule.getByRole('textbox', { name: /^min/ }).fill('85');
  await page.getByRole('button', { name: 'Save as new version' }).click();
  const v2 = lineage.getByRole('button', { name: new RegExp(`^└ r2-${stamp} v2`) });
  await expect(v2).toBeVisible();
  const latest = (await (await request.get('/api/v1/studio/families')).json()).find(
    (item: { hypothesis: string }) => item.hypothesis === hypothesis,
  );
  const v2Hash = latest.members
    .filter((member: { name: string }) => member.name === `r2-${stamp}`)
    .at(-1).config_hash as string;
  expect(v2Hash).not.toBe(v1Hash);

  for (const [version, hash] of [[v1, v1Hash], [v2, v2Hash]] as const) {
    await version.click();
    await page.getByRole('button', { name: 'Run Screening Result' }).click();
    const result = page.getByRole('region', { name: /^Screening Result \d+$/ }).last();
    await expect(result.getByText(/names passed the gates\. No performance figure belongs to a Screening Result\./)).toBeVisible({
      timeout: 150_000,
    });
    expect(await result.getAttribute('aria-label')).toMatch(/^Screening Result /);
    await expect.poll(async () => {
      const evaluations = await (await request.get(`/api/v1/studio/families/${family.id}/evaluations`)).json();
      return evaluations.filter((evaluation: { config_hash: string; result_class: string }) =>
        evaluation.config_hash === hash && evaluation.result_class === 'screening',
      ).length;
    }).toBe(1);
  }

  await page.reload();
  await expect(page.getByRole('button', { name: new RegExp(hypothesis) })).toBeVisible();
  await page.getByRole('button', { name: new RegExp(hypothesis) }).click();
  await expect(page.getByRole('region', { name: /^Screening Result \d+$/ })).toHaveCount(2);
  await expect(page.getByText(/No performance figure belongs to a Screening Result\./)).toHaveCount(2);
  await page.screenshot({ path: resolve(evidence, 'studio-reopened-version-comparison.png'), fullPage: true });
});

test('R2 legacy strategy comparison uses distinct stored synthetic runs', async ({ page }) => {
  await page.goto('/strategies');
  await expect(page.getByRole('heading', { name: 'Strategy Research' })).toBeVisible();
  await page.getByLabel('Strategy A (Baseline)').selectOption('benchmark_a_pure_momentum');
  await page.getByLabel('Strategy B (Comparison)').selectOption('minervini_trend_template');
  await expect(page.getByText('Total Comparisons', { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('table').getByRole('columnheader', { name: 'Symbol' })).toBeVisible();
  await page.screenshot({ path: resolve(evidence, 'strategy-comparison-r2.png'), fullPage: true });
});
