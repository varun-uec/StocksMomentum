/**
 * Regression tests for the defects the 23 Oct 2026 audit found
 * (docs/plans/wickstreet-2/ui-ux/audit-2026-10-23/REPORT.md). Each test names its
 * finding and checks the fix against the live snapshot; none writes to it.
 */
import { FUND, expect, expectNoSideScroll, test } from "./fixtures";

const pct = (v: number, digits = 1) =>
  `${v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(digits)}%`;

const UNIVERSE = [
  { field: "status", op: "in", value: ["active"] },
  { field: "plan", op: "in", value: ["direct"] },
  { field: "option", op: "in", value: ["growth"] },
];

test("F-01: the regimes chart draws one band per window", async ({
  page,
  request,
}) => {
  const regimes = await (await request.get("/api/v1/mf/regimes")).json();
  await page.goto(`/mf/studio?mode=regimes&code=${FUND}`);
  await expect(
    page.getByRole("img", { name: "Proxy level with regime windows" }),
  ).toBeVisible();
  await expect(page.locator(".mf-band")).toHaveCount(regimes.windows.length);
  expect(regimes.windows.length).toBeGreaterThanOrEqual(12);
});

test("F-02: risk-return gridline labels are round values", async ({ page }) => {
  await page.goto(`/mf/studio?mode=frontier&code=${FUND}`);
  const chart = page.getByRole("img", { name: "Risk-return scatter of peers" });
  await expect(chart).toBeVisible();
  const ticks = await chart
    .locator(".recharts-cartesian-axis-tick-value")
    .allTextContents();
  expect(ticks.length).toBeGreaterThan(4);
  // Every label is a whole or half percentage: a gridline at 11.4% can no longer read "11%".
  for (const t of ticks) expect(t).toMatch(/^−?\d+(\.5)?%$/);
});

