# 04 · API and capability map

## Verified foundation

Inspected `backend/src/wickstreet/analytics/interface/http.py`, its application/domain modules, `apphost/main.py`, the current frontend routes and accepted docs 20–22/ADR-022/023. All research routes below are under **`/api/v1/mf`**, on the app's origin. The local service answered 28 representative calls (22 GETs, screen/backtest and four calculator kinds) with HTTP 200 on 23 October 2026. Snapshot **2801**, **method 5**, **as_of 2026-10-22**, sources **amfi, rbi, tigzig**. The registry returned **160** fields and presets **6**. These are observations, not permanent counts or exhaustive data validation. [Evidence](evidence/inspection.md).

Older plans contain hypothetical fields and different API shapes. The code is the integration contract. In particular: MF screens have no `asset_class` request key; `asset_class` is a registry field inside the filter. `excluded_missing` is a list, not a scalar. Registry type/coverage/descriptions exist; proposed synonyms and formula input provenance graphs do not. There is no arbitrary historical `as_of` screen parameter: `data_revision` pins stored revisions, and historical rank/backtest endpoints do their own month-end analysis. Do not advertise arbitrary past snapshots or full point-in-time source-category correctness.

## Current endpoint-to-screen mapping

| Method / path | Request / response used | Screens | Important limit |
|---|---|---|---|
| GET `/screener/fields` | Optional `data_revision`; envelope, registry_version, fields (id/label/group/type/unit/description/values/available/coverage) | D01/02/03/04/05/08 | Fetch once per revision, searchable schema-driven controls; unit not inferred from label |
| GET `/screener/presets` | Six definitions with filter/sort/columns/purpose | D01/02 | No snapshot envelope; definitions shipped with application; retain a copy in saved research |
| POST `/screener/run` | filter, sort, columns, formulas, page {size, after}, data_revision → total, matched, rows, conditions, excluded_missing, relaxations, next | D01/02/04 | 1–500 rows/page, ≤5 sort keys, max two group levels, same revision/filter for cursor |
| GET `/funds` | `q` 2–100 chars, `limit` 1–100, revision → funds name/code/AMC/category/plan/option/nav_available | Global search/compare/simulation | Includes no-NAV plans; no exchange symbol lookup |
| GET `/funds/{code}` | Envelope, fund attributes, classification, curated links | D03 | No enrichment guarantees; current example has zero links |
| GET `/funds/{code}/metrics` | All registry values, states, trailing anchors, since_label | D03/05 | First stored NAV is not inception; statuses active/historical/no_nav |
| GET `/funds/{code}/navs` | `start`, `end`, revision → date/nav/anomaly/source/revision per row | D03/05 | Invalid points may be filed; chart excludes invalid values with disclosed counts, not gaps bridged by invented prices |
| GET `/funds/{code}/annual` | Calendar, financial, monthly return tables | D03/04 | First/last partial years labelled; no arbitrary financial-year convention |
| GET `/funds/{code}/rolling` | `window=1y|3y|5y`, revision → points `[date, fraction]` | D03/04 | Summaries are in metrics; full series has overlapping samples |
| GET `/funds/{code}/drawdowns` | `top` 1–20 → episodes | D03/04 | Whole-history episodes, not automatically identical to 3Y drawdown |
| GET `/funds/{code}/underwater` | Series, recovery spread, dd_now/days, longest duration | D03/04 | No recovered date for an open drawdown |
| GET `/funds/{code}/rank-history` | Peer group, history of ret_1y and cagr_3y rank/count/pct/quartile | D03/04 | Current category labels used historically; samples vary monthly |
| GET `/peers/transitions` | category, plan, option → counts/shares | D04 | One-year quartile transitions, not probabilities of future performance |
| GET `/peers/frontier` | category, plan, option → active peer points, frontier marker | D04/05 | 3Y volatility and CAGR; not portfolio optimisation |
| GET `/funds/{code}/direct-regular` | pair identities, dr_gap_1y/3y, dr_wealth_10y, label | D03/05 | Observed NAV gap is not TER; no_pair is valid |
| GET `/funds/{code}/rolling-sip` | tenor, amount>0, day 1–31, step_up 0–1 → summary and starts | D04/06 | Expensive view fetched on demand, not every dashboard mount |
| GET `/funds/{code}/near-duplicates` | count, state, listed with correlation/common_days | D03/05 | Daily-return correlation ≥0.95, top listed results; not holdings overlap |
| GET `/funds/{code}/score` | score/rank/peers, formula, parts/weights/percentiles, quality notes | D03/05/09 | Three equal parts: consistency, return/risk, drawdown; missing if a part missing |
| GET `/funds/{code}/confidence` | Status/history/gaps/flags/category basis/source ranges/notes | D03/04/09 | Its `sources` is detailed objects, replacing string envelope list; type separately |
| GET `/risk-free` | RBI points, method, unit, acknowledgement | D03/04 | 35-day staleness yields no_risk_free; do not substitute zero |
| GET `/regimes` | NAV-built proxy and windows | D01/04 | Explicit proxy label, no official index claim |
| GET `/funds/{code}/regimes` | Fund/proxy returns, difference/capture per regime | D03/04 | Proxy comparisons, not official benchmark capture ratios |
| GET `/compare` | Repeated `code` 2–5 distinct, optional start/revision → metrics, indexed series, pair correlations/observations, average | D05 | Start defaults to latest first valid NAV; chart points can start on differing trade dates; metric windows remain their own trailing windows |
| POST `/backtests` | category, plan, option, signal ret_1y or cagr_3y, top 1–50, revision → strategy, summary, months, limits | D04 | ≥5 peers, hold-out from 2024-01; survivor/code-change/drop limitations in returned text |
| POST `/calculators/{kind}` | kind sip/lumpsum/swp/stp; body below → summary, timeline, tax, cautions | D06 | No E1 exit loads, tax may be unmodelled; pure research read despite POST |
| GET `/me` (identity API) | Current fixed personal identity/context | Shell/data boundary | Existing tenancy is not MF workspace CRUD |

