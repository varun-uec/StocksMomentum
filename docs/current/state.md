# State

As of 2026-10-18, branch `wickstreet/m10-m11`: Wickstreet M10 (Vite web app served by the API), M9 (reference study) and M11 (chart workspace vertical slice). Before that, the last code commit was `f492f81` (2026-08-18).

## Verdict

The screener, the explainability chain, the research tooling and the walk-forward backtest are built, tested and audited. The production strategy is `minervini_trend_template` v3. Its last change was on 2026-08-09: `risk_rr` moved from `min_ratio: 2.0` to `max_risk_pct: 16` (backlog Phase 3.2) and the strategy became active. The version number stayed at 3; `config_hash` tells the two configs apart.

The weak point is ranking quality, not software. Within the qualified set, ranking IC is negative: 120d mean IC −0.0384, t −2.43, over 63 monthly runs (2020-11 → 2026-01). Eleven research proposals tried to fix it. None passed hold-out. The binding constraint is data.

Deploy only on a private network. There is no authentication.

## Checks run on 2026-10-18

| Check | Result |
|---|---|
| `lint-imports` | 2 contracts kept, 0 broken |
| `ruff check src tests` | clean |
| `mypy src` (strict) | clean, 234 files |
| `pytest` (full suite, PostgreSQL up) | 684 passed (638 before M10; +21 in M10, +25 in M11) |
| Web `npm test` (Vitest) | 49 passed |
| Web `npm run lint` / `npm run build` | clean |
| Web `npm run e2e` (Playwright, against a database clone) | 37 passed, stable over repeated runs |
| NFR-11 chart open, 10 years of bars, 30 runs each | warm P95 115 ms (≤ 1 s); cold P95 156 ms (≤ 3 s) |

## Delivery record

