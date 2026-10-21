import { resolve } from 'node:path';
import { expect, test } from './fixtures';

/**
 * ADR-014 section 12 (R3-R2-09): the experiment page hands a parameter variant to
 * a Strategy Studio family. The page names the parent, the variant and the
 * hypothesis, and labels the run Historical Research - In-Sample.
 */

test('an override becomes a stored variant in a family and runs In-Sample, by keyboard', async ({ page, request }) => {
  const stamp = Date.now();
  const hypothesis = `A lower RS floor keeps more winners (${stamp}).`;
  await page.goto('/experiment');
  await expect(page.getByRole('heading', { name: 'Experiment Laboratory' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run Experiment' })).toBeVisible();

  await page.getByPlaceholder('engines.trend_template.weight').fill('trend_template.tt_rs_rating_min.params.min');
  await page.getByPlaceholder('1.5').fill('60');

  // The variant form appears, Run Dates stop applying, and the button waits for a hypothesis.
  await expect(page.getByRole('group', { name: 'Variant in Strategy Studio' })).toBeVisible();
  await expect(page.getByLabel(/^Run Dates/)).toBeDisabled();
  const run = page.getByRole('button', { name: 'Run Variant (In-Sample)' });
  await expect(run).toBeDisabled();
  await expect(page.getByText('Name the variant.')).toBeVisible();

  await page.getByLabel('Variant name').fill(`rs-floor-${stamp}`);
  await page.getByLabel('Hypothesis, in one sentence').fill(hypothesis);
  await expect(run).toBeEnabled();

  // Keyboard: the hypothesis choice is a radio group; the arrow key moves to "Join".
  await page.getByRole('radio', { name: 'State a hypothesis (new family)' }).focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('radio', { name: 'Join an existing family' })).toBeChecked();
  await expect(run).toBeDisabled();
  await page.keyboard.press('ArrowUp');
  await expect(page.getByLabel('Hypothesis, in one sentence')).toHaveValue(hypothesis);

  await run.focus();
  await page.keyboard.press('Enter');

  const result = page.getByRole('region', { name: 'Variant run' });
  await expect(result.getByText(`rs-floor-${stamp} v1`).first()).toBeVisible();
  await expect(result.getByText(hypothesis)).toBeVisible();
  await expect(result.getByText('Historical Research — In-Sample')).toBeVisible();
  await expect(result.getByText('Not evidence of future returns.')).toBeVisible();
  await expect(result.getByText('1 research run in this family')).toBeVisible();
  await expect(result.getByText('trend_template.tt_rs_rating_min.params.min')).toBeVisible();
  await expect(result.getByRole('status')).toContainText(/Queued|Running|Completed/);

  const families = await (await request.get('/api/v1/studio/families')).json();
  const family = families.find((f: { hypothesis: string }) => f.hypothesis === hypothesis);
  expect(family.members).toHaveLength(1);
  const evaluations = await (await request.get(`/api/v1/studio/families/${family.id}/evaluations`)).json();
  expect(evaluations).toHaveLength(1);
  expect(evaluations[0].result_class).toBe('in_sample');
  expect(evaluations[0].config_hash).toBe(family.members[0].config_hash);
  expect(evaluations[0].config_hash).not.toBe(family.root_config_hash);

  // Joining the family needs an explicit confirmation of its hypothesis.
  await page.getByRole('radio', { name: 'Join an existing family' }).check();
  await page.getByLabel('Variant name').fill(`rs-floor-b-${stamp}`);
  await page.getByLabel('Family of the base strategy').selectOption({ label: `Family ${family.id}: ${hypothesis}` });
  await expect(page.getByText("Confirm that the family's hypothesis covers this variant.")).toBeVisible();
  await expect(run).toBeDisabled();
  await page.getByLabel('This hypothesis covers my variant.').check();
  await page.getByPlaceholder('1.5').fill('55');
  await expect(run).toBeEnabled();
  await run.click();
  await expect(result.getByText(`rs-floor-b-${stamp} v1`).first()).toBeVisible();
  await expect(result.getByText('2 research runs in this family')).toBeVisible();
});

test('a base experiment without overrides keeps the original controls', async ({ page }) => {
  await page.goto('/experiment');
  await expect(page.getByRole('button', { name: 'Run Experiment' })).toBeEnabled();
  await expect(page.getByRole('group', { name: 'Variant in Strategy Studio' })).toHaveCount(0);
  await expect(page.getByLabel(/^Run Dates/)).toBeEnabled();
});

test('the handoff form and result have no axe violation or overflow, light and dark, phone and desktop', async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript({ path: resolve(process.cwd(), 'node_modules/axe-core/axe.min.js') });
  const found: string[] = [];
  const stamp = Date.now();
  for (const theme of ['light', 'dark'] as const) {
    for (const size of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
      const tag = `${theme} ${size.width}px`;
      await page.setViewportSize(size);
      await page.goto('/about');
      await page.evaluate((mode) => localStorage.setItem('m25-theme', mode), theme);
      await page.goto('/experiment');
      await page.getByPlaceholder('engines.trend_template.weight').fill('trend_template.tt_rs_rating_min.params.min');
      await page.getByPlaceholder('1.5').fill('61');
      await page.getByLabel('Variant name').fill(`axe-${theme}-${size.width}-${stamp}`);
      await page.getByLabel('Hypothesis, in one sentence').fill(`Axe check ${tag} ${stamp}: a lower floor keeps winners.`);
      const measure = async (step: string) => {
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (overflow > 0) found.push(`${tag} ${step}: ${overflow}px horizontal overflow`);
        const violations = await page.evaluate(async () => {
          const axe = (window as unknown as {
            axe: { run: (d: Document, o: object) => Promise<{ violations: { id: string; nodes: { target: unknown[] }[] }[] }> };
          }).axe;
          const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
          return r.violations.map((v) => `${v.id} x${v.nodes.length} e.g. ${String(v.nodes[0].target[0]).slice(0, 70)}`);
        });
        violations.forEach((v) => found.push(`${tag} ${step}: ${v}`));
      };
      await measure('form');
      await page.getByRole('button', { name: 'Run Variant (In-Sample)' }).click();
      await expect(page.getByRole('region', { name: 'Variant run' })).toBeVisible();
      // Let the button's colour transition end before axe samples its colours.
      await expect(page.getByRole('button', { name: 'Run Variant (In-Sample)' })).toBeEnabled();
      await page.waitForTimeout(500);
      await measure('result');
    }
  }
  expect(found, 'axe findings and overflow').toEqual([]);
});
