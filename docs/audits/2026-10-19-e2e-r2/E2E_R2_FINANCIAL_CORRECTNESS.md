# Wickstreet Financial Correctness Audit — Round 2

**Date:** 2026-10-19 · **Data:** deterministic synthetic fixtures plus previously recorded read-only historical rerun evidence. No production snapshot was rewritten and no live market download ran.

## Pipeline verdict

Pinned financial invariants passed in the full backend suite and focused browser workflows. The pipeline was audited as:

`raw bars/actions → adjustment factors → OHLCV → period bars/indicators → RS/screening → rankings/explanations → Strategy Studio → alerts → chart`

Round 2 added an exact MCX 1:5 split relative-strength golden case and independent persistence/alert/chart checks. Full historical-universe parity over production-sized data was not independently rerun because the prior research copy was not the isolated R2 database; results from that work are retained as historical evidence below, not presented as a new R2 query.

## Invariants and evidence

| Invariant | Deterministic evidence | Result |
|---|---|---|
| Corporate-action price factor is applied once | Synthetic split/bonus daily bars; chart response compared with stored `adj_close`; adjusted row has factor 1; reingestion preserves adjusted close. | Pass. No double scaling in chart response. |
| OHLC are on the same adjusted basis; volume is inverse-adjusted | Corporate-action integration tests compare adjusted prices and volume around a 1:1 bonus; chart parity regression. | Pass in fixtures. |
| Dividends do not create a split-like price adjustment | Ratioless/dividend actions remain unadjusted; explicit tests cover dividend action parsing/storage. | Pass. No dividend reinvestment/total-return series is claimed. |
| Corporate-action formulas | 1:1 bonus factor 0.5; 1:3 bonus factor 0.75; face-value split 10→2 factor 0.2; malformed/unrecognized ratio gets no adjustment. | Pass. |
| GOLDIAM split regression | Historical raw prices 790.80→173.70 previously appeared as −78%; adjusted series 118.62→130.28 is +9.8%. | Previously fixed and pinned in M11 evidence; no regression found. |
| GOLDIAM 2026-07-10 1:3 bonus | Adjusted close 315.375→378.000, +19.86%; API/chart parity and one-time adjustment fixture. | Pass; prior M11 review corrected an earlier mistaken concern. |
| MCX 2026-01-02 1:5 split | Synthetic 500→100 post-split then 120; adjusted base 100→120 is +20%; RS99 vs flat control RS1. | Pass. New R2 golden case pins the case that previously read as −76% when raw close was used. |
| Weekly/monthly bars | Golden tests cover shortened holiday week, partial week/month, no-session interval, ISO year boundary, split/bonus action week, weekly/monthly indicator-on-aggregated-bars, same data version. | Pass for tested fixtures. The long-history browser stress bars are weekdays only and do not reproduce the actual NSE holiday calendar. |
| Drawings and traded price basis | Drawing coordinates stay as traded values; display conversion uses factor for the point’s date; tested split/bonus boundary and weekly/daily alignment. | Pass for pinned transformations. Extreme-price/invalid dates and off-range geometry need more property testing. |
| Alert thresholds | GOLDIAM bonus-adjusted close threshold stayed active through the synthetic action boundary; daily/weekly/monthly × seven source controls. | Pass in tested browser/API paths. Correction after an alert fires and an incomplete period being revised later remain open cases. |
| Historical decisions do not use future actions | PIT fixture places a 1:1 bonus after decision date; as-of repository does not reshape earlier prices; future actions and future revisions are excluded/raise lookahead errors. | Pass in backend tests. |
| Historical universe membership | Listing/delisting as-of tests, PIT security repository, historical point-in-time screening path. | Pass in fixtures; index membership/ASM/T2T gaps remain explicitly documented by product architecture. |
| Manifests/config hashes | Snapshot manifest and revision are persisted; deterministic config+data version repeat; stored results remain append-only. Interrupted OOS retry uses same sealed manifest and snapshot ID. | Pass for tested Studio/PIT flows. |
| Existing results not silently rewritten | Screening result rows are append-only; exact completed screen identity is reused; R2 did not run migrations/imports against a non-isolated DB or rewrite research copies. | Pass in tested flows. Same-session corrected source data has no distinct date-only live screening identity yet; the completed snapshot remains unchanged and may be stale. |
| Corrected RS used consistently | Split-aware RS uses adjusted closes; ranks feed engines/gates and explanation result persistence. | Backend golden confirms RS output; no complete UI explanation text comparison on every split symbol. |

## Old research versus point-in-time results

The existing M14.7 rerun report analyzed eight dates in the `adjfix-recheck` series and compared stored results, today’s historical path, and point-in-time results. It recorded 84–98% qualified-set similarity for most sampled dates, but 2023-02-28 retained only 8 of 25 stored top names under current code. It attributed differences to later corporate actions reshaping old prices, as-of universe membership (including delisted names), and a raw-close RS defect later fixed in commit `18cab43`. The last-session copy showed 107 of 2,432 names with split/bonus in the prior year; after the fix, 71 of 2,882 rated names moved by 10+ points, and 28 names crossed RS≥70.

These are reproduced results from [`2026-10-19-m14-pit-rerun-report.md`](../2026-10-19-m14-pit-rerun-report.md), not new Round 2 calculations. That report’s historical copy was not the explicitly labelled R2 database, so Round 2 did not connect to it or risk mutating its state. It is not sufficient evidence to assert that every legacy research result has been migrated or re-run through PIT. Past production/research outputs remain as stored; this audit did not rewrite them.

## Unresolved financial risks and evidence limits

- Live run identity currently uses the latest session date as `data_version`. If a source correction changes bars on that same date for the same config, a distinct corrected live snapshot cannot be selected by this identity. Round 2 fixed duplicate invocation by reusing the old immutable result; it deliberately does not overwrite old rows. Introduce a stable data revision/manifest identity before claiming corrected-data replay.
- The historical rerun was not independently repeated on an R2-owned copy. A broader comparison across all old research configurations, historical revisions and delisted membership is still required before promoting legacy research conclusions.
- The synthetic golden set does not establish correctness for every corporate-action source code, multi-leg rights issue, demerger, split plus dividend on one date, backdated correction, or malformed provider payload.
- Dividend behavior is price-only by design; total-return performance with reinvestment is not implemented by these tests.
- Historical membership tests cover listing/delisting but do not establish historical index constituents or surveillance-flag availability where sources are absent.
- Data corrections after an alert has fired, later completion of partial week/month alert bars, and app restart during alert persistence were not exercised.

### Financial release disposition

No unexplained numerical discrepancy was found in the pinned synthetic invariants, GOLDIAM regressions, or MCX golden. The exact critical fixtures pass; however, due same-session source revision identity and the unrerun historical-copy comparison, the financial pipeline is **not declared comprehensively certified** for all real-world source corrections or legacy research outputs. No old results were recalculated or silently changed.