The detailed [field catalogue](evidence/v5-field-catalogue.md) lists all current fields. UI must derive availability from responses, not hardcode the observed 160. It must not import backend persistence types or calculate new financial metrics in React.

## Screen and simulation payloads

The following matches current field ids and raw units. UI writes `15%` as `0.15`; percentile `75` stays `75`.

```json
{
  "filter": {"all": [
    {"field":"status","op":"in","value":["active"]},
    {"field":"plan","op":"in","value":["direct"]},
    {"field":"option","op":"in","value":["growth"]},
    {"field":"cagr_3y","op":">=","value":0.1}
  ]},
  "sort":[{"field":"score","dir":"desc"}],
  "columns":["category","cagr_3y","consistency_3y","mdd_3y","score"],
  "formulas":{}, "page":{"size":50}, "data_revision":2801
}
```

Custom formulas allow numeric registry ids, numbers, `+ - * /`, unary signs and parentheses. Max 10 formulas, expression ≤500 characters; names follow the backend's 1–40-character lower-case id rule and cannot collide with registry fields. Missing inputs propagate and zero division is NM. A zero-result screen returns relaxations only for a top-level ALL with at least two children. Do not manufacture relaxation counts for ANY groups.

```json
{
  "code":"122639", "amount":10000, "day":1,
  "start":"2021-10-01", "end":"2026-10-22", "step_up":0,
  "tax_class":"equity", "data_revision":2801
}
```

For SWP/STP, `amount` is initial investment and `instalment` monthly withdrawal/transfer. STP adds `target`. `slab_rate` is an optional raw fraction for applicable tax classes. The inspected `domain/tax.py` accepts `equity`, `debt`, `other`. Generate or contract-test that enum; do not infer it from fund names. The public calculator input model currently leaves `tax_class` as string; the UI must not present arbitrary free-text classes. The tax estimate also omits exit loads and STT and counts sales before 2018-04-01 as not modelled.

## Response and error handling

