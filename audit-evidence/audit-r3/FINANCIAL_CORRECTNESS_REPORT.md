# Financial Correctness Report — Round 3

Date: 2026-10-20. Branch `wickstreet/m10-m11`. No financial methodology was changed. Where a defect touches methodology, the audit stopped and recorded it (R3-B-09, R3-B-10).

## Verdict

| Area | Status |
|---|---|
| Adjustment factors, adjusted OHLCV and volume | **PASS** |
| Browser indicators (21 series) and backend indicators (RSI, ATR, ADX, MACD) | **PASS** |
| Weekly and monthly aggregation | **PASS** |
| RS ratings, eligibility, gates, scores, ranks (run #149) | **PASS** |
| Determinism (identical inputs, identical outputs) | **PASS** |
| Point-in-time look-ahead | **PASS** |
| In-Sample / hold-out boundaries | **PASS** |
| Run identity and same-session corrections (R2-LIMIT-01) | **PASS** (resolved) |
| Walk-forward backtest: reproducibility | **PASS** |
| Walk-forward backtest: fill and mark prices | **FAIL — open, owner decision (R3-B-09)** |
| Differences from spec §8 and the strategy config | **FAIL — open, owner decision (R3-B-10)** |

## How the checks were made

- **Reference code is independent.** `ref_financial.py` and `ref_eligibility.py` (worker) and `indicator_reference.py`, `aggregation_check.py`, `adjust_parity.py` (main session) import no Momentum25 code. They recompute from the spec formulas and compare with stored rows, API output or browser output.
- **Data.** Worker: a read-only dump of the real database restored into an isolated container (3,206,035 daily bars, 3,463 securities, 1,739 sessions from 2019-10-01 to 2026-10-19, run #149). Main session: GET-only calls and read-only SELECTs on the real database; fixtures for the browser maths.
- **Named symbols.** RELIANCE, TCS, MCX (1:5 split), GOLDIAM (split and 1:3 bonus), TRENT (bonus), SBC.

## Results

### Corporate actions and adjustment

| Check | Result | Evidence |
|---|---|---|
| Factor = product of priced split/bonus ratios with ex-date after the bar, 703 securities, 893,479 bars | 0 mismatches | `backend/ref_financial_run149.json` |
| Bars with a non-unit factor but no later action | 0 | same |
| Dividend rows ("other") that carry a ratio | 0, so dividends are not adjusted | same |
| API daily OHLC = stored `round(raw × adj_factor, 4)` | 0 mismatches over 1,739 bars each for MCX, RELIANCE, TCS | `ui/adjust_parity.py` |
| API volume = stored `raw / adj_factor` on factored rows | 1,544 of 1,544 (MCX), 1,252 of 1,252 (RELIANCE); unfactored TCS equals raw on all 1,739 | same |
| `adj_close = close × adj_factor` | Holds for the five named symbols except TRENT (max diff 0.18). Database-wide **22,328 rows differ by more than 0.0101** (max 0.25%); 925 sit in the current RS window | R3-B-18 (open, real-data write needs owner) |

### Indicators

| Check | Result |
|---|---|
| Browser: SMA, EMA, WMA, Bollinger, Keltner, Donchian, Ichimoku (tenkan, kijun), ATR, ATR%, RSI, Stochastic %K/%D, Williams %R, CCI, ROC, OBV, CMF, MFI, +DI/−DI, MACD (line, signal, histogram): 21 series × 300 bars | Equal to an independent pure-Python reference to 1e-9, warm-up gaps included. Mutation-checked: a 0.001 change in one reference value fails the test. `web/src/lib/indicators/golden.test.ts` |
| Backend: RSI14, ATR14, ADX14, MACD per bar on the 277-bar window, five symbols | Identical at 4 dp on every bar |
| Backend: SMA50/150/200, 52-week high and low and distances, SMA200 slope, ADR% | Match the API at 4 dp |
| **Not covered** | Supertrend, Parabolic SAR, linear-regression channel, pivot points, anchored VWAP and bands, rolling VWAP, swing levels. Their conventions differ between vendors, so a reference would only restate the code. They keep the property tests in `indicators.test.ts`. **NOT VERIFIED** against a golden reference. |

### Aggregation

| Check | Result |
|---|---|
| Weekly (ISO week) and monthly OHLCV rebuilt from daily bars: open of first session, max high, min low, close of last session, summed volume | 0 mismatches for RELIANCE, MCX, TCS, SBC on the real database (369 weekly, 85 monthly bars; SBC 222/56). The current week and month carry `partial = true`. `ui/aggregation_check.py` |
| Worker's check with volume as the sum of per-day `round(vol/f)` | 0 mismatches |
| Browser candle geometry against stored bars, both sides of a split, weekly, monthly, replay | `candle-anatomy.spec.ts`: 11 passed on the current build. See the note on wick size below. |

### Screening engine (run #149, 2026-10-19, `minervini_trend_template` v3)

| Check | Result |
|---|---|
| RS ratings over 3,073 equities | Match the stored value for all 1,338 scored names. One exact return tie in the universe. |
| Eligibility: equity, 277 bars, not stale (> 30 days), bar on the run date, 252 prior sessions, 50-session turnover mean ≥ 1e7, close ≥ 20 | 0 mismatches over 3,096 names. Exclusions: insufficient history 714, stale 453, below turnover floor 355, close floor 203, no bar 33. |
| Gate operators recomputed over 32,112 rule rows | 0 mismatches. 18 rows sit exactly at RS = 70 and pass (≥). |
| Hard-filter flag, rank order (momentum, then buy-setup, then RS, then id) | 0 mismatches, 0 tied ranks |
| Momentum and buy-setup scores from stored contributions | Max difference 0.0018. Cause: stored contributions are rounded to 4 dp; production sums unrounded values. |
| Gate boundaries | New unit tests pin each operator at, just above and just below its threshold (12 tests, commit `21f37c3`) |
| Two strategies on the same data (historical as of 2026-08-07) | Top-25 overlap 5 of 25, different top 5, different config hashes |
| Saved parameters drive the backend | `strategy-integration.spec.ts`: a saved config with `tt_rs_rating_min` = 99 passes only names with RS ≥ 99 and ranks none below. 7 of 7 pass. |
| Cross-screen values | SBC: momentum 70.5303 and setup 69.0352 are identical in `/rankings/runs/149`, `/stocks/SBC` and the screener row. Watchlist TCS carries run 149 and the same config hash. |

### Determinism, run identity, point in time

| Check | Result |
|---|---|
| Five independent full-universe screens and run #149 | SHA-256 of results, rules (with explanation text) and universe identical in all six; same `config_hash` |
| After all fixes, on a fresh restore | Byte-identical |
| Run identity, R2-LIMIT-01 | A second screen reused run 155. A same-session correction (RELIANCE 1202 → 1222) gave a new `data_version` and run 156. Run 155 was unchanged (hash, `finished_at`). RELIANCE score 32.07 → 36.64. **Resolved.** |
| Look-ahead | Historical run as of 2026-08-07, then in the copy: ×3 prices on 17,510 later bars, 4,349 later bars deleted, a future split for 3 symbols, 2 future delistings. The rerun gave identical results, rules and universe hashes. |
| In-Sample / hold-out | Independent calculation equals production: hold-out 2023-01-02 → 2025-12-31; In-Sample 2020-11-12 → 2022-07-06; last In-Sample forward exit 2022-12-30, before the hold-out. One-shot sealing is covered by integration tests in the green suite; not re-run end to end here. |
| Walk-forward reproducibility | Two runs (2025-01 → 2026-07) have identical SHA-256. 19 rebalances, every fill dated after its decision. |

## Open financial findings

### R3-B-09 (P1, methodology — STOP) Walk-forward fills use a stale price

For a name with no bar on the fill date, the engine fills and marks at the last earlier bar. This is 176 of 649 trades, 27% of notional, and contradicts the code's own docstring ("skip"). Example: 3PLAND bought on 2025-01-01 at 81.50, last bar 2024-12-18. Evidence: `backend/walkforward/` (`stale_fills.txt`, `trades.csv`).

- **Impact.** Backtest return and turnover figures include fills at prices the market did not offer on that day. It biases results toward illiquid names. The live screener is not affected.
- **Why no fix.** Choosing the policy (skip, fill at next available bar, or carry cash) changes backtest results. That is methodology.
- **Verification once decided.** Zero trades fill on a date without a bar; the backtest is re-baselined and every backtest figure quoted in research notes is refreshed.

### R3-B-10 (P2, methodology — STOP) Four differences from spec §8 and the strategy config

1. RS is ranked over all equities, not over eligible names (1,253 of 1,338 ratings change; 39 cross 70).
2. `rel_volume` uses a 49-session prior mean.
3. EMA uses a first-value seed (the browser indicators use an SMA seed, the textbook form).
4. The rank tie-break is `security_id`, not `symbol`.

Owner decides per item: amend the spec to match the code, or change the code.

### R3-B-08 (P1, fixed, owner to confirm) Read-path RS ranked ETFs and funds

`/stocks/{symbol}/live` and the watchlist ranked RS over every active security, including fund and ETF units. The screening, historical and evaluation paths rank equities only. On 2026-10-19, 2,679 equities got a different rating on the read path and 101 crossed the RS ≥ 70 gate (RELIANCE 30 live against 34 in run #149). Commit `51f3239` filters equities like the run and moves the cache key to v2. **No run output changes** (run #149 hashes are byte-identical). It is a consistency fix, but it moves displayed numbers on the live and watchlist views, so the owner should confirm it. To undo: revert `51f3239`.

### Other

- R3-B-13 (P2). `/live` reports `data_as_of` = today and `data_sufficient` = true for stale stocks (ITETFADD, last bar 2025-12-12). The web reads this field.
- R3-B-14 (P2). The RS cache is keyed by name and date with a 6-hour TTL, so same-day corrections are ignored on the read path.
- R3-B-17 (P3). Historical `data_version` uses a wall-clock suffix.
- R3-U-09 and R3-B-12 (P2, same root cause). The manifest records `git rev-parse HEAD` on every capture. On a development host `data_version` changes with each commit for identical data (one of my E2E assertions failed this way while the worker committed). In the container there is no git, so it records `null`, and tonight's job will write a duplicate 2026-10-19 snapshot. **Fixed in source** (`8e5922d`, ADR-014 §10). `data_version` now hashes the market data (revision, calendar version) and the engine (`INDICATOR_VERSION`, rule-registry version). The strategy configuration keeps `config_hash`. The build id (`M25_BUILD_ID`, else the git commit read once per process, else null) is stored in the manifest but never hashed. Bodies without `identity_schema` keep the old hash rule, so every stored key still loads (run 149's `8790a000bd4f` is reproduced in a test). Tests show the same data gives the same `data_version` across commits and with no git, and that it changes with revision, indicator version, registry version and calendar. **Owner decision (Q4):** a scoring or ranking code change that alters results without bumping `INDICATOR_VERSION` or the registry is no longer visible in `data_version`; adding an `ENGINE_VERSION` constant would close that. Observed before the fix on the real database: run 150 equals run 149 in results (hash `8e1a3aed…`) and differs only in the manifest's commit (null against `5961b9c…`) at the same revision 133621.

## Note on candle wick size (asked mid-audit)

The earlier wick-size defect has **not** returned. The candle rendering code is unchanged by this audit; `PriceChart.tsx` differs by two colour class names. The geometry tests that guard the earlier fix pass on the current build (candle-anatomy 11, openchart-parity, m13-charting: 38 passed). A 3-month `E2ECANDLE` chart shows distinct wicks per candle (`ui/candle-wicks-e2ecandle-3M.png`).

## Limits of this report

- Real-data recomputation ran on a restored dump of the development database, not on a second source of market data. It proves the code computes what the spec says. It does not prove the exchange data is right.
- Indicators without a vendor-neutral convention are not golden-checked (listed above).
- The main session spot-checked the worker's evidence (commit list, test counts, the R3-B-09 trade list). It did not repeat the worker's full-universe recomputation.
