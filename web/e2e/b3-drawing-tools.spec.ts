import type { APIRequestContext, Page } from '@playwright/test';
import { expect, openPanelTab, pickTool, resetDocuments, test } from './fixtures';

/**
 * B3 (plan 2026-10-19): each new drawing tool passes the per-tool checklist:
 * flyout and last-used button, create, persistence round trip, select and drag,
 * resize by an anchor, style, undo and redo, lock and hide, and the
 * corporate-action rescale (anchors saved at traded prices).
 */

test.beforeEach(() => resetDocuments());

type Box = { x: number; y: number; width: number; height: number };
type At = (box: Box) => { x: number; y: number };
const frac = (fx: number, fy: number, dx = 0, dy = 0): At => (box) => ({ x: box.x + box.width * fx + dx, y: box.y + box.height * fy + dy });

interface Tool {
  name: string;
  kind: string;
  group: string;
  anchors: At[];
  /** A point on the drawing's body, away from its anchors. */
  body: At;
  text?: boolean;
}

const TOOLS: Tool[] = [
  { name: 'Arrow', kind: 'arrow', group: 'Annotation', anchors: [frac(0.3, 0.35), frac(0.6, 0.55)], body: frac(0.45, 0.45) },
  { name: 'Date range', kind: 'date_range', group: 'Measure', anchors: [frac(0.3, 0.3), frac(0.6, 0.6)], body: frac(0.45, 0.4) },
  { name: 'Date and price range', kind: 'date_price_range', group: 'Measure', anchors: [frac(0.3, 0.3), frac(0.6, 0.6)], body: frac(0.4, 0.4) },
  { name: 'Ellipse', kind: 'ellipse', group: 'Shapes', anchors: [frac(0.3, 0.3), frac(0.6, 0.6)], body: frac(0.45, 0.45) },
  { name: 'Triangle', kind: 'triangle', group: 'Shapes', anchors: [frac(0.3, 0.6), frac(0.6, 0.6), frac(0.45, 0.3)], body: frac(0.45, 0.5) },
  { name: 'Trend-based Fib extension', kind: 'fib_extension', group: 'Fibonacci', anchors: [frac(0.2, 0.7), frac(0.35, 0.4), frac(0.45, 0.6)], body: frac(0.52, 0.3) },
  { name: 'Pitchfork', kind: 'pitchfork', group: 'Lines', anchors: [frac(0.2, 0.5), frac(0.4, 0.35), frac(0.4, 0.65)], body: frac(0.65, 0.5) },
  { name: 'Callout', kind: 'callout', group: 'Annotation', anchors: [frac(0.3, 0.6), frac(0.5, 0.35)], body: frac(0.5, 0.35, 15, -5), text: true },
  { name: 'Price label', kind: 'price_label', group: 'Annotation', anchors: [frac(0.4, 0.5)], body: frac(0.4, 0.5, 30, 0) },
];

async function ready(page: Page): Promise<void> {
  await page.waitForFunction(() => performance.getEntriesByName('wickstreet:chart-painted').length > 0);
  await expect(page.getByText(/\d+ (daily|weekly|monthly) bars from the stored NSE series/)).toBeVisible();
}

interface Saved { id: string; kind: string; color: string; locked: boolean; hidden: boolean; text: string | null; points: { date: string; price: number }[] }
async function saved(request: APIRequestContext, symbol: string): Promise<Saved[]> {
  const res = await request.get(`/api/v1/drawings/${symbol}`);
  return res.ok() ? ((await res.json()).body?.drawings ?? []) : [];
}

async function draw(page: Page, tool: Tool, anchors = tool.anchors): Promise<void> {
  await pickTool(page, tool.name);
  const box = (await page.getByTestId('price-chart').boundingBox())!;
  for (const at of anchors) {
    const { x, y } = at(box);
    await page.mouse.click(x, y);
  }
  if (tool.text) {
    await page.getByLabel('Annotation text').fill(`${tool.name} note`);
    await page.keyboard.press('Enter');
  }
}

