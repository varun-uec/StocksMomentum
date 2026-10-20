# Owner Decision Packet — R3-B-09 and R3-B-10

> **Superseded in part (2026-10-20, Stage A).** After the owner direction, [STAGE_A_FINANCIAL_METHODOLOGY_SPEC.md](STAGE_A_FINANCIAL_METHODOLOGY_SPEC.md) §1 changes the defaults for B09-1 (buys use the next eligible session), B09-5 (10% participation cap) and B10-4 (the direction conflicts with ADD §21). It also adds R3-B-30 to R3-B-32. This packet's evidence and numbers stand unchanged.

Date: 2026-10-20. Branch `wickstreet/m10-m11` at `2506150`. Data: development database, `ohlcv_daily` revision 133621 (3,206,035 bars, last session 2026-10-19), read with `default_transaction_read_only=on`.

**This packet changes no code, specification, ADR, strategy or stored result.** Every number below comes from the scripts in [`backend/decision-packet/`](backend/decision-packet/). Each script reads a read-only CSV export ([`export.sh`](backend/decision-packet/export.sh)) and runs in memory. No database was written, restored or created.

Terms used with one meaning throughout:

- **Fill date (F):** the first session of a month, when the backtest trades. **Decision date (D):** the session before F.
- **Stale fill:** a trade priced from a bar dated before the fill date.
- **Stale mark:** a valuation that uses a bar dated before the valuation date.
- **Bar on X:** an `ohlcv_daily` row for the security dated exactly X.
- **Current engine:** `WalkForwardRunner` at `2506150`. **Reference simulator:** [`sim.py`](backend/decision-packet/sim.py). It imports no backtest or domain code.

---

## 1. Decision summary

Each question has a recommended default. Nothing is implemented until you approve.

| # | Question | Recommended default | Section |
|---|---|---|---|
| **B09-1** | Fill policy | **EXEC-1** (policy D in §3): buys fill at the fill-date open or are cancelled. Sells fill at the fill-date open, or else at the open of the next session with a bar. No stale fill, ever. | 3 |
| **B09-2** | Score a name with no bar on the decision date? | **No.** Brief §2 defines `price(t)` on the decision date. The code's own docstring says "never scored on a … forward-filled price". | 2.3 |
| **B09-3** | Value of a held name that has stopped trading | **Last adjusted close, flagged.** Every result also reports the NAV with those names at zero, as a lower bound. | 3.4 |
| **B09-4** | Cash when buys cannot fill, or sells are stuck | **No leverage.** Cash from a cancelled buy stays cash until the next rebalance. Buys scale pro rata when cash is short. | 3.4 |
| **B09-5** | Fill size against the session's traded value | **No capacity model** (the data cannot support one). Report participation and flag fills above 10% of the session's traded value. | 4.5 |
| **B09-6** | Backtest universe defects R3-B-27 (dual-listed names excluded) and R3-B-28 (353 ETFs and fund units included) | **Fix both in the same method version as B09-1.** Both contradict brief §1. | 2.2 |
| **B09-7** | Method versioning | `BACKTEST_METHOD_VERSION = 2`, plus the data manifest and the policy constants in every response. No legacy mode in code: you reproduce v1 from a pre-fix commit. | 5.1 |
| **B09-8** | Release gate G3 after the fix | **G3 passes for fill correctness only.** The backtest still makes no performance claim, because Nifty 500 membership and T2T/ASM status are still stubs (loop-3 Item 13). | 4.6 |
| **B10-1** | RS rating population | **REQUIRE OWNER CLARIFICATION.** Default: option C, every active equity with valid RS inputs (≥ 253 bars, last bar within 30 days). Fix the code, and amend spec §8 to say so. | 6.1 |
| **B10-2** | `rel_volume` denominator | **FIX CODE** to spec §8: `volume_today / avg_volume50`. | 6.2 |
| **B10-3** | EMA seed | **FIX CODE** to spec §8: SMA seed, the same as the browser. | 6.3 |
| **B10-4** | Rank tie-break | **FIX CODE** to `symbol` ascending, as spec §10, ADD §21 and the stored strategy config all say. | 6.4 |
| **B10-5** | Engine versioning for R3-B-10 | Approve the open audit question Q4 (`ENGINE_VERSION` in the manifest identity) and bump `INDICATOR_VERSION` 2 → 3. Ship B10-1 to B10-4 as one engine version. | 5.2 |
| **B10-6** | Validate B10-1 on the research harness first? | **Report only, not a promotion gate.** B10-1 corrects invalid inputs; it is not a ranking hypothesis. The research freeze stays in force. | 5.2 |
| **B10-7** | R3-B-29: spec §10 omits that gate engines are left out of both scores | **AMEND SPEC.** The code documents it, and it is rank-neutral among names that pass the gates. | 6.5 |

---

## 2. Root-cause report — R3-B-09

### 2.1 Reproduction

[`reproduce.py`](backend/decision-packet/reproduce.py) feeds the production `WalkForwardRunner`, `SqlPriceHistoryProvider`, `SqlSurvivorshipEligibilityProvider` and `SqlBenchmarkProvider` from the export. The window is 2025-01-01 to 2026-07-31 and capital is ₹10,00,000, the same as the audit.

