# State

As of 2026-10-19, branch `wickstreet/m10-m11` (local, never pushed): Wickstreet M9 to M15 and the M16 audit are complete; the focused release-hardening pass is verified. Public distribution is independent of direct exchange downloads, which now default off. Publication remains on hold for the proposed licence and Wickstreet name/trademark decisions. Before Wickstreet, the last code commit was `f492f81` (2026-08-18).

## Verdict

The screener, the explainability chain, the research tooling and the walk-forward backtest are built, tested and audited. The production strategy is `minervini_trend_template` v3. Its last change was on 2026-08-09: `risk_rr` moved from `min_ratio: 2.0` to `max_risk_pct: 16` (backlog Phase 3.2) and the strategy became active. The version number stayed at 3; `config_hash` tells the two configs apart.

The weak point is ranking quality, not software. Within the qualified set, ranking IC is negative: 120d mean IC −0.0384, t −2.43, over 63 monthly runs (2020-11 → 2026-01). Eleven research proposals tried to fix it. None passed hold-out. The binding constraint is data.

The single-user app has no authentication and must remain loopback-only. An unauthenticated network-exposed instance is not secure; add an authenticating proxy before any network exposure.

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

## Independent product audit, 2026-10-19

| Check | Result |
|---|---|
| Backend full suite | 815 passed, 2 deprecation warnings. |
| Web lint, Vitest, build | lint clean; 101 passed; production build clean with a 565.72 kB main chunk (182.13 kB gzip). |
| Playwright full suite | 108 passed, 6 opt-in benchmark cases skipped; all 26 documented routes hard-loaded. The six benchmark cases also passed separately. |
| NFR-11, 30 samples each | warm P95 165 ms; first chart open after fresh API process P95 482 ms (boot excluded). Both targets met. |
| M13 workspaces, 30 samples each | 1 chart warm/cold P95 185/201 ms; 4 charts 495/528 ms; 16 charts 1,772/1,785 ms. |
| Test data | Marked synthetic fixtures in a disposable tmpfs `*_e2e` database; no NSE automated downloads. |
| Evidence and limits | See [audit report](../../E2E_AUDIT_REPORT.md), [coverage](../../E2E_COVERAGE_MATRIX.md), [UX audit](../../UX_USABILITY_AUDIT.md), and [defect register](../../E2E_DEFECT_REGISTER.md). |

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
| 2026-10-18 | Wickstreet M11: chart workspace vertical slice | Engineering gate closed; owner usability assessment open | [report](../history/audits/2026-10-18-m11-vertical-slice-report.md) |
| 2026-10-18 | M11b weekly bars, M12 workspace shell, M13 professional charting, M15 daily alerts | Done; M13 and M15 accepted | [M11b](../history/audits/2026-10-18-m11b-weekly-report.md), [M12](../history/audits/2026-10-18-m12-shell-report.md), [M13](../history/audits/2026-10-18-m13-charting-report.md), [M15](../history/audits/2026-10-18-m15-alerts-report.md) |
| 2026-10-19 | M14 Strategy Studio: history tables, point-in-time port, manifests, families, evaluations, `/studio` | Done; every ADR-014 hard-gate test passes | [M14 report](../history/audits/2026-10-19-m14-strategy-studio-report.md), [re-run](../history/audits/2026-10-19-m14-pit-rerun-report.md) |
| 2026-10-19 | M16 release readiness | Focused hardening verified; publication on hold for owner decisions | [RC report](../history/audits/2026-10-19-m16-release-candidate-report.md), [hardening evidence](../../audit-evidence/benchmarks/release-hardening.md) |

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
| 5 | The research harness cannot apply parameter overrides: `apply_parameter_overrides` is never called. Every variant test so far was a one-off script. | `domain/research/services.py` |
| 6 | `rs_sector_relative`, `rs_industry_relative`, `rs_line_uptrend` are still registered after v3 removed them. The v3 description names a high-tight-flag detector that does not exist. | `domain/engines/relative_strength.py`, strategy JSON |
| 10 | Eleven dev-only npm advisories (typescript-eslint 7, tailwindcss 3 tool chain). Fixing them needs major upgrades. No runtime package is affected. | `web/package.json` |

Fixed in M14 and M16 (2026-10-19):

- **RS ratings read raw closes**, so a split inside the lookback read as a crash (MCX: −76% instead of +20%). This touched the live daily run. On the latest session, 28 names that failed the RS ≥ 70 gate now pass. Fixed in `18cab43`. **Not deployed:** the owner's running image is unchanged until rebuilt.
- **CI never ran a check.** Every run on `main` since 2026-08-17 failed with `ruff: command not found` and `pytest: command not found`: the steps called the tools outside the uv environment. They now use `uv run`, install with `--frozen`, and run `lint-imports` (was defect 4). Confirmed only by reading the logs, because nothing has been pushed since.
- **A look-ahead read was logged per symbol, not raised**, in historical screening. Fixed in `ad3d1c2`.
- **The Docker image ignored `uv.lock`.** It installed the newest versions that `pyproject.toml` allowed, so production ran other versions than the tests did (44 of 67 packages differed). The image now installs the lock, and the lock now holds the versions the production image runs.

