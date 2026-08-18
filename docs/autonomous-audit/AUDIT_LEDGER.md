# Audit Ledger

Cycle log. Never overwrite prior entries — append only.

## Cycle 1 — Batch 1 (Core Data)
- Started: 2026-08-18
- Reviewer dispatched (read-only) to audit market data, securities, OHLCV, indicators (incl. pipeline_impl.py placeholder investigation), watchlist.
- Status: COMPLETE

## Cycle 1 — Batch 1 complete
- Findings: 2 total — 0 CRITICAL, 0 HIGH, 0 MEDIUM, 1 LOW (B1-001), 1 OBSERVATION (B1-002).
- Indicator placeholder investigation: `IndicatorPipelinePlaceholder` (domain/indicators/pipeline_impl.py) is confirmed dead code — not called from production. Real indicator math (RSI, MACD, ATR, ADX, Stochastic, Williams %R, CCI, ROC, SMA/EMA, ADR%) lives in `infrastructure/pipelines/indicator_pipeline.py::IndicatorPipelineImpl`, wired through dependencies.py/market_sync.py/screening_job.py, and is well covered by 11 test files. `/stocks/{symbol}/indicators/series` and the frontend catalogue receive real computed values, not None. Recommended: delete the placeholder file and its `__init__.py` export (autonomous fix allowed).
- Market data, securities OHLCV/search, watchlist (add/remove/detail), and data-freshness (`/health/data-freshness`, `web/src/app/data/page.tsx`) reviewed — all wired correctly end-to-end, no defects found.
- Capability registry note: row 5 (Technical Indicators) backend path and route location need correction — see B1-002.

## Cycle 1 — Batch 2 (Core Screening)
- Reviewer dispatched (read-only) to audit strategies, all 8 domain engines (trend_template, momentum_quality, relative_strength, breakout, pattern, volume_accumulation, risk, fundamental), scoring_engine.py, ranking_engine.py, gate logic.
- Status: COMPLETE

