# 06 — Unified Screening Specification

> Part of the [Wickstreet 2.0 blueprint](README.md). Status: Proposed. Governing decision: ADR-018. Extends the existing screener (`web/src/components/momentum25/screener.tsx`, `ScreenerPanel.tsx`, `saved_screens`); it does not replace it.

## 1. One screener, three asset tabs

`/` stays the screener. A tab strip above the table picks the asset class: **Stocks · Mutual funds · ETFs**. The chart workspace's bottom-panel screener gets the same strip.

| | Stocks | Mutual funds | ETFs |
|---|---|---|---|
| Row | Listed equity (`instrument_type = EQUITY`) | Plan-option (default Direct Growth) | Listed ETF |
| Field groups | Fundamental · Valuation · Growth · Technical · Momentum25 | Returns · Risk · Cost · Portfolio · Category | Returns · Tracking · Liquidity · Cost · Exposure |
| Default columns | Symbol, mcap, PE, ROCE, sales CAGR 3Y, RS, Momentum25 status, rank | Plan, category, 1Y/3Y/5Y return, rolling 3Y beat-benchmark %, max drawdown, TER, AUM | Symbol, index, 1Y return, tracking error, premium/discount, 20D traded value, TER |
| Opens | Company page | Fund page | ETF page |

The interaction model is the same on every tab: presets on the left, filter pills above the table, a column-set picker, sort by header click, row click opens the research page with `from` set.

## 2. Field registry

The server owns the field list. `GET /screener/fields?asset_class=stock` returns:

```json
{
  "registry_version": "a3f9…",
  "fields": [
    {
      "id": "roce",
      "label": "ROCE",
      "group": "Fundamental",
      "type": "number",
      "unit": "%",
      "description": "TTM EBIT ÷ average capital employed",
      "formula_ref": "03-product-specs#14-metric-dictionary",
      "templates": ["general"],
      "pit": true,
      "availability": "fundamentals"
    },
    {
      "id": "m25_qualified",
      "label": "Momentum25 qualified",
      "group": "Momentum25",
      "type": "boolean",
      "description": "Passed every gate in the latest production run",
      "pit": true,
      "availability": "momentum25_run"
    }
  ]
}
```

- `type` is `number`, `boolean`, `enum` (with `values`) or `date`.
- `availability` names the dataset. If that dataset has no rows, the field is listed with `"available": false` and a reason, and the picker shows it disabled with the reason ("No fundamentals imported yet"). The UI never hides a field silently.
- The registry is generated from the domain metric definitions, so a formula and its screen field cannot drift.

### 2.1 Momentum25 fields (unchanged meaning)

| Field | Source | Same as today's filter |
|---|---|---|
| `m25_qualified` | `rank > 0` in the production run for the date | `qualified` |
| `m25_trend` | All Trend Template checklist items pass | `trend` |
| `m25_rank`, `m25_rank_change`, `m25_momentum_score`, `m25_buy_setup_score`, `rs_rating` | Run fields | `ranges.*` |
| `m25_risk`, `m25_volume`, `m25_breakout` | Explanation categories | `risk`, `volume`, `breakout` |

The run used is the latest production run on or before the screen's `as_of`, from the selected strategy (the existing strategy selector). The row shows the run id. A security outside that run's evaluated set gets `NA (not evaluated in run 412)` for every Momentum25 field.

## 3. Filter language

A filter is a JSON tree. Groups nest at most two levels: the top group and its child groups. That covers "A AND B AND (C OR D)" and keeps the UI simple.

```json
{
  "all": [
    { "field": "roce", "op": ">", "value": 20 },
    { "field": "profit_cagr_3y", "op": ">", "value": 15 },
    { "field": "rs_rating", "op": ">", "value": 80 },
    { "field": "m25_qualified", "op": "=", "value": true },
    { "any": [
      { "field": "sector", "op": "in", "value": ["Capital Goods", "Chemicals"] },
      { "field": "mcap", "op": ">=", "value": 20000 }
    ]}
  ]
}
```