| Date | Work | Outcome | Record |
|---|---|---|---|
| before 2026-08-08 | MVP milestones M0–M8 (git history starts 2026-08-08) | Shipped | [ADD §27](../architecture/ADD.md#27-implementation-roadmap) |
| 2026-07-01 → 07-03 | Research programs RP-000 → RP-013, dataset v1.0 | 0 promoted; dataset frozen | [research/](../research/) |
| 2026-08 | Phased backlog 0–9: correctness fixes, live lookup, indicators, stop-loss, coverage, stock detail, Elliott Wave, chart patterns, charting | Shipped, except Phase 3/3b swing targets (failed hold-out) and Phase 4 base-rate panel (blocked by Phase 3) | below |
| 2026-08-09 | Functional audit | Findings fixed | [history/audits](../history/audits/2026-08-09-functional-audit.md) |
| 2026-08-10 | Unified analysis screen | Shipped | [plan](../history/plans/2026-08-10-unified-analysis-screen-plan.md) |
| 2026-08-10 | RP-014: legacy NSE (1994→) and BSE (2006→) history | Loaded | [report](../research/2026-08-10-rp014-historical-data-extension-report.md) |
| 2026-08-11 | UI/UX audit | Fixes applied | [report](../history/audits/2026-08-11-ui-ux-audit.md) |
| 2026-08-15 | Functional audit F1–F20 | All confirmed items fixed (`b9de0a1`) | [report](../history/audits/2026-08-15-functional-audit.md) |
| 2026-08-15 | UI/UX audit (Investing.com benchmark) | Recommendations only. Not applied. | [report](../history/audits/2026-08-15-ui-ux-audit.md) |
| 2026-08-16 | Market-data refresh page | Shipped | commit `4a76f19` |
| 2026-08-17 | Walk-forward backtest: Builder/Reviewer loops 1, 2, approximations, 3 | Each loop ended in PASS | [backtest-loop](../history/backtest-loop/) |
| 2026-08-18 | Autonomous audit, 6 batches | PASS. 15 findings, 7 LOW fixed, 0 open | [final report](../history/autonomous-audit/FINAL_REPORT.md) |
| 2026-10-18 | Wickstreet M10: Vite SPA served by the API, Host/Origin guard, loopback binding | S1–S7 pass; ADR-013 awaits acceptance | [spike report](../history/audits/2026-10-18-m10-stack-spike-report.md) |
| 2026-10-18 | Wickstreet M9: reference study, wireframes, design record | For review | [study](../history/plans/2026-10-18-m9-reference-study.md) |
| 2026-10-18 | Wickstreet M11: chart workspace vertical slice | Built and tested; awaits the M11 review gate | [report](../history/audits/2026-10-18-m11-vertical-slice-report.md) |

**Swing targets (Phase 3/3b).** Hold-out from 2025-01-01: 3,211 trades, hit rate 64.0%, average R −0.021. Six exit-plan variants all made average R worse in-sample (−0.105 to −0.396). Closed. The stop-loss part shipped as a risk-only figure. Log: [phase3b](../research/2026-08-phase3b-target-methodology-log.md).

## Research verdicts

| Line of work | Verdict | Record |
|---|---|---|
| RP-000, RP-001, RP-003, RP-007 — re-weight or re-compose the ranking | Rejected on hold-out | [director cycle report](../research/2026-07-02-research-program-director-cycle-report.md) |
| RP-002 — audit of qualified-set IC | Negative, not the +0.028 reported earlier | same |
| RP-004, RP-005, RP-009 → RP-011 — new characteristics | Rejected or wrong sign | same |
| RP-006 — structural or regime-driven? | Underpowered. Only 2022 is determinate. | same |
| RP-012 → RP-014 — historical data foundation | Built. 1994 → today. | [dataset v1.0](../research/2026-07-03-research-dataset-v1.0-baseline.md), [RP-014](../research/2026-08-10-rp014-historical-data-extension-report.md) |
| 2026-08-09 methodology review: P-1 breakout weight, P-2 vol-scaled momentum, P-4 RS skip-month | All rejected on hold-out | [review](../research/2026-08-09-momentum-selection-methodology-review.md), [validation](../research/2026-08-10-ranking-fix-validation-report.md) |

**Standing decision:** do not re-weight the existing engines. Ranking research stays frozen until the data below exists. One unvalidated lead is parked: `risk_extension` dispersion against per-run IC (ρ −0.231, p 0.0018).

Reports dated before 2026-08-10 quote database row counts from their own date. The database was rebuilt between reports, so those counts do not agree with each other.

## Open defects

Found while writing these docs. Not fixed.

| # | Defect | Where |
|---|---|---|
| 1 | Walk-forward fills at the first session's adjusted **close**. The brief (§5) says **open**. The loop reviews checked that decision and fill dates differ, not the price field. | `walk_forward.py::_apply`, `SqlPriceHistoryProvider` |
| 2 | `POST /runs` creates a `PENDING` run that nothing executes. | `routers/runs.py`, `use_cases/runs.py` |
| 3 | CLI `ingest` and `screen` are stubs. | `interface/cli/main.py` |
| 4 | `lint-imports` is not in CI. | `.github/workflows/ci.yml` |
| 5 | The research harness cannot apply parameter overrides: `apply_parameter_overrides` is never called. Every variant test so far was a one-off script. | `domain/research/services.py` |
| 6 | `rs_sector_relative`, `rs_industry_relative`, `rs_line_uptrend` are still registered after v3 removed them. The v3 description names a high-tight-flag detector that does not exist. | `domain/engines/relative_strength.py`, strategy JSON |
| 8 | Historical screening applies today's cumulative `adj_factor` to past dates, so a later split rescales earlier prices that price-level gates read. | `infrastructure/pipelines/indicator_pipeline.py::_to_dataframe` (ADR-014 §7) |
| 9 | Historical screening reads bars only for `is_active` securities, which may drop names delisted after the decision date. Not yet verified against past runs. | `indicator_pipeline.py::_fetch_bars` (ADR-014 §7) |

Fixed in M10 and M11 (2026-10-18):

- **Chart attribution** (was defect 7). Every page footer now credits TradingView Lightweight Charts™ and links to tradingview.com. `/about` shows the NOTICE text.
- **The Docker image had no strategy configs.** `strategy_dir` pointed outside the image, so a fresh `docker compose up` skipped strategy sync with only a warning. The image now copies `docs/architecture/strategies/`; startup syncs 7 strategies.
- **Engine effectiveness dropped its `measurability` block.** The DTO had no such field, so Pydantic discarded it silently, and `/validation` crashed whenever engine rows existed. Regression test: `tests/unit/test_validation_dto_measurability.py`.
- **The chart's MAX range showed only the last 500 bars.** With no `from` date the OHLCV use case capped the series at 500 rows (about two years). It now returns the whole stored series. Regression test: `tests/unit/test_security_ohlcv_range.py`. *(M11)*
- **A fast second click lost a drawing anchor.** The chart library drops a second click inside its double-click window, so a quick two-click trendline never completed. Anchors are now placed from native clicks. *(M11)*
- **The web app's API URL setting never worked.** The client read `NEXT_PUBLIC_API_BASE`; Compose set `NEXT_PUBLIC_API_BASE_URL`. The app now calls same-origin `/api/v1`, so no setting exists.

Architecture-level differences from the ADD are listed in [architecture.md](architecture.md#drift-from-the-add).

## Data gaps

| Gap | Effect |
|---|---|
| No point-in-time Nifty 500 membership, T2T or ASM history | Backtest eligibility check is a labelled stub. |
| No Nifty 500 TRI | Backtest benchmark is the price index, labelled "not TRI". |
| `securities.sector` / `.industry` empty | No sector RS. Market-context sector panel is empty and says why. |
| Corporate actions start at 2011-01-06 (NSE API: 20 rows per symbol) | Earlier bars are unadjusted. |
| Legacy archives keep their original adjustment factors | The corporate-action refresh updates `ohlcv_daily` only. Re-run the legacy backfill to re-adjust. |
| No correction-spanning hold-out fold with matured returns | Ranking research cannot test regime claims. |
| Data freshness is operational | Rankings describe the latest ingested bar. Check `GET /health/data-freshness`. |

Several thresholds are editorial, not validated: pattern-detector constants, the risk stop-distance cap, Elliott Wave ranking weights, forward-return tier boundaries.

## Operations

Ready for private deployment. Missing for public deployment: authentication, a monitoring stack (metrics exist; no Prometheus or Grafana service), alerting, log aggregation, staging. Detail: [production readiness](../operations/production_readiness.md), [deployment](../operations/deployment.md), [backup](../operations/backup.md).

## In flight

**Wickstreet** (started 2026-10-17). An open-source, self-hosted charting workspace on daily data, with Momentum25 as its engine and built-in screener. [ADD Amendment A1](../architecture/ADD-amendment-A1.md), ADR-012 and ADR-014 are Proposed; ADR-011 and ADR-013 are accepted. M10 (stack spike), M9 (reference study) and M11 (chart workspace vertical slice) are done on branch `wickstreet/m10-m11`; the owner accepted M9 and M10. The M11 engineering gate closed on 2026-10-18 after four corrections and four checks: see the [M11 report](../history/audits/2026-10-18-m11-vertical-slice-report.md). The owner's usability assessment is still open. M11b (weekly bars, data version) is done: see the [M11b report](../history/audits/2026-10-18-m11b-weekly-report.md). M12 (workspace shell) is done: see the [M12 report](../history/audits/2026-10-18-m12-shell-report.md). M13 (professional charting: twelve drawing tools, indicator dialog, context menus, chart types and scales, monthly bars, compare, layouts up to 4 × 4 with sync) is done: see the [M13 report](../history/audits/2026-10-18-m13-charting-report.md). Next: M15 (daily alerts); M14 (Strategy Studio) waits for ADR-014. Open: ADR-015 licence.