## Cycle 1 — Batch 2 complete
- Findings: 3 total — 0 CRITICAL, 0 HIGH, 0 MEDIUM, 2 LOW (B2-001, B2-002), 1 OBSERVATION (B2-003).
- B2-001 (LOW): `domain/rules/registry.py`/`base.py` — a `RuleRegistry`/`Rule` Protocol rule-dispatch abstraction with zero production or test callers, superseded by the actually-used per-engine evaluator-dict pattern and the real `domain/strategy/engine_registry.py`. Dead-code cleanup, no behavior change.
- B2-002 (LOW): `relative_strength.py` passes `security.sector` to `_eval_rs_industry_relative` instead of `security.industry`; currently cosmetic (the fallback explanation branch doesn't use the label) but wrong wiring. `industry_rs_percentile` scoring itself is correct and unaffected.
- B2-003 (OBSERVATION): Full review summary — gate correctness confirmed (`rank=None` for hard-filter failures, ranking only over the qualified set), hard-filter enforcement checked at both engine and rule level, all engines use Decimal arithmetic with no float leakage into scores, no wall-clock/random/hidden state found, boundary/missing-data handling is explicit and consistent across all 8 engines, formula spot-checks (52w-high/low %, downside-only risk_rr, ADTV turnover) match documented methodology. `FundamentalEngine` confirmed to be an intentionally disabled ADD §6 placeholder (registered but never enabled in any strategy config) — not a defect. No re-litigation of closed research (RP-000 risk_extension rejection not re-opened).
- Gate/scoring correctness: no CRITICAL/HIGH/MEDIUM findings. Core screening math is sound; both LOW findings are dead-code/mislabeling issues, not correctness bugs affecting production output.

## Cycle 1 — Batch 3 (Research: Walk-Forward Backtesting, Historical Screening, Validation, Experimentation, Analytics)
- Reviewer dispatched (read-only) to audit the newly-added `POST /backtest/walk-forward` API surface plus historical screening, validation, experimentation, and analytics frontends.
- Status: COMPLETE

## Cycle 1 — Batch 3 complete
- Findings: 3 total — 0 CRITICAL, 0 HIGH, 0 MEDIUM, 2 LOW (B3-001, B3-003), 1 OBSERVATION (B3-002).
- B3-001 (LOW): CLI `walk-forward` command lacks the `start > end` guard the new API router has; a reversed date range silently produces a spurious "0 rebalances, 0% return" report instead of erroring, unlike the API which 422s.
- B3-002 (OBSERVATION): Full walk-forward engine review — confirmed defense-in-depth no-look-ahead enforcement (runner re-checks every price date against `as_of`, provider independently clamps to `min(target, as_of)`), decision/fill dates are always different sessions (M-1 close decide, M first-session fill), determinism verified by dedicated tests plus an independent trade-log NAV reconstruction path, CLI and API share one wiring function so they cannot drift on providers. Ran `test_walk_forward.py` + `test_backtest_api.py`: 14/14 pass. Nifty 500 membership/T2T/ASM surveillance stub is honestly disclosed end-to-end (docstring → warning constant → API DTO field → visible UI caveat box) — a known, human-decision-blocked data gap, not a new defect, not re-litigated.
- B3-003 (LOW): Historical Replay page destructures `runsLoading` from its `useQuery` but never renders it — the "Available Historical Runs" empty state is indistinguishable from a genuine loading state for the duration of the initial fetch.
- No CRITICAL/HIGH/MEDIUM findings. The new backtest API is well-built: shared wiring with the CLI, explicit look-ahead guards, deterministic-by-construction NAV reconstruction, and an honestly-labeled data-quality caveat surfaced all the way to the UI.

## Cycle 1 — Batch 4 complete
- Findings: 1 total — 0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW, 1 OBSERVATION (B4-001).
- B4-001 (OBSERVATION): Full review of Elliott Wave analysis (pivots, patterns, fibonacci, personality, ranking, analysis orchestration), chart-pattern recognition, and stop-loss calculation. All three Elliott Wave cardinal rules correctly implemented as hard binary rejections (never traded off against guidelines); guidelines (alternation, Fibonacci ratio bands, personality) correctly never affect count admissibility, only ranking score. Fibonacci canonical ratios and per-wave projection-zone ranges independently checked against Frost & Prechter and are correct. Fully deterministic (Decimal-only arithmetic, no wall-clock/random, explicit tie-break ordering). Insufficient-history behavior degrades gracefully (empty pivots/counts with explanatory notes; personality checks degrade to "not measurable" on indicator-pipeline failure without failing the wave count). Chart rendering (`useElliottWaveChart.ts`) consumes only API-supplied fields, no client-side divergence from backend. Chart-pattern detection shares the same `zigzag_pivots` function as Elliott Wave (no second swing-point definition), enforces required-vs-optional criteria correctly, and is deterministic. Stop-loss lives in `domain/research/stop_loss.py` (ATR-based, with swing-low fallback and honest "unavailable" state), correctly separated from the `risk_rr` gate-scoring rule in `domain/engines/risk.py`. Ran `test_elliott_wave.py` + `test_chart_patterns.py`: 86/86 pass.
- No CRITICAL/HIGH/MEDIUM/LOW findings. This is the cleanest batch of the audit so far — Elliott Wave and chart-pattern recognition are rigorously built, well-documented against their literature sources, and show no software, math, determinism, or rule-consistency defects.

## Cycle 1 — Batch 5 complete
Scope: Frontend/Product — Dashboard, NavBar, mobile/desktop layout, loading/empty/error states, accessibility basics, cross-page metric consistency, Learn pages vs implementation, api-client.ts/types.ts vs backend DTOs.
Findings: B5-001 (LOW), B5-002 (LOW), B5-003 (OBSERVATION, review summary).
Severity counts: CRITICAL 0, HIGH 0, MEDIUM 0, LOW 2, OBSERVATION 1.
Notable: no cross-page metric drift found (rank/momentum_score/rs_rating render identically on Dashboard vs Watchlist); Learn/scoring-guide pulls weights live from the API so weight numbers cannot drift, and its qualitative engine descriptions matched Batch 2's verified engine logic. Both defects are cosmetic/type-hygiene only (duplicate nav icon, an unmodeled `unknown[]` field with no current reader) — no user-facing correctness or data-integrity issues found in this batch. Reviewed source-level only; did not run a live dev server.