for (const tool of TOOLS) {
  test(`${tool.name}: flyout, create, round trip, drag, resize, style, undo, lock and hide`, async ({ page, request }) => {
    await page.goto('/chart/TCS'); await ready(page);
    // The tool sits in its TradingView group's flyout, with no shortcut of its own.
    const rail = page.getByRole('toolbar', { name: 'Drawing tools' });
    await rail.getByRole('button', { name: `${tool.group} tools` }).click();
    const item = page.getByRole('group', { name: `${tool.group} tools` }).getByRole('button', { name: tool.name, exact: true });
    await expect(item).toBeVisible();
    await expect(item).not.toHaveAttribute('aria-keyshortcuts', /.+/);
    await page.keyboard.press('Escape');

    await draw(page, tool);
    await expect.poll(async () => (await saved(request, 'TCS')).length).toBe(1);
    const [created] = await saved(request, 'TCS');
    expect(created.kind).toBe(tool.kind);
    expect(created.points).toHaveLength(tool.anchors.length);
    if (tool.text) expect(created.text).toBe(`${tool.name} note`);
    // The group button now shows the last tool used.
    await expect(rail.getByRole('button', { name: tool.name, exact: true })).toBeVisible();

    // Round trip: the saved drawing is back after a reload, in the Object tree.
    await page.reload(); await ready(page);
    await openPanelTab(page, 'Object tree');
    const tree = page.getByRole('tabpanel', { name: 'Object tree' });
    await expect(tree.getByRole('button', { name: `Hide ${tool.name}`, exact: true })).toBeVisible();

    // Select and drag the body: every anchor moves.
    const box = (await page.getByTestId('price-chart').boundingBox())!;
    const body = tool.body(box);
    await page.mouse.move(body.x, body.y);
    await page.mouse.down();
    await page.mouse.move(body.x + 40, body.y - 25, { steps: 6 });
    await page.mouse.up();
    await expect.poll(async () => (await saved(request, 'TCS'))[0].points.every((p, i) => p.date !== created.points[i].date && p.price !== created.points[i].price)).toBe(true);
    const moved = (await saved(request, 'TCS'))[0];

    // Resize: drag the first anchor; only it moves.
    const first = tool.anchors[0](box);
    await page.mouse.move(first.x + 40, first.y - 25);
    await page.mouse.down();
    await page.mouse.move(first.x + 40, first.y + 15, { steps: 6 });
    await page.mouse.up();
    await expect.poll(async () => (await saved(request, 'TCS'))[0].points[0].price).not.toBe(moved.points[0].price);
    const resized = (await saved(request, 'TCS'))[0];
    expect(resized.points.slice(1)).toEqual(moved.points.slice(1));

    // Style from the selected drawing's menu (Shift+F10), then undo and redo it.
    await page.keyboard.press('Shift+F10');
    const menu = page.getByRole('menu', { name: 'Drawing' });
    await menu.getByRole('menuitemradio', { name: 'Rose' }).click();
    await expect.poll(async () => (await saved(request, 'TCS'))[0].color).toBe('#ef4444');
    await page.keyboard.press('Escape');
    await page.keyboard.press('Control+z');
    await expect.poll(async () => (await saved(request, 'TCS'))[0].color).toBe(created.color);
    await page.keyboard.press('Control+Shift+z');
    await expect.poll(async () => (await saved(request, 'TCS'))[0].color).toBe('#ef4444');

    // Lock and hide from the Object tree.
    await tree.getByRole('button', { name: `Lock ${tool.name}`, exact: true }).click();
    await tree.getByRole('button', { name: `Hide ${tool.name}`, exact: true }).click();
    await expect.poll(async () => (await saved(request, 'TCS'))[0]).toMatchObject({ locked: true, hidden: true });
  });
}

test('every new tool saves traded prices across a split, so it stays on its bars', async ({ page, request }) => {
  // GOLDIAM: a 1:5 split went ex on 2022-03-28 (factor 0.15 before it, 0.75 after, until a 1:3 bonus on 2026-07-10).
  await page.goto('/chart/GOLDIAM'); await ready(page);
  await page.getByRole('button', { name: 'MAX', exact: true }).click();
  await ready(page);
  for (const tool of TOOLS) {
    // The first anchor before the split, the second after it, at one height; a third anywhere.
    const anchors = [frac(0.15, 0.6), frac(0.6, 0.6), frac(0.7, 0.4)].slice(0, Math.max(2, tool.anchors.length));
    await draw(page, tool, tool.kind === 'price_label' ? [anchors[0]] : anchors);
    if (tool.kind === 'price_label') await draw(page, tool, [anchors[1]]);
  }
  await expect.poll(async () => (await saved(request, 'GOLDIAM')).length).toBe(TOOLS.length + 1);
  const all = await saved(request, 'GOLDIAM');
  for (const tool of TOOLS) {
    const mine = all.filter((d) => d.kind === tool.kind);
    const [before, after] = tool.kind === 'price_label' ? [mine[0].points[0], mine[1].points[0]] : mine[0].points;
    expect(before.date < '2022-03-28' && after.date > '2022-03-28', tool.name).toBe(true);
    expect(before.price / after.price, tool.name).toBeCloseTo(0.75 / 0.15, 4);
  }
});