Fixed in M10 and M11 (2026-10-18):

- **Chart attribution** (was defect 7). Every page footer now credits TradingView Lightweight Charts™ and links to tradingview.com. `/about` shows the NOTICE text.
- **The Docker image had no strategy configs.** `strategy_dir` pointed outside the image, so a fresh `docker compose up` skipped strategy sync with only a warning. The image now copies `docs/architecture/strategies/`; startup syncs 7 strategies.
- **Engine effectiveness dropped its `measurability` block.** The DTO had no such field, so Pydantic discarded it silently, and `/validation` crashed whenever engine rows existed. Regression test: `tests/unit/test_validation_dto_measurability.py`.
- **The chart's MAX range showed only the last 500 bars.** With no `from` date the OHLCV use case capped the series at 500 rows (about two years). It now returns the whole stored series. Regression test: `tests/unit/test_security_ohlcv_range.py`. *(M11)*
- **A fast second click lost a drawing anchor.** The chart library drops a second click inside its double-click window, so a quick two-click trendline never completed. Anchors are now placed from native clicks. *(M11)*
- **The web app's API URL setting never worked.** The client read `NEXT_PUBLIC_API_BASE`; Compose set `NEXT_PUBLIC_API_BASE_URL`. The app now calls same-origin `/api/v1`, so no setting exists.

Fixed during the 2026-10-19 E2E audit:

- **Walk-forward fills used the next session's adjusted close instead of its adjusted open.** The price-history port now returns adjusted opens, holdings are marked and rebalance quantities are sized at the open, and regression tests cover a corporate-action-adjusted open and a gap between open and close.
- **Historical replay used today's cumulative factors and active universe.** New `/historical`, validation backfill and experiment replays now capture and persist one point-in-time data manifest. Previously saved runs are preserved and labelled with a legacy-basis warning; they are not rewritten.
- **`POST /runs` left a pending row with no worker.** It now schedules the established background pipeline. An API regression stubs the provider, so no NSE request is made.
- **Zero rank values placed filtered names among qualified names.** The screener sorts unranked rows last and displays a dash with an explanation.
- **The mobile bottom navigation could cover the last page content.** The shared shell reserves safe-area-aware trailing space; a browser check confirms the chart status can scroll clear of it.
- **Fast chart search could lose an early key or close a newly reopened dialog.** The search input now receives focus explicitly and the redundant native-dialog close callback is removed; the interaction passed 20 repeated browser runs.

Release hardening (2026-10-19): direct exchange requests default off; normalized authorized CSV imports support EOD bars, corporate actions, and benchmark closes; `screen` evaluates stored data and the retired `ingest` command exits nonzero with its replacement path. The Data screen explains the offline import workflow. Playwright coverage exercises all 12 drawing tools through draw, select, move, recolor, undo/redo, delete, and reload; Strategy Studio insufficient-data and one-shot matured hold-out cases; corporate-action alert re-evaluation; and durable browser state after a named-volume database restart. See the release-hardening addendum in [E2E audit report](../../E2E_AUDIT_REPORT.md) for final check outcomes.

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

The app is a loopback-only, unauthenticated single-user application. A network-exposed instance is not secure without an authenticating proxy. Metrics exist, but there is no bundled Prometheus/Grafana service, alerting, log aggregation or staging environment. Detail: [production readiness](../operations/production_readiness.md), [deployment](../operations/deployment.md), [backup](../operations/backup.md).

## In flight

**Wickstreet** (started 2026-10-17). A self-hosted charting workspace on daily data, with Momentum25 as its engine and built-in screener. Its project licence remains proposed, so public source publication is on hold. [ADD Amendment A1](../architecture/ADD-amendment-A1.md) governs it.

- **Done:** M9 to M15 on branch `wickstreet/m10-m11`. The owner accepted M9, M10, M13, M15, ADR-013 and ADR-014. The owner's M11 usability assessment is still open.
- **Done:** M16 independent product audit. See the four audit deliverables linked above. The owner's M11 usability assessment is still open.
- **Distribution boundary:** direct NSE/BSE adapters are disabled by default; no automated NSE download is required for the public distribution. Operators can import data they are authorized to use through the documented offline CSV workflows. The optional adapter remains off unless source and use permissions are confirmed. See the [data-use review](../history/audits/2026-10-19-m16-nse-data-use.md), [README](../../README.md), and [deployment guide](../operations/deployment.md).
- **Publication decisions:** choose and accept a project licence ([ADR-015](../architecture/adr/ADR-015-licence.md) remains Proposed), complete Wickstreet name/trademark clearance, then authorize publication. The no-login app is for local loopback use; any network-exposed deployment needs an authenticating proxy. Deploying the RS fix remains an owner operation.