for (const width of [1280, 1440, 1920])
  test(`F-03: row actions are visible without sideways scroll at ${width} px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/mf/screen");
    const compare = page
      .getByRole("region", { name: "Screen results" })
      .getByRole("button", { name: /to comparison$/ })
      .first();
    await expect(compare).toBeVisible();
    const box = (await compare.boundingBox())!;
    expect(box.x + box.width).toBeLessThanOrEqual(width);
    await expect(compare).toBeInViewport({ ratio: 1 });
  });

test("F-04: search finds the flagship fund and common spellings", async ({
  page,
  request,
}) => {
  for (const [q, name] of [
    ["parag", "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"],
    ["ppfas", "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"],
    ["sbi smallcap", "SBI Small Cap Fund - Direct Plan - Growth"],
    ["axis bluechip", "Axis Large Cap Fund - Direct Plan - Growth"],
  ]) {
    const funds = (
      await (
        await request.get(`/api/v1/mf/funds?q=${encodeURIComponent(q)}&limit=3`)
      ).json()
    ).funds;
    expect(
      funds.map((f: { name: string }) => f.name),
      q,
    ).toContain(name);
  }
  await page.goto("/mf");
  await expect(
    page.getByRole("combobox", { name: "Search funds", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("/");
  await page.keyboard.type("parag");
  await expect(page.getByRole("option").first()).toContainText(
    "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
  );
});

test("F-05: Match any never ORs the starting universe", async ({
  page,
  request,
}) => {
  const gates = (
    await (
      await request.post("/api/v1/mf/screener/run", {
        data: {
          filter: { all: UNIVERSE },
          sort: [],
          columns: [],
          page: { size: 1 },
        },
      })
    ).json()
  ).matched;
  await page.goto("/mf/screen");
  await page.getByRole("radio", { name: "Match any" }).click();
  await expect(page.getByText(/still apply to every fund/)).toBeVisible();
  const shown = page
    .locator('[aria-live="polite"]')
    .filter({ hasText: /funds$/ })
    .first();
  const count = async () =>
    Number(((await shown.textContent()) ?? "").replace(/[^\d]/g, ""));
  await expect.poll(count).toBeGreaterThan(0);
  expect(await count()).toBeLessThanOrEqual(gates);
});

test("F-06: the default screen ranks one category and warns on a cross-category score sort", async ({
  page,
}) => {
  await page.goto("/mf/screen");
  await expect(
    page.getByRole("combobox", { name: "Category" }).first(),
  ).toHaveValue("Equity Scheme - Flexi Cap Fund");
  await expect(
    page.getByText(/ranks a fund inside its own category/),
  ).toHaveCount(0);
  await page
    .getByRole("combobox", { name: "Category" })
    .first()
    .selectOption("");
  await expect(
    page.getByText(/ranks a fund inside its own category/),
  ).toBeVisible();
});

test("F-07: Risk and Performance show one worst-1-year figure", async ({
  page,
  request,
}) => {
  const metrics = await (
    await request.get(`/api/v1/mf/funds/${FUND}/metrics`)
  ).json();
  await page.goto(`/mf/funds/${FUND}?tab=risk`);
  const tile = page
    .getByText("Worst 1-year window")
    .locator('xpath=ancestor::div[contains(@class,"rounded-[12px]")][1]');
  await expect(tile).toContainText(pct(metrics.values.rolling_1y_min));
  await expect(page.getByText("Worst 1-month window")).toBeVisible();
  await page.goto(`/mf/funds/${FUND}?tab=performance`);
  await expect(
    page.getByText(`Worst ${pct(metrics.values.rolling_1y_min)}`).first(),
  ).toBeVisible();
});

test.describe("formula check", () => {
  // The drawer asks the screener to parse the formula; a 422 is the expected answer.
  test.use({ allowStatus: [422] });

  test("F-09: a bad formula stays in the drawer and the results keep their state", async ({
    page,
  }) => {
    await page.goto("/mf/screen");
    const url = page.url();
    await page.getByRole("button", { name: /^Formula/ }).click();
    await page.getByRole("textbox", { name: "Name" }).fill("broken");
    await page.getByRole("textbox", { name: "Expression" }).fill("cagr_3y / (");
    await page.getByRole("button", { name: "Add formula" }).click();
    await expect(page.getByRole("alert")).toContainText("Not added");
    expect(page.url()).toBe(url);
  });
});

test("F-12 and U-01: Studio, Compare and Lab open on a chart with no fund chosen", async ({
  page,
}) => {
  await page.goto("/mf/studio");
  await expect(
    page.getByRole("figure", { name: "Rolling returns over time" }),
  ).toBeVisible();
  await page.goto("/mf/compare");
  await expect(
    page.getByRole("figure", { name: "Rebased growth of the selected funds" }),
  ).toBeVisible();
  await page.goto("/mf/simulate");
  await expect(
    page.getByRole("img", { name: "Scenario value over time" }),
  ).toBeVisible();
});

test("F-13: the Appearance panel has no developer text", async ({ page }) => {
  await page.goto("/mf");
  await page.getByRole("button", { name: "Appearance", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText(/src\/features|themes\.ts/)).toHaveCount(0);
});

test("U-02: the fund verdict restates the API numbers", async ({
  page,
  request,
}) => {
  const regimes = await (
    await request.get(`/api/v1/mf/funds/${FUND}/regimes`)
  ).json();
  const deepest = regimes.windows
    .filter(
      (w: { kind: string; fund_return: number | null }) =>
        w.kind !== "recovery" && w.fund_return !== null,
    )
    .sort(
      (a: { proxy_return: number }, b: { proxy_return: number }) =>
        a.proxy_return - b.proxy_return,
    )[0];
  await page.goto(`/mf/funds/${FUND}`);
  const verdict = page.getByTestId("fund-verdict");
  await expect(verdict).toContainText(`lost ${pct(-deepest.fund_return)}`);
  await expect(verdict).toContainText(`${pct(-deepest.proxy_return)} fall`);
});

test.describe("phone", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });

  test("U-13: score and the action bar are on the first screen", async ({
    page,
  }) => {
    await page.goto(`/mf/funds/${FUND}`);
    await expect(
      page.getByRole("img", { name: /^Score \d+ of 100$/ }).first(),
    ).toBeInViewport();
    const bar = page.getByRole("group", { name: "Fund actions" });
    await expect(
      bar.getByRole("button", { name: "Add to watchlist" }),
    ).toBeInViewport();
    await expectNoSideScroll(page);
  });

  test("U-16: chips and small buttons are at least 44 px tall", async ({
    page,
  }) => {
    await page.goto("/mf/screen");
    const chip = page.getByRole("button", { name: /Flexi Cap by score/ });
    expect((await chip.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  });
});
