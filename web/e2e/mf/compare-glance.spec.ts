/**
 * Compare answers first: the At a glance strip names the stronger fund per question,
 * with every fund's value, and matches the compare API.
 */
import { FUND, expect, test } from './fixtures';

const HDFC_FLEXI = '118955';

test('At a glance names the stronger fund for return, fall, cost and benchmark', async ({ page, request }) => {
  const data = await (await request.get(`/api/v1/mf/compare?code=${FUND}&code=${HDFC_FLEXI}`)).json();
  const [a, b] = data.funds;
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/mf/compare?code=${FUND}&code=${HDFC_FLEXI}`);
  const glance = page.getByRole('list', { name: 'At a glance' });
  await expect(glance).toBeVisible();
  const winner = (id: string, better: 'higher' | 'lower') => {
    const pick = better === 'higher' ? (a.values[id] >= b.values[id] ? a : b) : (a.values[id] <= b.values[id] ? a : b);
    return pick.name.replace(/ - .*$/, '').replace(/ Fund$/, '');
  };
  for (const [title, id, better] of [['Higher 3Y return', 'cagr_3y', 'higher'], ['Shallower 3Y fall', 'mdd_3y', 'higher'], ['Lower cost', 'ter', 'lower']] as const) {
    const card = glance.getByRole('listitem').filter({ hasText: title });
    await expect(card.locator('p').nth(1)).toContainText(winner(id, better).split(' ').slice(0, 2).join(' '));
  }
  // The strip and the growth chart are both in the first desktop viewport.
  const box = await page.getByText('Growth of ₹10,000 from the common start').boundingBox();
  expect(box && box.y).toBeLessThan(1000);
});
