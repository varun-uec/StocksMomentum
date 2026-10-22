# Phase B evidence

Evidence for B1–B4 of the [TradingView-workstation plan](../../docs/plans/shipped/2026-10-19-tradingview-workstation-plan.md), captured on 2026-10-20. B5 Volume Profile is deferred. Phase C has not started.

## Final visual sign-off continuation (2026-10-20)

Resumed from `a5cb551`. Application verification source: `1ed0dd8`. The results below supersede the earlier run totals later in this historical evidence index.

- [Refreshed sign-off PDF](wickstreet-phase-b-signoff.pdf): 26 rendered and inspected pages, with 28 screenshots.
- [Standalone sign-off page](signoff.html): the same reviewed workflows and figures, with embedded images and no external resources.
- [Final verification record](final/verification.json), [raw logs](final/logs/), [document QA](final/document-qa.json).

| Check | Final result |
| --- | --- |
| Full serial production-build browser suite | **227 passed, 0 failed, 0 skipped**; includes all six opt-in benchmarks and two sign-off capture journeys |
| Backend | **921 passed**; strict mypy on 263 source files; both import contracts; touched-test Ruff |
| Web | **141 unit tests passed**; zero-warning lint, typecheck and production build |
| NFR-11, 30 warm / 30 fresh-API cold runs | P95 **166 ms / 505 ms**, within 1 s / 3 s |
| Isolated 16-chart repeat | Warm P95 **1,361 ms**, cold P95 **1,383 ms**, pan P5 **61 fps**, heap max **85 MB** |
| Phase A standalone comparison | 1,361 ms is **5.7%** above 1,288 ms, within the 10% comparison target |
| Responsive and accessibility | All 26 routes × 2 themes × 4 viewport sizes; 200% equivalent reflow; axe, keyboard, touch and save/recovery checks passed |

The full-suite 16-chart warm P95 was **1,483 ms**. The isolated repeat above followed on a fresh synthetic database without the preceding research workload. Both [full-suite](final/m13-bench-full-run.json) and [isolated](final/m13-bench.json) raw samples are retained. This variation does not prove a cause or a speed improvement from the interval fix. NFR-11 cold restarts the API process and excludes its boot time; M13 cold starts a fresh browser context with the API already running. Measurements are specific to the recorded machine and fixture data.

Additional safeguards completed:

- `fea198b`: an integration test inserts the exact E2ECANDLE fixture and proves unchanged daily screening/rankings, live RS, market breadth and point-in-time equity results. The raw point-in-time repository intentionally retains inactive identities; equity screening excludes this fund-unit fixture.
- `1ed0dd8`: fixing the representative screenshots exposed an interval-loading viewport race. The chart now uses the interval of its actual displayed bars until the requested series arrives. A deliberately delayed weekly response verifies that a range chosen during loading still shows the full year.
- The nine representative candle views and light/dark drawing examples were recaptured after both the axis-label and interval fixes. E2ECANDLE is synthetic. Retained screener, TCS replay, alert and flyout images are also synthetic fixtures; they demonstrate the established B1–B4 workflows.
- The refreshed PDF was rasterized and every page reviewed. Text bounds and missing-glyph checks passed; the standalone page contains 28 valid embedded PNGs and no external image/font dependencies.
- General regression PNG changes were restored. No PNG changes remain in the working tree. The report's reviewed images are embedded in the HTML/PDF.

The application preview runs locally at `http://127.0.0.1:8772/chart/E2ECANDLE`, against the synthetic verification database only. Scheduler and exchange downloads are disabled. No real financial data was changed and nothing was pushed. B5 remains deferred by the owner; Phase C has not started. Product visual acceptance remains the owner's decision.

### Reproduce the sign-off artifacts

Use a fresh, marked `*_e2e` database. Capture PNGs outside the working tree:

```sh
cd web
SIGNOFF_EVIDENCE_DIR=/tmp/wickstreet-phase-b-final/shots E2E_DATABASE_URL=<isolated-database-url> npx playwright test e2e/phase-b-visual-signoff.spec.ts
```

Then run from the repository root with ReportLab installed in a temporary environment:

```sh
uv run --with reportlab python scripts/build_phase_b_signoff.py --verification audit-evidence/phase-b/final/verification.json --captures /tmp/wickstreet-phase-b-final/shots --output-dir audit-evidence/phase-b
```

The verification JSON points to committed benchmark records. The generator refuses mismatched source commits and missing captures. `.dashboard/index.html` tracks this continuation locally; it remains ignored by the repository as before.

## Earlier Phase B evidence

## Data

Every capture and benchmark ran against the synthetic, marked `*_e2e` database. Prices, scores and runs are fixture data, not market data. Symbols such as `TCS`, `INFY` and `RELIANCE` are fixture rows with synthetic prices. The screenshots show no credentials, paths or personal data.

