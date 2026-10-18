# M11b Report — Weekly Bars and Data Version

> **Date:** 2026-10-18 · **Branch:** `wickstreet/m10-m11` · **Plan:** [milestones](../plans/2026-10-18-wickstreet-milestones.md) · **Design:** ADR-013 §4

## What changed

| Part | Result |
|---|---|
| Weekly bars | `GET /securities/{symbol}/ohlcv?interval=1W`. One bar per ISO week of NSE sessions: open of the first session, highest high, lowest low, close of the last session, summed volume, dated at the last session. Built from adjusted daily bars only. |
| `partial` | True when the calendar has a session in the bar's week after its last session. Deterministic: it reads the data and the calendar, never the clock. |
| Weekly indicators | `GET /stocks/{symbol}/indicators/series?interval=1W` runs the snapshot's own RSI, ATR, ADX and MACD functions on weekly bars. Nothing is resampled from daily values. |
| `data_version` | On every price and indicator-series response: a 12-character hash of the symbol's stored bars (raw prices, volume, `adj_factor`) and `INDICATOR_VERSION`. One symbol's price and indicator series carry the same version when built from the same data. |
| Interval switch | D and W buttons on the chart workspace, apart from the range buttons. Saved per chart (`ChartV1.interval`). Research screens stay daily, because they mark daily signals. |
| Drawings | On weekly bars, a point shows on the bar of its ISO week. Its saved date and traded price change only when the owner moves it. |

## Golden tests (exit criteria)

| Case | Test |
|---|---|
| Holiday week | `test_a_holiday_week_is_one_bar_dated_at_its_last_session` |
| Partial week | `test_a_week_still_running_is_partial` |
| Corporate-action week | `test_a_corporate_action_week_has_no_jump_inside_it` (unit); `test_the_bonus_week_is_one_weekly_bar_on_the_adjusted_basis` (API, GOLDIAM's real bonus week of 6 July 2026) |
| Week with no sessions | `test_a_week_with_no_sessions_has_no_bar` |
| ISO year boundary | `test_iso_weeks_cross_the_new_year` |
| Weekly indicators are not a resample | `test_weekly_indicators_are_computed_on_weekly_bars` |
| One data version | `test_price_and_indicator_series_share_one_data_version`; `test_daily_and_weekly_responses_share_one_data_version` |

## Verification

| Suite | Result |
|---|---|
| Backend `pytest` | 706 passed |
| `ruff check`, `mypy --strict`, import contracts | clean |
| Web Vitest | 71 passed |
| Web ESLint, build | clean |
| Playwright | 46 passed. The M11 and M11b specs passed 3 repetitions in a row (48/48). |
| NFR-11 chart open (30 runs each) | Warm P95 165 ms (target ≤ 1 s); cold P95 200 ms (target ≤ 3 s) |

NFR-11 rose by about 30 ms over M11. The likely cause: the indicator-series request now also loads the whole price history to compute `data_version`, and it competes with the price request on the one test server. Both figures stay far inside their targets.

## Decisions taken

- **`data_version` is a content hash until M14.** ADR-013 named the latest ingest run as an input, but no ingest-run record exists. A hash of the stored inputs is stricter: it also catches corrected prints and refreshed factors.
- **`partial` reads the calendar, not the clock**, so the same data always gives the same bars.
- **Weekly is offered only in the chart workspace.** The analysis and Elliott Wave screens place daily signal markers.
- **`spec=` waits for M13 and M15.** M11b serves the four existing panes.

## Not in M11b

Monthly bars (M13), indicator specs by catalogue id (M13, M15), panes that follow the price range (M12).
