/**
 * The fund overview is a first-screen dossier (live assessment 2026-10-24, reasons 3 and 6):
 * on a 1440×1000 desktop the growth chart and the dated key facts sit in the first viewport,
 * and each fact matches the API.
 */
import { FUND, expect, test } from './fixtures';

const filedDate = (value: unknown) => {
  if (typeof value !== 'string') return '—';
  const [year, month, day] = value.slice(0, 10).split('-');
  return `${Number(day)} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][Number(month) - 1]} ${year}`;
};

test('desktop first viewport shows the chart and dated cost, size, risk, benchmark, manager and portfolio facts', async ({ page, request }) => {
  const { values } = await (await request.get(`/api/v1/mf/funds/${FUND}/metrics`)).json();
  const profile = await (await request.get(`/api/v1/mf/funds/${FUND}/profile`)).json();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/mf/funds/${FUND}`);
  const facts = page.getByRole('region', { name: 'Key facts' });
  const inFirstViewport = async (locator: import('@playwright/test').Locator) => {
    await expect(locator).toBeVisible();
    const box = await locator.boundingBox();
    expect(box && box.y + box.height).toBeLessThanOrEqual(1000);
  };

  await inFirstViewport(page.getByRole('heading', { name: 'Growth of ₹10,000' }));
  await inFirstViewport(facts.getByText(`${(values.ter * 100).toFixed(2)}% a year`));
  await inFirstViewport(facts.getByText(`AMFI as of ${filedDate(values.ter_as_of)}`));
  await inFirstViewport(facts.getByText(`₹${Math.round(values.aum_cr).toLocaleString('en-IN')} Cr`));
  await inFirstViewport(facts.getByText(values.riskometer, { exact: true }));
  await inFirstViewport(facts.getByText(values.benchmark, { exact: true }));
  await inFirstViewport(facts.getByText(profile.managers[0].name.replace(/^(Mr|Ms|Mrs|Dr)\.?\s+/, ''), { exact: true }));
  await inFirstViewport(facts.getByText(`Portfolio of ${filedDate(values.holdings_as_of)}, as filed`));

  // A fact links to its full section.
  await facts.getByRole('link', { name: /Portfolio/ }).click();
  await expect(page).toHaveURL(/tab=holdings/);
});