## Files

| File | What it shows |
| --- | --- |
| [`screenshots/01`–`04`](screenshots/) | B1: range popover, saved-screen menu, saved screen after a reload (dark), screener at 390 px |
| [`screenshots/05`–`09`](screenshots/) | B2: replay before any run, replay on the run date, bottom screener in replay, dark theme, 390 px |
| [`screenshots/10`–`12`](screenshots/) | B3: all nine new drawing tools (light, dark) and the five rail flyouts |
| [`screenshots/13`–`15`](screenshots/) | B4: "Alert on this line…" menu, prefilled ray alert form, fired ray alert |
| [`nfr11.json`](nfr11.json) | NFR-11 chart open, 30 warm and 30 cold runs, on `0d9ceb1` |
| [`m13-bench.json`](m13-bench.json) | 1, 4 and 16 charts: open, pan FPS and heap, on `0d9ceb1` |
| [`m13-bench-phase-a.json`](m13-bench-phase-a.json) | The same benchmark at Phase A (`35883c9`), the baseline for the 16-chart comparison |

Screenshots 01–12 were captured after `0d9ceb1`. Screenshots 13–15 were captured after `c22be94`, which fixed the alert-form note. All are 1440 × 900 except the 390 px phone views and the flyout crops.

The full-screen set for A9.1 (four screens × four widths × two themes, with `geometry.json`) is in [`../tradingview-clone/`](../tradingview-clone/). It comes from the same final full run on `0d9ceb1`.

## Results

| Measure | Result | Limit |
| --- | --- | --- |
| Full serial E2E, Playwright, `0d9ceb1` | 208 passed, 0 failed, 6 skipped | — |
| Backend pytest | 920 passed | — |
| Web unit tests (vitest) | 141 passed | — |
| Chart open, warm P95 | 165 ms | ≤ 1,000 ms |
| Chart open, cold P95 | 479 ms | ≤ 3,000 ms |
| 16 charts, warm open P95 | 1,351 ms (Phase A 1,288 ms, +4.9%) | +10% over Phase A |
| 16 charts, pan P5 | 61 fps | — |

The 6 skips are the opt-in layout benchmark (`M13_BENCH=1`). It ran on its own on the same commit; `m13-bench.json` holds its output. The E2E totals come from the run log. The backend and web totals come from the sign-off run; their logs were not kept.

Hardware: Apple M4 Pro, 48 GB, headless Chromium 153, 1280 × 720 for the benchmarks. The numbers hold only for this machine and the synthetic histories.

## Candle anatomy

On visual review, every candle in the screenshots above had near-identical wicks. The cause is the synthetic data, not the chart. The seed in [`web/e2e/db.py`](../../web/e2e/db.py) sets each bar's high to open × 1.01 and its low to open × 0.99, and its close within 0.2% of the open. On 2,610 TCS bars the upper and lower wicks measured 0.80–1.00% of the open, and no body exceeded 0.20%. The API, the corporate-action adjustment, weekly and monthly aggregation and the chart all pass each bar's own open, high, low and close.

Screening goldens depend on those fixtures, so they stay as they are. A new chart-only fixture, `E2ECANDLE`, has 525 deterministic sessions from 2024-08-05 to 2026-08-07, with a 1:2 split on 2026-06-22. Its wicks run from 0 to 5.6% of the open and its bodies from 0 to 6.3%. It has doji, hammers, shooting stars, strong-bodied bars, gaps of up to 5% and volatility that changes every 60 sessions. It is inactive and has a fund-unit ISIN, so no screening, breadth, RS or point-in-time universe reads it. The screening seed still evaluates 22 names and qualifies 7.

[`web/e2e/candle-anatomy.spec.ts`](../../web/e2e/candle-anatomy.spec.ts) reads the price pane's pixels. It requires every drawn wick and body edge to lie within 1 px of one linear price scale fitted to the bars' high, low, open and close. It covers daily bars on both sides of the split, weekly and monthly bars, and replay before the split. A deliberate change that drew fixed ±1% wicks failed all 4 tests by 56–94 px.

| File | View |
| --- | --- |
| [`candles/01`–`05`](candles/) | Light, 1440 × 900: daily 6M, daily 3M, weekly 1Y, monthly MAX, replay on 2026-06-12 |
| [`candles/06`–`07`](candles/) | Dark, 1440 × 900: daily 3M, weekly 1Y |
| [`candles/08`–`09`](candles/) | Phone, 390 × 844: daily 3M, light and dark |

The replay view shows prices near 2,376. That is correct: on 2026-06-12 the split had not happened, so replay shows the prices as they stood then. With this fixture, the full serial E2E run gave 212 passed, 0 failed and 6 skipped. The web unit tests gave 141 passed.
