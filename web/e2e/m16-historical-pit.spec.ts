import { expect, resetDocuments, test } from './fixtures';

/** M16: the existing Historical Replay route must use a sealed PIT input view. */

test.beforeEach(() => resetDocuments());

test('historical replay records point-in-time inputs and stays out of the live latest run', async ({
  page,
  request,
}) => {
  const latestBeforeResponse = await request.get(
    '/api/v1/runs/latest?strategy=minervini_trend_template',
  );
  expect(latestBeforeResponse.ok()).toBe(true);
  const latestBefore = (await latestBeforeResponse.json()) as { id: number };

  await page.goto('/historical');
  await page.locator('input[type="date"]').fill('2026-07-09');
  await page.getByRole('button', { name: 'Replay Date' }).click();

  const pitNotice = page.getByRole('status').filter({ hasText: 'Point-in-time inputs' });
  await expect(pitNotice).toBeVisible({ timeout: 60_000 });
  const runIdText = await page.getByText(/^Run ID$/).locator('..').innerText();
  const runId = Number(runIdText.match(/#(\d+)/)?.[1]);
  expect(Number.isInteger(runId)).toBe(true);

  const runResponse = await request.get(`/api/v1/runs/${runId}`);
  expect(runResponse.ok()).toBe(true);
  const run = (await runResponse.json()) as {
    data_version: string;
    stats: {
      historical: boolean;
      market_data_basis: string;
      market_data_revision: number;
      market_data_manifest: string;
    };
  };
  expect(run.data_version).toContain(':pit:');
  expect(run.stats).toMatchObject({
    historical: true,
    market_data_basis: 'point_in_time',
  });
  expect(run.stats.market_data_revision).toBeGreaterThan(0);
  expect(run.stats.market_data_manifest).toMatch(/^[0-9a-f]{12}$/);

  const latestAfterResponse = await request.get(
    '/api/v1/runs/latest?strategy=minervini_trend_template',
  );
  expect(latestAfterResponse.ok()).toBe(true);
  const latestAfter = (await latestAfterResponse.json()) as { id: number };
  expect(latestAfter.id).toBe(latestBefore.id);
});
