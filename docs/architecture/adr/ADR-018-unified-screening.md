# ADR-018: Unified Screening in the Domain

**Status:** Proposed (2026-10-22). Part of the [Wickstreet 2.0 blueprint](../../plans/wickstreet-2/README.md).

## Context
Today the screener filters one Momentum25 run's rows in the browser, with fixed fields and AND only. Wickstreet 2.0 needs compound filters across fundamental, technical, Momentum25, fund and ETF fields, saved screens, presets, and point-in-time historical screens, with an explanation for each row. The universes are small: about 2,500 equities, 250 ETFs and 1,600 scheme-plan rows.

## Decision
1. **One evaluator in the domain** (`domain/screening/`). It filters an in-memory snapshot of typed field values. Live, historical and saved screens use it. No SQL query builder.
2. **A server field registry** (`GET /screener/fields`), generated from the metric definitions, like the Studio rule registry. Each field states type, unit, formula reference, asset class and data availability.
3. **A JSON filter tree** with `all`/`any` groups, at most two levels, typed operators, and fixed missing-data semantics: a condition on `NM`/`NA` is false, and the response counts rows excluded for missing data with reasons.
4. **Snapshots** keyed by `(asset_class, as_of, data_version)`, cached in `metric_snapshots` and Redis. A snapshot is a cache; deleting it changes no result.
5. **Determinism.** Sort keys end with the instrument id. Same request and `data_version` → byte-identical response.
6. **Momentum25 fields keep their meaning** and come from the production run on or before `as_of`. The server must return the same rows as today's browser filters for every V1 saved screen before the browser code is removed.
7. **Historical screens are reads.** They write no run and read no outcomes (forward returns are not fields).

## Consequences
- One code path, easy to test, explainable per row.
- The whole snapshot is rebuilt when data changes (≤ 5 s cold).
- Ceiling: past ~50,000 rows the snapshot should move to an indexed wide table.

## Alternatives considered
- **Dynamic SQL over a wide metrics table:** rejected for now. Two implementations of filter semantics (SQL and Python for explanations) would drift.
- **Keep filtering in the browser:** rejected. It cannot do point-in-time or full-universe fundamentals, and it ships all data to the client.
- **A formula language for custom ratios:** deferred. ADD A1 §4 excludes scripting languages.
