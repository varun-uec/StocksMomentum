# Phase B evidence

Evidence for B1–B4 of the [TradingView-workstation plan](../../docs/history/plans/2026-10-19-tradingview-workstation-plan.md), captured on 2026-10-20. B5 Volume Profile is deferred. Phase C has not started.

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