| Check | Result |
|---|---|
| SHA-256 of the API response body | `8da9853e…ef5`: **byte-identical** to the audit's `walkforward/wf_1.json` and `wf_2.json` |
| Total return, final NAV | −9.016%, ₹9,09,839.29 |
| Trades, stale trades | 649 trades, **176 stale (27.1% of trades)** |
| Stale notional | ₹17,10,628.76 of ₹62,43,574.69 absolute notional = **27.40%** |

**How the 27% is calculated.** It is the sum of `|notional|` over stale fills divided by the sum of `|notional|` over all fills. Buys and sells both count. 99 of the 176 stale trades are buys, and they carry 83% of the stale notional. In the audit's `stale_fills.txt`, `649|176|1710628.76|6243574.69` holds these same four numbers.

The reference simulator, rebuilt from brief.md alone, reproduces the current engine. It selects the same targets at all 19 rebalances, makes the same 649 trades, and ends at the same final NAV to within 2×10⁻²⁴ (Decimal summation order). It is the independent reference for every policy below.

### 2.2 The mechanism, step by step

| Step | Code | What happens |
|---|---|---|
| Universe | [`walk_forward_market_data.py:275`](../../backend/src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py#L275) | It loads `exchange == 'NSE'` only. Dual-listed names carry `exchange = 'BOTH'` (since Phase 5, 2026-08-08), so all 2,431 of them are dropped: RELIANCE, TCS, INFY, HDFCBANK, MCX. It applies no equity filter, so 353 of the 1,018 names (35%) are ETFs or fund units. Example: EBBETF0425, a bond ETF that matured in April 2025, was held. Membership and surveillance are stubs. **The universe is mostly small names with long trading gaps.** New findings: R3-B-27 and R3-B-28. Brief §1 says "Nifty 500 constituents", so both contradict it. |
| Signal | [`walk_forward.py:230`](../../backend/src/momentum25/application/use_cases/walk_forward.py#L230) | `p_t = price_on_or_before(D)` returns the last bar, however old. **All 176 stale fills follow a signal scored on a stale `p_t`:** none of those names had a bar on D. The `_score` docstring says the opposite: "never scored on a fabricated or forward-filled price". |
| Price lookup | [`walk_forward_market_data.py:124`](../../backend/src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py#L124) | `bisect_right(dates, min(target, as_of)) - 1` returns the latest bar on or before the fill date. It never returns `None` for a name that traded earlier. |
| Execution | [`walk_forward.py:290`](../../backend/src/momentum25/application/use_cases/walk_forward.py#L290) | `_apply` fills at that bar's adjusted open. The "Skip rather than invent one" branch (line 297) cannot run for any name that traded before. **This is the stale fill.** |
| Valuation | [`walk_forward.py:270`](../../backend/src/momentum25/application/use_cases/walk_forward.py#L270) | `_mark_to_market` uses the same lookup. Its docstring says a name with no price "is marked to zero". In fact it is marked at the old bar's open. **This is the stale mark.** |
| Accounting | [`walk_forward.py:314`](../../backend/src/momentum25/application/use_cases/walk_forward.py#L314) | `_settle` rebuilds holdings as `target_value / price` for every target name and sets `cash = nav_pre − invested − total_cost`. It does not use the fills. It agrees with the trade log only because every fill succeeds. **If fills could be skipped, holdings, cash and costs would leave the trade log.** This is a latent defect that any policy fix must remove. |
| Final NAV | [`walk_forward.py:397`](../../backend/src/momentum25/application/use_cases/walk_forward.py#L397) | The final mark uses the last close on or before the end date: a stale terminal mark. |
| Tests | `tests/unit/test_walk_forward.py:63` | `FakePrices` has the same on-or-before rule, and no test covers a missing fill-date bar. So the defect cannot fail a test. |

**How staleness is distributed.** Median 42 sessions, p90 103, maximum 258. Only 13 of 176 stale fills are within 5 sessions.

### 2.3 Worked examples ([`trace.py`](backend/decision-packet/trace.py))

| Name | What the current engine did | What the market offered |
|---|---|---|
| 3PLAND | Bought 2025-01-01 at 81.50 (bar of 2024-12-18). Trimmed on 2025-02-01 and 2025-03-03, again at 81.50. Sold 2025-04-01 at 38.86. | No trading from 2024-12-18 to 2025-03-25. Reopened at 40.00 against a last close of 74.40. |
| ABMINTLLTD | Bought 2025-02-01 at 105.36 (bar of 2024-10-30). Sold 2025-03-03 at 46.09. | No trading from 2024-10-30 to 2025-02-10. Reopened at 64.05. |
| LEXUS | Bought 2026-04-01 and 2026-05-04 at 38.00 (bar of 2026-02-23). Sold 2026-06-01 at 18.00. | No trading from 2026-02-23 to 2026-05-19. Reopened at 18.99. |

The pattern repeats. A name stops trading for about three months and reopens 40–50% lower. The engine buys it at the pre-gap price while no market exists, holds it through the gap at that price, then books the fall. **The bias does not have one fixed direction** (§4.3).

### 2.4 Execution prices versus valuation marks

A stale fill is a transaction the market did not offer, so it is never valid. A stale mark is a valuation convention: the last traded price is the usual mark for a suspended holding. It is valid only when it is disclosed, because it can hide a later gap. The fix removes stale fills completely. It keeps stale marks, but flags them and bounds them (B09-3).

---

## 3. Policy comparison

### 3.1 Policies tested

All non-current policies share these rules. Holdings are marked at the fill-date open, or else at the last close on or before D. Buys are cash amounts and sells are share counts. Sells run before buys. Fills, and only fills, move holdings and cash. Costs are 30 bps on filled notional (brief §7). There is no leverage.

| Policy | Buys | Sells | Assumption | Benefit | Limitation | Complexity |
|---|---|---|---|---|---|---|
| **Current** | Last bar on or before F | Same | Any earlier price is a valid fill | — | Fills prices the market did not offer | — |
| **A** strict same session | Bar on F only, else cancel and keep the cash | Bar on F only, else keep the position for a month | No trading means no fill | Simplest; causal | Holds a rejected name for a month even if it reopens on F+1 | Low: monthly loop only |
| **C5** cancel after a window | Up to 5 sessions, then cancel | Same | A short window is realistic | — | The 5-session window is an arbitrary parameter. Results ≈ A. | Medium |
| **B** next eligible session | First later session with a bar, until the next rebalance | Same | Late fills are acceptable | Fewest stranded orders | Buys a reopened name weeks later on an old signal, often into the reopening gap | Medium: intra-month loop |
| **D (EXEC-1)** hybrid | Bar on F only, else cancel | Bar on F, else the first later session with a bar; the next rebalance replaces it | Exits are forced; entries are optional | No stale fill. No buying on an old signal. Exits at the first real price. | Names that never trade again stay held (B09-3) | Medium: intra-month loop for sells only |

### 3.2 Recommendation: EXEC-1

Every rule is deterministic, and every rule uses only facts known at or before the trading session.

1. **E1 Signal availability.** Score a name at D only if it has a bar on D. Lookback prices (3, 6 and 12 months) keep the documented rule: the latest session on or before the target date ([`walk_forward.py`](../../backend/src/momentum25/application/use_cases/walk_forward.py) `_months_before` docstring). The result counts lookbacks more than 5 sessions stale (§4.5).
2. **E2 Execution price.** Use only the adjusted open of a bar dated on the execution session.
3. **E3 Sizing.** Target value = NAV before trading / number of target names. A held name is marked at its adjusted open on F, or else at its last close on or before D (flagged).
4. **E4 Order.** Sells, then buys, in the same session.
5. **E5 Buys.** Execute on F only. With no bar on F, cancel the buy. Its cash stays cash until the next rebalance and is not given to other names.
6. **E6 Sells.** Execute on F. With no bar on F, retry at the adjusted open of each later session with a bar. At the next rebalance, the new plan replaces the pending sell.
7. **E7 Cash.** No leverage. If buy cash plus cost exceeds available cash, scale every buy by one factor.
8. **E8 Costs.** 30 bps on filled notional only.
9. **E9 Accounting.** Holdings and cash change only through fills. Trade-log replay equals the running NAV at every rebalance and at the end.
10. **E10 Valuation.** Daily, rebalance and terminal marks use the last adjusted close on or before the date. The result reports the NAV share in names with no bar for more than 20 sessions, and the NAV with those names at zero.
11. **E11 Delistings.** No synthetic liquidation. `securities.delisting_date` is inferred from the last bar seen (`rp012_populate_survivorship_dates.py`), not from exchange records. Selling at the last close would be a stale fill, and writing the name off would assume an outcome the data does not hold.
12. **E12 Liquidity.** No capacity model. The result reports participation (|notional| / the session's `turnover_value`) and flags fills above 10%.

**Why D and not A.** A and D give nearly the same numbers here (+25.5% against +25.1%). D sells a rejected name at its first real price, not a month later, and it costs one extra loop over pending sells. If you prefer the smallest change, A is an acceptable fallback: same buys, and sells wait for the next rebalance. B and C5 are rejected because they buy on a signal that is weeks old, and C5's window has no basis in the brief.

**Owner-configurable values.** Keep them as constants of the versioned policy (`BACKTEST_METHOD_VERSION = 2`), not as request parameters. Two results with the same method version are then always comparable. The candidates are: buy window 1 session; sell retry until filled; decision-date bar required; non-trading flag after 20 sessions; participation flag at 10%. A change to any of them is a new method version.

### 3.3 Historical realism

- NSE suspensions and trade-for-trade moves explain the multi-month gaps. Nobody could trade these names during a gap, so no policy may fill there.
- A reopening open is a real price. Its depth is unknown: under every policy, 2–3 fills in the NSE-only universe exceed the whole session's traded value (§4.5).
- With no T2T/ASM history, the backtest cannot exclude restricted names before they stop trading, as brief §1 requires. E1 removes names that are already stale at D. It cannot remove a name that stops trading the day after.

### 3.4 Cash and positions under EXEC-1

- Mean cash at rebalance is 17.2%, and the maximum is 46.6% (2025, NSE-only, current signal). Under E1 the mean drops to 0.0%, because names with a bar on D almost always have a bar on F.
- Under E1, names that stop trading after purchase stay held and accumulate: 36.4 holdings on average against a target of 30, and 15.1% of NAV on stale marks. This is why B09-3 needs a disclosed lower bound.

---

## 4. Financial impact analysis

Window 2025-01-01 → 2026-07-31, 19 rebalances, ₹10,00,000. Benchmark: Nifty 500 Price Index (not TRI), +2.80% over the same span, the same under every policy. Source: [`headline.json`](backend/decision-packet/headline.json), [`out-NSE.txt`](backend/decision-packet/out-NSE.txt).

### 4.1 Production configuration (NSE-only universe, current signal rule)

| Metric | Current | A | C5 | B | D (EXEC-1) |
|---|---|---|---|---|---|
| Orders / with no bar on F | 649 / 176 (27.1%) | 653 / 196 | 654 / 196 | 683 / 202 | 652 / 196 |
| Fills | 649 | 457 | 466 | 524 | 461 |
| Stale-filled notional | **27.40%** | 0 | 0 | 0 | 0 |
| Filled notional (₹) | 62,43,575 | 47,18,051 | 48,14,520 | 59,54,447 | 47,20,844 |
| Cancelled or expired orders | 0 | 196 | 188 | 146 | 142 |
| Deferred fills (max sessions late) | 0 | 0 | 8 (4) | 43 (19) | 5 (19) |
| Costs (₹) | 18,731 | 14,154 | 14,444 | 17,863 | 14,163 |
| One-way turnover per year | 2.26× | 1.39× | 1.41× | 1.76× | 1.39× |
| **Total return** | **−9.0%** | +25.5% | +25.5% | +23.3% | +25.1% |
| CAGR | −5.8% | +15.5% | +15.5% | +14.2% | +15.3% |
| Max drawdown (daily) | −23.9% | −13.8% | −14.4% | −14.3% | −13.8% |
| Lower bound (non-trading names at zero) | −38.2% | +6.2% | +6.2% | +2.3% | +5.8% |
| Mean / max cash at rebalance | −0.1% / −0.0% | 17.2% / 46.6% | 17.0% / 46.6% | 14.7% / 46.6% | 17.2% / 46.6% |
| Mean holdings | 30.0 | 25.9 | 25.9 | 27.1 | 25.9 |
| Max single weight | 3.7% | 4.4% | 4.4% | 4.4% | 4.4% |
| Mean / max NAV on stale marks | 28.4% / 53.4% | 14.4% / 29.1% | 14.5% / 29.1% | 17.3% / 30.7% | 14.4% / 29.2% |
| Mean target overlap with current (Jaccard) | 1.00 | 0.89 | 0.89 | 0.92 | 0.89 |

The current engine's cash is slightly negative because `_settle` pays costs out of cash after investing 100% of NAV. That is a small implicit leverage.

### 4.2 Recommended configuration (EXEC-1 with E1)

| Metric | Current + E1 | **EXEC-1 + E1** |
|---|---|---|
| Orders with no bar on F | 4.1% | 16.0% (mostly the same stuck sells, re-issued each month) |
| Stale-filled notional | 12.0% | **0** |
| Total return / CAGR | +27.7% / +16.8% | **+23.8% / +14.5%** |
| Max drawdown | −18.6% | −18.3% |
| Lower bound (non-trading names at zero) | +19.9% | **+3.4%** |
| Costs / turnover | ₹24,885 / 2.46× | ₹17,526 / 1.76× |
| Mean holdings / NAV on stale marks | 30.0 / 3.3% | 36.4 / 15.1% |

### 4.3 Attribution and direction of bias ([`attrib.py`](backend/decision-packet/attrib.py))

- The gap between the current engine and A is −34.5 points of return (₹−3,45,296). Of that, ₹−2,94,776 (85%) sits in the 51 names with at least one stale fill. The rest comes from different holdings later in the path (the buffer rule depends on holdings).
- The current engine lost ₹1,91,836 on those 51 names and made ₹1,01,675 on all other names.
- **The sign of the bias depends on the mix.** A stale buy enters before a fall, so it hurts. A stale sell exits before a fall, so it flatters. In the wider universe with E1, the current engine shows −3.6% and EXEC-1 shows −9.7%. So the audit register's phrase "biased toward illiquid names" is right about exposure, but no fixed direction may be claimed for returns.

### 4.4 Sensitivity: universe and signal ([`out-BOTH.txt`](backend/decision-packet/out-BOTH.txt), [`out-BOTH-fresh.txt`](backend/decision-packet/out-BOTH-fresh.txt))

With dual-listed names included, 1,477 to 1,929 names are scored per rebalance (NSE-only: 142 to 211). ETFs are still in the universe in this sensitivity run:

| Universe / signal | Current | EXEC-1 | EXEC-1 lower bound |
|---|---|---|---|
| NSE only, current signal | −9.0% | +25.1% | +5.8% |
| NSE only, E1 | +27.7% | +23.8% | +3.4% |
| NSE + BOTH, current signal | −19.9% | +0.6% | −25.9% |
| NSE + BOTH, E1 | −3.6% | −9.7% | −34.2% |

**Across these four configurations, total return runs from −42% to +28%** once valuation is included. The fill policy matters, but universe construction and the valuation of names that stop trading matter as much. This backtest cannot support a performance claim until R3-B-27, R3-B-28 and loop-3 Item 13 are resolved (B09-8).

### 4.5 Liquidity and lookback staleness ([`liquidity.json`](backend/decision-packet/liquidity.json))

| Configuration | Fills | Median participation | p99 | Fills > 10% of session value | Fills > 100% |
|---|---|---|---|---|---|
| NSE, current | 649 | 0.01% | 63.9% | 23 | 5 |
| NSE, EXEC-1 + E1 | 655 | 0.01% | 19.9% | 13 | 3 |
| NSE + BOTH, EXEC-1 + E1 | 738 | 0.004% | 8.7% | 6 | 0 |

Lookbacks: under E1, 1,233 of 10,281 lookback prices (12.0%) in the NSE-only universe come from a bar more than 5 sessions before the target date, and 982 from more than 20 sessions. In NSE + BOTH the figures are 7.3% and 5.8%. **Limitation:** the data has no order-book depth, so no policy can show a fill was executable at size. The packet reports this instead of modelling it.

### 4.6 Consequences beyond the backtest

- **Strategy selection and ranking.** The backtest does not use the screener, its engines, Strategy Studio or the hold-out ([ADR-014](../../docs/architecture/adr/ADR-014-strategy-studio.md), context item 1 and the rejected alternative "Reuse the walk-forward backtest"). The policy changes only the backtest's own holdings path (Jaccard 0.89–0.92 against the current engine).
- **Research walk-forward and out-of-sample results.** These are unaffected. `validation.py` and the forward-return backfill never call `WalkForwardRunner` or `price_on_or_before` (verified by search). Forward returns count the security's own bars ([`forward_returns.py`](../../backend/src/momentum25/domain/research/forward_returns.py)).
- **Stored results.** No backtest result is persisted: there is no table, and `/backtest/walk-forward` computes on demand. The only stored outputs are the audit files `walkforward/wf_1.json` and `wf_2.json`. No current document quotes a backtest return.

---

## 5. Methodology and compatibility plan

### 5.1 Backtest (R3-B-09, R3-B-27, R3-B-28)

| Surface | Change |
|---|---|
| Domain | `BACKTEST_METHOD_VERSION = 2` and an `ExecutionPolicy` constant (E1–E12 values) in `domain/backtest/`. Version 1 means the code before the fix. |
| Result and API | `WalkForwardResult` and `BacktestResponse` gain additive fields: `method_version`, `execution_policy`, `data_version` with the manifest body (revision, calendar version), `build_id`, and the universe provider label. They also gain counts: orders, fills, cancelled buys, deferred sells, unfilled notional, non-trading NAV share, zero-mark lower bound, fills above 10% participation, stale lookbacks. Regenerate `web/src/lib/api-schema.ts`. Existing fields keep their meaning. |
| Web `/backtest` | Show the method version, the policy line, and the lower bound next to the total return. The survivorship warning stays first. |
| CLI | `format_walk_forward_report` prints the same lines. |
| Old results | Leave the audit files `wf_1.json` and `wf_2.json` untouched. Mark them "method v1 (stale fills)" in the evidence index. Reproduce v1 from commit `2506150` with data revision 133621 and `reproduce.py`; the expected SHA-256 is `8da9853e…ef5`. No v1 mode stays in code: there are no persisted v1 results to serve, and dead code would violate CLAUDE.md. |
| Research manifests | Not affected. The backtest writes no manifest today. Version 2 records one in its response, not in `data_manifests`. |

### 5.2 Screening engine (R3-B-10)

| Surface | Change |
|---|---|
| Version carriers | Items 2 and 3 move existing indicator values, so bump `INDICATOR_VERSION` 2 → 3 (the rule at [`indicator_pipeline.py:67`](../../backend/src/momentum25/infrastructure/pipelines/indicator_pipeline.py#L67): "Bump only when an existing value moves"). Items 1 and 4 live outside both `INDICATOR_VERSION` and `registry_version()`, so `data_version` cannot see them today. Precedent: `18cab43` (2026-10-19) changed every RS rating without a version bump. Approve Q4: add `ENGINE_VERSION` to the manifest identity as identity schema 3. Schema 1 and 2 bodies keep their hash rules, so every stored key still loads. |
| Stored runs | Immutable under ADR-006. The next screen writes a new run with a new `data_version`. Run 149 and every earlier run keep their results, rules, explanations and hashes. |
| `config_hash` | Unchanged. The stored config already says `tie_breakers: [..., "symbol"]`. After B10-4 the code honours text that the hash already covers. |
| Score and rank history | The UI and the APIs that show a stock's score or rank history across runs must mark the engine-version break. The minimum is a field on each point; the chart shows a divider. |
| Research | The RP-000 to RP-007 reports and the dataset v1.0 baseline stay as written. Add one line to the research index: results measured before engine version 2 used the old RS population and raw closes (pre-`18cab43`). |
| Studio hold-outs | The development database has 0 `strategy_evaluations` rows. Anywhere they exist, a sealed hold-out stays sealed and keeps its `data_version`. It is never re-run because the engine changed. |

---

## 6. R3-B-10 decision table

Source: [`r3b10.py`](backend/decision-packet/r3b10.py) for run 149, and [`r3b10_multi.py`](backend/decision-packet/r3b10_multi.py) and [`r3b10_optc.py`](backend/decision-packet/r3b10_optc.py) for 7 more runs (2020-11-27 to 2025-09-30). The rebuild reproduces run 149 first: RS 0 mismatches over 3,073 equities, gates 1,338 of 1,338, ranks 155 of 155, maximum score difference 0.0018 (stored contributions are rounded to 4 dp).

### 6.1 Item 1 — RS rating population

| Field | Finding |
|---|---|
| Specification | Spec §8: "percentile rank (1–99) of RS raw return across the **eligible universe** in the same run". ADD §17 (higher precedence): "computed across **the universe** within a run". ADD §25: "Compute RS after **universe load**". ADD §17 also says: "**Insufficient history ⇒ indicator `None`** and the security is flagged ineligible." |
| Implementation | [`screening_orchestrator.py:121`](../../backend/src/momentum25/application/use_cases/screening_orchestrator.py#L121) loads every active equity; [`:318`](../../backend/src/momentum25/application/use_cases/screening_orchestrator.py#L318) ranks RS over it before eligibility. [`rs_ratings.py:111`](../../backend/src/momentum25/application/services/rs_ratings.py#L111) shortens each window to `min(period, len(bars) − 1)` and takes the last bar however old. The historical and read paths use the same service. |
| Classification | **Ambiguity** (ADD and spec differ) **with an embedded defect**. Run 149 ranks 669 names with fewer than 253 bars on shortened windows, against ADD §17 and the formula `R(d) = close/close[−d] − 1`. It also ranks 468 names whose last bar is more than 30 days old. |
| Options | **A** current: all active equities (3,073 on run 149). **B** spec: eligible names only (1,338). **C** all active equities with valid inputs: ≥ 253 bars and not stale under the screener's own rule `is_stale_as_of` (more than 30 days, [`data_quality.py:33`](../../backend/src/momentum25/domain/research/data_quality.py#L33)) (1,959). C adds no new threshold. |
| Financial impact | A → B over 8 runs: 1,005–1,678 ratings change per run. Per run, 0–157 names cross RS 70 upward and 0–3 downward. Qualified set grows by up to +60 (run 88: 200 → 260). **Top-25 overlap 19–25 of 25**, with 0–6 names swapped per run; run 149 swaps 0. **B against C:** qualified-set Jaccard 0.98–1.00, mean rating difference 0.04–0.23 points in 7 of 8 runs (4.8 on run 149). The code-versus-spec gap is almost entirely the invalid inputs, not the liquidity and price floors. |
| User and workflow impact | Option B ties every RS rating to each strategy's eligibility settings (`min_price_inr`, `min_avg_turnover_inr`). A Studio strategy that raises its turnover floor would change every name's RS rating, and the gate `tt_rs_rating_min` would mean different things in different strategies. Option C keeps RS one shared measure. |
| Compatibility | Engine version change (§5.2). The read path (`resolve_universe_rs_ratings`, `/live`, the watchlist) must change in the same commit, or R3-B-08 returns. Bump the RS cache key to v3. |
| Verification | Golden test: a fixture universe holding one short-history name, one stale name and one ETF; assert each is excluded from the population and has rating `None`. Parity: the live, historical and read paths give identical ratings for all scored names. Rerun the look-ahead test. |
| **Decision** | **REQUIRE OWNER CLARIFICATION.** Default: **option C** (FIX CODE for the invalid inputs, under ADD §17), then AMEND SPEC §8 to "every active equity with a valid RS raw return (≥ 253 bars, last bar within 30 days of the run date)". This does not legitimise current behaviour: it removes 1,137 invalid inputs from run 149's population. |

### 6.2 Item 2 — `rel_volume`

| Field | Finding |
|---|---|
| Specification | Spec §8: "`avg_volume50 = mean(volume[-50:])`. `rel_volume = volume_today / avg_volume50`." The denominator includes today. |
| Implementation | [`indicator_pipeline.py:852`](../../backend/src/momentum25/infrastructure/pipelines/indicator_pipeline.py#L852) computes `volume[-1] / mean(volume[-50:-1])`, a mean of **49** prior sessions. Its docstring says "over `window` (excluding latest)", which would be 50 prior sessions. All 1,337 stored values equal the 49-session form. |
| Classification | **Defect.** It matches neither the spec nor its own docstring (off by one). |
| Financial impact | Run 149: `vol_breakout_confirm` (threshold 1.4, weight 1.0) changes pass/fail for 1 name under the spec form and for 6 under the 50-prior form. Rank order changes at 7 (spec) or 26 (50-prior) of 155 positions. Top-25 is unchanged under both. The largest single change is 72.5% of the value (spec form), on a high-volume day. |
| User impact | `rel_volume` shows on the stock pages and the screener and drives one scored rule. The values change slightly. |
| Compatibility | `INDICATOR_VERSION` 3. |
| Verification | Golden test with 50 known volumes: assert `rel_volume == v[-1] / mean(v[-50:])` exactly. Assert `rel_volume` and `avg_volume50` share one window. |
| **Decision** | **FIX CODE** to the spec. The spec text is explicit and reuses the stored `avg_volume50`. The "50 prior sessions" form would be a new convention with no source document. |

### 6.3 Item 3 — EMA seed

| Field | Finding |
|---|---|
| Specification | Spec §8: "EMA(n): … **seed = SMA(n) of first n bars**." |
| Implementation | [`indicator_pipeline.py:112`](../../backend/src/momentum25/infrastructure/pipelines/indicator_pipeline.py#L112) calls `ewm(span, adjust=False)`, seeded with the first close. The docstring states the deviation openly. The browser seeds with SMA ([`overlays.ts:66`](../../web/src/lib/indicators/overlays.ts#L66), golden-tested). MACD is built from the same `_ema`. |
| Classification | **Intentional deviation**, with no approval recorded in any spec or ADR. |
| Financial impact | **No screening effect.** No rule reads `ema10`, `ema21` or MACD (verified by search). At the last bar of the 277-bar window, values differ at 4 dp for 4 names (`ema21`) and 7 names (MACD) out of 1,337, all with short histories. |
| User impact | The backend MACD series feeds the chart's MACD pane (`PriceChart.tsx:408`), the Technical Workbench and server-side MACD alerts. 56% of its rows differ from the SMA-seeded series at 4 dp, by up to 5.7% of price near the start of the window. The browser's catalogue MACD uses an SMA seed, so two MACDs on one screen can disagree. |
| Compatibility | `INDICATOR_VERSION` 3. Alert definitions are unchanged; alert values on early bars move. |
| Verification | Golden test on 300 bars against the browser `golden-fixture.json` series: EMA10, EMA21, MACD line, signal and histogram equal to 1e-9, warm-up gaps included. |
| **Decision** | **FIX CODE** to the spec. The spec is explicit, the browser already complies, and no screening result moves. |

### 6.4 Item 4 — rank tie-break

| Field | Finding |
|---|---|
| Specification | Spec §10: `(momentum_score desc, buy_setup_score desc, rs_rating desc, symbol asc)`. ADD §21: "→ `symbol`". Run 149's stored strategy config: `ranking.tie_breakers: ["buy_setup_score", "rs_rating", "symbol"]`, which is inside `config_hash`. |
| Implementation | [`ranking_engine.py:41`](../../backend/src/momentum25/domain/scoring/ranking_engine.py#L41) sorts by `s.security_id  # deterministic proxy for symbol ascending`. No code reads `ranking.tie_breakers`. |
| Classification | **Defect.** The "proxy" is false for 97 adjacent id pairs among 3,463 securities. |
| Financial impact | **Zero on production.** Across 136 completed `minervini_trend_template` runs (31,239 qualified rows), no tie exists where id order and symbol order differ. The 9 cases sit in two `benchmark_c_trend_template_only` research runs, at ranks 102–233, never at the Top-25 boundary. |
| Compatibility | Engine version (§5.2). The ranking needs the symbol as of the run (carry it on `StockScore`), so that a later rename does not reorder a replay. |
| Verification | Unit test: three names with equal scores and RS whose id order differs from symbol order; assert symbol order. Replay run 149 and assert identical ranks. |
| **Decision** | **FIX CODE.** Three sources agree on `symbol`. Amending the spec would legitimise a stated proxy that is false. |

### 6.5 Related findings found during this review (not in the original four)

| ID | Finding | Recommendation |
|---|---|---|
| R3-B-27 (P1) | The backtest universe excludes all 2,431 `exchange = 'BOTH'` names ([`walk_forward_market_data.py:275`](../../backend/src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py#L275)). | FIX CODE with B09-1 (B09-6). |
| R3-B-28 (P1) | The backtest universe includes 353 ETFs and fund units; EBBETF0425 was held. | FIX CODE with B09-1: use `is_equity`, as the screener does. |
| R3-B-29 (P3) | The scoring engine leaves gate engines out of both weighted scores ([`scoring_engine.py:119`](../../backend/src/momentum25/domain/scoring/scoring_engine.py#L119)). Spec §10 sums every engine. The code docstring proves it is rank-neutral among names that pass. | AMEND SPEC (B10-7). It is documented in code, it is reproduced exactly by this packet's rebuild, and no rank changes. |
| Note | `_MIN_LISTING_DAYS = 252` "trading days" is compared with calendar days ([`eligibility.py:17`](../../backend/src/momentum25/domain/backtest/eligibility.py#L17)). This has no effect today, because the 12-month lookback price enforces 12 months of history. | Fix the comment when the backtest is touched. |
| Note | The backtest reports no CAGR or drawdown, although loop-2 addendum §3 asks for CAGR. | Add both with B09-7. |

---

## 7. Dependency and regression analysis

| Component | R3-B-09 fix | R3-B-10 fixes | Revalidate |
|---|---|---|---|
| Live Momentum25 screening | **Unaffected.** It shares no code with the backtest (search for `WalkForwardRunner` and `price_on_or_before`). | **Affected** by items 1, 2 and 4. Item 3 changes no score. | Determinism (5 runs, identical hashes), golden scoring, gate boundaries, run 149 replay under the old engine |
| Strategy config and execution | Unaffected | `tie_breakers` becomes honoured; RS population changes for every strategy | `strategy-integration.spec.ts` |
| Historical point-in-time screening | Unaffected | Affected through the shared `rs_ratings` and ranking | Look-ahead mutation test, historical run as of 2026-08-07 |
| Strategy Studio and experiments | Unaffected (separate method, ADR-014) | Affected; new `data_version` | Studio journeys; hold-out labelling |
| Backtest and portfolio accounting | **Affected:** signal, fills, accounting, universe, response | Unaffected (own signal) | All of §8.1 |
| In-sample / hold-out separation | Unaffected | Window boundaries unchanged; ranking inputs change | Boundary tests (hold-out 2023-01-02 → 2025-12-31) |
| Chart and research provenance | Unaffected | EMA and MACD series change on early bars; `/live` and the watchlist follow the item 1 change | `golden.test.ts`, candle-anatomy, alerts, R3-B-08 parity |
| Research walk-forward, IC, forward returns | Unaffected | Not comparable across the engine version; prior reports stand as written | Research index note |
| APIs | `/backtest` response gains fields; regenerate TS types | No schema change; values change | OpenAPI drift check |
| Persisted documents and results | Nothing persisted | Runs immutable; new snapshots only | Run 149 hash unchanged after the deploy |

**Unaffected, with evidence:** adjustment factors, aggregation, browser indicators, determinism mechanics, run identity, eligibility gates, explanation text, the hold-out windows and drawings.

---

## 8. Implementation acceptance criteria

### 8.1 R3-B-09 (after B09-1 to B09-7 are approved)

1. **No stale fill.** On the real-data replay (2025-01-01 → 2026-07-31), every trade's price comes from a bar dated on its fill date. Count = 0.
2. **Signal freshness.** No name without a bar on D is scored. Unit test: a name whose last bar is D−1 is absent from the signals.
3. **Missing fill bar (unit tests with a fake that returns `None` when no bar exists on the exact date):** a buy is cancelled and its cash stays cash; a sell retries and fills at the next session's open; the next rebalance replaces a pending sell.
4. **Accounting identity.** At every rebalance and at the end, trade-log replay NAV equals the running NAV exactly (Decimal). Holdings equal the sum of filled quantities, and costs equal 30 bps of filled notional.
5. **No leverage.** Cash is never below zero after a rebalance. A test with stuck sells checks the pro-rata buy scale.
6. **Universe.** Dual-listed names are included and ETFs and fund units excluded. RELIANCE is present; EBBETF0425 is absent.
7. **Independent reference.** On the same data, the production engine equals `sim.py` policy D with E1 and the fixed universe: same targets, same fills, final NAV equal to 1e-20. Commit the reference as a test fixture, not as production code.
8. **Determinism.** Two runs give byte-identical responses.
9. **Look-ahead.** The leaky-provider test still raises `LookAheadError`. A price dated after F at a deferred sell must also raise it.
10. **Disclosure.** The response and the `/backtest` page show the method version, policy, non-trading weight, zero-mark lower bound and participation flags. An E2E check asserts the lower bound sits next to the total return.
11. **Re-baseline.** Record the new real-data result as method v2 in the audit evidence. v1 files stay untouched.

### 8.2 R3-B-10 (after B10-1 to B10-7 are approved)

1. Item 1: the golden population test in §6.1; live, historical and read-path parity for every scored name; a new run on 2026-10-19 data gives 1,959 rated names (option C) and run 149 is unchanged.
2. Item 2: the golden volume test in §6.2; the stored `rel_volume` of the new run equals `volume / avg_volume50` to 4 dp.
3. Item 3: browser and backend parity to 1e-9 on `golden-fixture.json` for EMA10, EMA21 and MACD; the warm-up gaps match.
4. Item 4: the tie test in §6.4; ranks on run 149 replay unchanged.
5. Versioning: `INDICATOR_VERSION == 3`; `ENGINE_VERSION` present in identity schema 3; run 149's key `8790a000bd4f` still reproduces; same data under the new engine gives a new key.
6. Full backend and browser suites green; `lint-imports` clean; OpenAPI types regenerated.

---

## 9. Limits of this packet

- One backtest window (19 months), set by the audit. Longer windows were not run.
- One data source. The recomputation proves what the code does with this data. It does not prove the exchange data is right.
- No order-book depth and no point-in-time Nifty 500 or T2T/ASM data. Fill size and the brief's exclusions cannot be checked.
- `delisting_date` is inferred from bar coverage, so a long suspension and a delisting look the same.
- R3-B-10 impact uses stored contributions for every rule except RS and `vol_breakout_confirm`. It covers the qualified set and ranks, not the full explanations.
- Stored RS for runs before `18cab43` used raw closes, so only 22 to 402 of each run's 1,113 to 1,782 stored ratings reproduce. The 7-run comparison therefore compares two recomputed variants on today's data, not stored ratings.