| Operator | Types | Meaning |
|---|---|---|
| `>`, `>=`, `<`, `<=`, `=`, `!=` | number, date, boolean (`=`/`!=` only) | Compare |
| `between` | number, date | Inclusive `[min, max]`; either side may be null |
| `in`, `not_in` | enum | Membership |
| `top_pct`, `bottom_pct` | number | Within the current universe at `as_of`, e.g. ROCE in the top 20% |
| `is_available`, `is_missing` | any | Tests the value state directly |

**Missing data.** A condition on an `NM` or `NA` value is **false**. `!=` and `not_in` are also false on missing values (no silent inclusion). The response counts, for each condition, the rows excluded *because the value was missing*, with the top reasons. The UI shows "37 stocks had no ROCE (bank template: 21, no filing: 16)".

**Validation.** The server rejects an unknown field, a wrong type, a field from another asset class or a tree deeper than two levels with `422` and the path of the bad node.

## 4. Evaluation

```text
POST /screener/run
{ "asset_class": "stock", "as_of": null | "2022-06-30",
  "filter": {…}, "sort": [{"field": "roce", "dir": "desc"}],
  "columns": ["symbol","mcap","roce","rs_rating","m25_rank"],
  "page": {"size": 100, "after": null},
  "strategy": "minervini_trend_template" }
→ { "as_of": "2026-10-21", "data_version": "…", "metric_version": 1,
    "total": 2431, "matched": 14,
    "excluded_missing": [{"field":"roce","count":37,"reasons":{"template:bank":21,"no_filing":16}}],
    "rows": [{ "id": 1234, "symbol": "…", "values": {…}, "states": {…},
               "conditions": [{"path":"all[0]","passed":true,"value":31.4}, …] }],
    "provenance": {"recorded": 14, "reconstructed": 0},
    "next": null }
```

- **Determinism.** Same filter, sort, `as_of`, strategy and `data_version` give byte-identical rows. Sort keys end with the instrument id.
- **Explanation.** Every row carries each condition's outcome and the value tested. Clicking a value opens its formula and inputs (the metric's `inputs` list from the engine).
- **Historical screens.** With `as_of`, the snapshot is built through the point-in-time ports: fundamentals visible at `as_of` (ADR-016), the Momentum25 run of that date, prices to that date, the universe listed and not delisted at that date. The header says "Screen as of 30 Jun 2022 — only data public by then". If any input is `reconstructed`, the header shows "Incomplete historical provenance" (ADR-014 §7 wording).
- **Isolation.** A historical screen is a research read. It writes no run, no strategy and nothing in the research namespace. It never reads the sealed hold-out window's *outcomes*; it reads only inputs, as the live screener does. Forward returns are not screen fields.

## 5. Saved screens and presets

- `SavedScreensV2` replaces `SavedScreensV1` in the `saved_screens` document. Each screen holds `asset_class`, `filter`, `sort`, `columns`, `strategy` and an optional pinned `as_of`.
- **Migration on read.** A V1 screen converts to V2 losslessly: `qualified` → `m25_qualified =`, `ranges.rs_rating` → `between`, and so on. The first save writes V2. A test round-trips every V1 shape.
- **Parity test.** For each V1 screen shape, the server evaluator on the latest run returns exactly the rows `applyFilters` returns in the browser today. Only then does the browser filter code get deleted.
- **Presets** are read-only screens shipped in `docs/architecture/screens/` (JSON), loaded at startup like strategies. Each has a one-line purpose. Examples:

