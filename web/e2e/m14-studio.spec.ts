import { expect, test } from './fixtures';

/**
 * M14: Strategy Studio. A family is created from the production strategy, a
 * change is checked against the registry's bounds and saved as a new version,
 * and a Screening Result runs on the latest session.
 *
 * Families are append-only, so each run states a new hypothesis.
 */

test('a family is created, a bounded change is saved in its lineage, and a Screening Result runs', async ({ page }) => {
  test.setTimeout(180_000); // one full-universe point-in-time screen
  const stamp = Date.now();
  await page.goto('/studio');
  await expect(page.getByRole('heading', { name: 'Strategy Studio' })).toBeVisible();

  await page.getByLabel('Hypothesis, in one sentence').fill(`A higher RS floor improves 120d returns (${stamp}).`);
  await page.getByLabel('Start from').selectOption('minervini_trend_template');
  await page.getByLabel('Name of the first config').fill(`rs-${stamp}`);
  await page.getByRole('button', { name: 'Create family' }).click();

  const lineage = page.getByRole('list', { name: 'Lineage' });
  await expect(lineage.getByRole('button', { name: new RegExp(`^rs-${stamp} v1`) })).toBeVisible();

  // A value outside the registry's bounds is caught before saving.
  const rule = page.getByRole('group', { name: 'tt_rs_rating_min' });
  const floor = rule.getByRole('textbox', { name: /^min/ });
  await floor.fill('150');
  await expect(rule.getByText('Allowed: 1–99 RS rating (1-99).')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save as new version' })).toBeDisabled();

  await floor.fill('85');
  await page.getByRole('button', { name: 'Save as new version' }).click();
  await expect(lineage.getByRole('button', { name: new RegExp(`^└ rs-${stamp} v2`) })).toBeVisible();

  // The hold-out asks before it is spent; cancelling spends nothing.
  await page.getByRole('button', { name: 'Run Out-of-Sample Evaluation' }).click();
  await expect(page.getByRole('alertdialog', { name: 'Spend the hold-out' })).toBeVisible();
  await page.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('alertdialog')).toHaveCount(0);

  await page.getByRole('button', { name: 'Run Screening Result' }).click();
  const result = page.getByRole('region', { name: /^Screening Result \d+$/ });
  await expect(result.getByText(/names passed the gates\. No performance figure belongs to a Screening Result\./)).toBeVisible({
    timeout: 150_000,
  });
  await expect(result.getByRole('link').first()).toHaveAttribute('href', /^\/chart\//);
  await expect(page.getByText(/validated/i)).toHaveCount(0);
});