Most research reads carry `data_revision`, `latest_revision`, `method_version`, `as_of`, `sources`. `/confidence` is the source-shape exception and `/screener/presets` has no envelope. Type generation must include the **standalone MF OpenAPI**, not only the Momentum25 schema that `npm run gen:api` currently exports. Preserve optional/missing variants and inspect runtime errors from RFC-7807 `detail`/`type`; 422 may also be FastAPI validation details.

Handle 403 rights-denied, 404 no-snapshot/unknown-fund, 422 invalid-request/invalid-cursor/invalid-simulation separately. Cancel stale requests when a query changes. Cache keys include path, selected codes, inputs and revision. GET retry may be bounded; POST research reads can be retried explicitly without mutation, but avoid replaying future writes automatically. Do not round until display/export formatting.

## Service and data dependencies for the complete vision

These are **proposed contract requirements**, not implemented URLs or claims of a new accepted backend design. Implement within the existing modular monolith and public application interfaces. No new service/queue/broker is required by this plan.

| ID | Needed capability | Minimum contract / UI binding | Delivery |
|---|---|---|---|
| W1 | Research records | Tenant/owner-scoped list/get/create/patch/archive/restore; stable UUID, schema_version, revision/ETag; conflict 412; notes, lists, screens, scenarios and briefs | M6/Slice 4 |
| W2 | Alert lifecycle | Rule id/type/inputs/unit/scope/cadence; active/paused/error; last evaluated data revision; idempotent event id and event evidence; evaluator after successful snapshot publish | M6/Slice 4 |
| W3 | Context/diff | Saved snapshot results and exact view spec; compare original with latest; field change with both values/states/dates/methods; no cross-method delta without warning | M6/Slice 4; E1/E4 extend |
| A1 | Agent runtime | Typed turn id/context; structured tool stages; cancellation; validated result with citations; action proposal; model/template/prompt version; exact answer persistence | Slice 5 (ADR-022) |
| A2 | Personal recommendations | Deterministic scoring/constraint/alternative result; input profile version, constraints, reasons, counter-evidence and unavailable inputs | Slice 5/6; owner-approved methods |
| P1 | CAS import and ledger | Parse-only preview id/hash/format/issues/dedupe/reconciliation; one-use password; explicit idempotent commit; undo batch; plan-id resolution; local only | Slice 6 |
| P2 | Portfolio intelligence | Dated cash flows/value/XIRR/states; exposure totals and unresolved buckets; look-through disclosure context; proposed allocations/drift/tax-aware scenarios with assumptions | Slice 6 + E1/E4 |
| S1 | Forward/goal scenarios | Explicit assumptions, cash-flow engine, method/rules version, nominal/real and pre/post-tax outputs; stochastic percentiles only with accepted model | After historical calculators; not an alias of current API |
| E1 | TER/AUM/riskometer/profile/loads | Value, effective date, publication/source, per-field missing reason and import revision | Enrichment; not currently populated by v5 |
| E2 | Risk-free | Existing RBI 91-day T-bill data and acknowledgement | Built v5; future imports operational |
| E3 | Benchmark TRI | Licensed series and time-varying scheme benchmark; proxy must be clearly named and separately typed | Enrichment; alpha/beta/tracking/capture depend on it |
| E4 | Holdings | Disclosure id/date/publication date, securities/weights/quantities/resolution status and prior disclosure | Enrichment → holdings, overlap, look-through |
| E5 | IDCW distributions | Record/payment dates, per-unit payouts, reinvestment basis, source/revision | Enrichment → total returns; NAV-only caution stays meanwhile |
| E6 | ETF market data | Dated traded price/NAV/liquidity with storage rights and timestamp | Enrichment → premium/discount; no iNAV claim |
| E7 | Sector/style/fundamentals | Taxonomy/version/source, dated coverage and fund-weight linkage | E4 labels first; valuation/quality require vendor data |

No fake data accompanies blocked modules. Slice 4 ships useful NAV research and real persistence; the complete vision artboards specify what integrates next. Show dependency explanations at the relevant research location, not a navigation full of empty enabled tools. Recommendation and optimisation methods need their own approved specification and deterministic tests; this UI plan does not invent portfolio weights.