| Preset | Asset | Filter |
|---|---|---|
| Quality compounders | Stock | ROCE > 20 for 3 FY AND sales CAGR 5Y > 12 AND D/E < 0.5 |
| Quality in momentum | Stock | ROCE > 20 AND profit CAGR 3Y > 15 AND RS > 80 AND Momentum25 qualified |
| Reasonable value | Stock | PE < industry median AND ROE > 15 AND interest coverage > 3 |
| Debt-free growers | Stock | D/E < 0.1 AND sales growth TTM > 20 |
| (fund presets) | Fund | see [03 §2.2](03-product-specs.md#22-fund-discovery-and-screening) |
| Liquid low-cost ETFs | ETF | TER ≤ 0.2 AND 20D median traded value ≥ ₹5 cr AND tracking error 1Y ≤ 0.2 |

Presets describe a style. They make no performance claim. A preset that names a return expectation would need a research proposal (walk-forward plus hold-out) first.

## 6. UI behaviour

```text
┌ Screener ───────────────────────────────────────────────────────────────────────────┐
│ [Stocks] Mutual funds  ETFs          As of: Latest ▾   Strategy: Momentum25 v3 ▾     │
├──────────────┬──────────────────────────────────────────────────────────────────────┤
│ PRESETS      │ [ROCE > 20 ×] [Profit CAGR 3Y > 15 ×] [RS > 80 ×] [M25 qualified ×]  │
│ Quality comp.│ [+ Add filter]  [Any of… ]                         14 of 2,431 match  │
│ Quality in m.│ ⓘ 37 had no ROCE · 112 not evaluated by Momentum25   [Columns ▾][CSV] │
│ Reasonable v.│──────────────────────────────────────────────────────────────────────│
│ ──────────── │ Symbol    Mcap ₹cr   ROCE %  Profit 3Y %  RS  M25   Rank             │
│ MY SCREENS   │ ABC       42,310     31.4    22.8         93  ✓     4                │
│ Capex names  │ DEF       18,955     27.9    19.1         88  ✓     11               │
│ + Save as…   │ …                                                                     │
└──────────────┴──────────────────────────────────────────────────────────────────────┘
```

- **Add filter** opens a searchable field picker grouped by the registry `group`. Typing "roce" or "return on capital" finds it (labels plus synonyms in the registry).
- A pill shows the condition in words. Clicking it edits operator and value in a popover (the existing `RangePill` pattern).
- **Any of…** creates an OR group, shown as one pill with a bracket.
- Results update 300 ms after the last edit. The count and the missing-data line update with them.
- **Columns** offers saved column sets per asset class; the Momentum25 column sets (Explanation, Technical) stay.
- **CSV** exports the visible columns with states (`NM`, `NA`) written out, plus a header row naming `as_of`, `data_version` and the filter in words.
- **Keyboard:** ↑/↓ move rows; `Enter` opens; Alt+C opens the chart for the row. No single-letter keys: a typed letter opens symbol search ([keyboard shortcuts](../../../current/keyboard-shortcuts.md)).
- **Empty result:** "No stocks match all 4 filters. Without *RS > 80*, 41 would match." The server computes the relaxation for each condition (one extra evaluation per condition; the universe is small).

## 7. Inside strategies (Phase 2, optional)

Fundamental fields become available to Strategy Studio as rules through the existing `FundamentalEngine` slot (ADD §6), read through `PointInTimeFundamentals`. The production strategy is not changed. A user strategy that uses them is evaluated in the research namespace like any other (ADR-014). Adding the rules changes the registry fingerprint and so the engine identity, as designed.

## 8. Tests

| Test | Checks |
|---|---|
| AST validation | Every operator × type; depth limit; unknown field; cross-asset field |
| Missing-value semantics | `NM`/`NA` false for every operator including `!=`; excluded counts and reasons |
| Determinism golden | Fixed fixture DB, 10 screens, byte-identical JSON across two runs and two processes |
| V1 → V2 migration | Every V1 shape round-trips |
| Server/browser parity | Every V1 shape returns the same rows as `applyFilters` on the fixture run |
| Point in time | A filing published the day after `as_of` is invisible; a restatement published later does not change the historical screen; `LookAheadError` on any later read |
| Performance | 2,500-row snapshot, 10-condition filter: P95 ≤ 50 ms in the domain, ≤ 300 ms end to end warm |
| E2E | Screener → add ROCE filter → open company → Financials → back keeps filters (`from`) |
