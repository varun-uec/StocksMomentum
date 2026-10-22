# Stage A — Financial Methodology Specification (Proposed)

Date: 2026-10-20. Branch `wickstreet/m10-m11` at `2506150`. Status: **PROPOSED. Not approved. Not implemented.**

This document answers the owner direction "Financial Correctness Remediation — Consolidated Owner Direction" (2026-10-20). It builds on the [decision packet](R3-B-09_R3-B-10_DECISION_PACKET.md) and supersedes the packet's defaults where §1 says so. It changes no code, specification, ADR, strategy or stored result. Every number comes from scripts in [`backend/decision-packet/`](../../../audit-evidence/audit-r3/backend/decision-packet/) and [`backend/decision-packet/stage-a/`](../../../audit-evidence/audit-r3/backend/decision-packet/stage-a/). Those scripts read a read-only export ([`export.sh`](../../../audit-evidence/audit-r3/backend/decision-packet/export.sh)) and run in memory.

Precedence (CLAUDE.md): ADD, then ADRs, then the Implementation Spec, then CLAUDE.md, then the task prompt. The owner direction is a task prompt. Where it conflicts with a higher source, this document says so and does not resolve the conflict silently (§1, B10-4 and S-8).

Terms: **fill date (F)**, **decision date (D)**, **stale fill** and **stale mark** keep their packet meanings. A **valid execution bar** is a bar dated on the execution session with `open > 0`, `volume > 0` and `low ≤ open ≤ high`. A **non-trading holding** is a held security with no bar for more than 20 sessions.

---

## 0. What the Stage A investigation added

The packet's conclusions stand. Four new facts change what the method must cover:

| ID | Finding | Evidence | Effect |
|---|---|---|---|
| **R3-B-30** (P1) | The backtest price provider drops every bar with `adj_close` NULL. That is 553,534 bars (17%), and 42% of all 2026 bars. **Every one has `adj_factor = 1`**, so `close × adj_factor` prices it exactly. The indicator pipeline already uses `close × adj_factor`. | read-only SELECT; `stage-a/stageA.py` | Names that traded look absent. With the corrected universe over 2021–2026, the 5.5-year result moves from +334% to +281% (§5). |
| **R3-B-31** (P1) | **Renames are split across unlinked security rows.** TWL ends 2023-06-16 and TITAGARH starts 2023-06-19. MAGMA ends 2021-06-08 and POONAWALLA starts 2021-09-13, with the same listing date. MEGASOFT and SIGMAADV share one ISIN. Old rows have no ISIN. A heuristic (an old row without ISIN, delisted, sharing a listing date with a live row) finds up to 334 candidate pairs. **Not verified.** | `stuckA.py`; read-only SELECT | The backtest freezes a renamed holding at its last pre-rename price for years. MAGMA was held frozen for 1,269 sessions. The screener and RS treat the successor as a new listing until it has 253 bars. |
| **R3-B-32** (P2, research) | Stored forward returns count the security's own next *h* bars ([`forward_returns.py`](../../../backend/src/momentum25/domain/research/forward_returns.py)). For a name with trading gaps, "120 sessions" covers more calendar time. | `rs_align.py` | In-Sample Top-25 names with gaps: 65.7% stored against 50.3% measured on exchange sessions (120 sessions). Research IC and Top-25 returns on gap names are inflated. |
| Lead | The ingest keeps EQ-series rows only ([`bhavcopy.py:238`](../../../backend/src/momentum25/infrastructure/providers/bhavcopy.py#L238)). The repeated 2–4-month gaps are consistent with trade-for-trade (BE) periods, which the EQ ingest never records. In the In-Sample runs, 12.9 of 25 Top-25 names on average have under 95% bar completeness. **Not verified:** that needs one NSE bhavcopy fetch, which leaves this machine (S-10). | `gaps_top25.py`, `rs_ref.py` | If true, a "missing bar" usually means "trading under surveillance", not "suspended". Brief §1 excludes T2T names, so treating those sessions as untradable fits the brief. |

---

## 1. The 15-question matrix, mapped to the owner direction

"Resolves" means the direction fixes the rule. "Partial" means a parameter or a sub-choice is still open.

| # | Packet default | Owner direction | Resolution | Precise rule proposed | Open choice |
|---|---|---|---|---|---|
| **B09-1** Fill policy | Buys at F or cancel; sells at F or the next session with a bar | §1.4 "prefer next-eligible-session execution"; buy expiry to be decided | **Partial. Default changed.** Evidence: once a decision-date bar is required (E1), a buy window of 1, 2 or 5 sessions gives identical results. "Until the next decision" adds 4 late buys in 5.5 years. | **X1:** each order executes at the adjusted open of the first valid execution bar on or after F. A buy expires after `BUY_WINDOW_SESSIONS` sessions, counting F. A sell stays live until filled or until the next plan replaces it. | **S-1:** `BUY_WINDOW_SESSIONS`, default 5 (immaterial in the data). |
| **B09-2** Decision-date bar | Require it | §1.2 requires it | **Resolves.** | **E1:** score a name at D only if it has a valid bar dated D. | — |
| **B09-3** Non-trading holdings | Last close, flagged; report a zero-mark bound | §1.7: explicit handling; "prevent fictitious positions" | **Partial.** 35% of end NAV (2021–2026) sits in non-trading holdings, and many are renames (R3-B-31). | **V1:** mark at the last adjusted close; flag after 20 sessions; report NAV and a zero-mark lower bound. Never liquidate synthetically: a sale at a stale price breaks direction §1.3. When identity chains exist, a rename moves the position to its successor 1:1 on the effective date. | **S-5:** fix identity chains first. **S-6:** write-down rule for a confirmed delisting with no successor. |
| **B09-4** Cash | No leverage; cancelled-buy cash stays cash; pro-rata scale | §1.9 no negative cash or leverage; settlement to be decided | **Partial.** | **C1:** no negative cash; a buy never exceeds available cash after costs. Cash from a cancelled or expired buy stays cash until the next plan. | **S-2:** sale proceeds usable in the same session (brief §5) or at T+1. |
| **B09-5** Liquidity | No cap; flag fills above 10% | §1 "partial fills, available liquidity"; §6 realism | **Partial. Default changed.** | **L1:** a fill is capped at `PARTICIPATION_CAP × session turnover_value`. The remainder waits under X1. Every fill records its participation. | **S-3:** the cap, default 10%. |
| **B09-6** Universe defects | Fix with the method version | §2 resolves: include BOTH, exclude funds, point in time | **Resolves**, and widens to R3-B-30 and R3-B-31. | §3.1 below. | **S-5** (identity chains). |
| **B09-7** Versioning | `BACKTEST_METHOD_VERSION` + manifest; no legacy mode | §7 distinct identities; §8 never relabel | **Resolves, extended.** | §4 below. | **S-8** (amend ADR-014 §10). |
| **B09-8** G3 scope | Fill correctness only; no performance claim | §6 three properties; §10 no claims | **Resolves.** | G3 certifies causal and accounting correctness only. No backtest return is quoted as performance evidence while membership and surveillance are stubs. | — |
| **B10-1** RS population | Option C (valid inputs) | §3: a strategy-independent reference universe; no truncation; no stale bars; date alignment; evaluate before changing the live screener | **Partial.** C meets every requirement except date alignment. The aligned variant CA changes about half the Top-25. | §3.2. | **S-4:** C or CA. **No default taken.** |
| **B10-2** `rel_volume` | Fix code to spec | §4 resolves | **Resolves.** | `rel_volume = volume[t] / mean(volume[t−49..t])`, the same 50-bar window as `avg_volume50`. | — |
| **B10-3** EMA seed | Fix code to spec | §4 resolves, if evidence supports it | **Resolves.** The browser golden fixture is the reference. | SMA(n) seed at bar n; MACD signal seeded the same way on the MACD line. Output withheld until the signal is seeded. | — |
| **B10-4** Tie-break | `symbol` ascending | §4: "stable, deterministic security identifier … symbol as an appropriate secondary key" | **CONFLICT.** ADD §21, spec §10 and the stored strategy config (`tie_breakers: [..., "symbol"]`, inside `config_hash`) all say `symbol`. ADD outranks a task prompt. | Proposed to satisfy both: `(…, rs_rating desc, symbol_at_run asc, isin asc, security_id asc)`. The symbol recorded with the run comes first, as ADD requires. ISIN and `security_id` make the key unique and exchange-independent. Production impact: 0 ranks (136 runs). | **S-7:** accept this, or amend ADD §21, spec §10 and the config (which changes `config_hash`) to put the identifier first. |
| **B10-5** Engine version | Q4 `ENGINE_VERSION`; `INDICATOR_VERSION` 3 | §7 distinct identities, reconciled with ADR-014 §10 | **Resolves, design changed.** | §4. | **S-8.** |
| **B10-6** Research validation | Report only | §10 compare In-Sample and Out-of-Sample; §8 preserve boundaries | **Partial.** This review read In-Sample data only. | In-Sample comparison in §5.3. | **S-9:** may the hold-out be read for this change? Default **no**. |
| **B10-7** R3-B-29 | Amend spec §10 | Silent | **Stands.** | Spec §10 states that gate engines are left out of both weighted scores. | — |

### New owner questions raised by Stage A

| # | Question | Evidence | Recommended default |
|---|---|---|---|
| **S-1** | Buy window | 1, 2 and 5 sessions give identical results in both windows | 5 sessions |
| **S-2** | Same-session sale proceeds or T+1 | T+1 defers 1,352 buy fills one session; +281% → +259% over 2021–2026 | Same session, as brief §5 places every trade at the same open. Disclosed as a simplification. |
| **S-3** | Participation cap | No cap: 64 fills above 10%, maximum 2.2× the session value. Cap 10%: +279%, 134 partial fills. Cap 2%: +267%. | 10% |
| **S-4** | RS window alignment, C or CA | §5.3: CA keeps 13.5 of 25 Top-25 names; In-Sample Top-25 return (120 sessions) 17.1% against 29.0% | **Owner clarification. No default.** |
| **S-5** | Identity chains (R3-B-31) | Up to 334 candidate pairs (heuristic); MAGMA frozen 1,269 sessions | Build a `security_identity_chain` from an authoritative NSE symbol-change source before any backtest claim. The source needs owner approval (it is an external download). |
| **S-6** | Write-down for a confirmed delisting with no successor | Lower bound +148% against marked +281% (2021–2026) | Keep marking at the last close and report the lower bound until delisting-price data exists. No automatic write-down. |
| **S-7** | Tie-break order | Conflict with ADD §21 | `symbol_at_run`, then `isin`, then `security_id` (no ADD change) |
| **S-8** | Amend ADR-014 §10 to identity schema 3 | §4 | Yes |
| **S-9** | Read the hold-out to evaluate engine v2 | Would spend hold-out evidence on a correctness fix | No |
| **S-10** | Verify the EQ-only gap explanation with one NSE bhavcopy fetch | Lead in §0 | Yes, once, read-only, after approval |
| **S-11** | Forward-return horizon in exchange sessions (R3-B-32) | Gap names inflated by about 15 points | Research decision; not part of engine v2. Record it in the research backlog. |
| **S-12** | Costs and dividends | Brief §7 sets 30 bps flat. There is no dividend-amount data (`corporate_actions.other`: 25,624 rows, no amounts). | Keep 30 bps. Report price return only, which matches the price-index benchmark. State that brief §2's dividend adjustment cannot be met. |
| **S-13** | One adjusted-price rule | Backtest reads `adj_close`; RS reads `adj_close`, else `close`; indicators compute `close × adj_factor`. 22,285 rows differ (R3-B-18). | Every engine uses `raw × adj_factor`. The stored `adj_close` column feeds no calculation. |

---

## 2. Execution and portfolio-accounting contract (backtest method v2)

### 2.1 Phases and the information each may use

| Phase | When | May use | Must not use |
|---|---|---|---|
| Signal | Close of D | Bars dated ≤ D. A name is scored only with a valid bar on D (E1). | Any bar after D; a stale `price(t)` |
| Plan | Before the open of F | Holdings and cash after D; the last close ≤ D for names without a bar on F | Prices of F |
| Order submission | Open of F | The plan | — |
| Execution | Open of each session s ≥ F | That session's valid execution bar only | Any other session's price |
| Settlement | Same session (S-2 default) | Fills of session s | — |
| Valuation | Close of each session | The last adjusted close ≤ s, flagged when stale | Future bars |

### 2.2 Orders

1. **Targets.** At F: equal weight = NAV before trading / number of target names (brief §4), with the buffer rule (brief §6).
2. **Order sizes.** Sells are share counts: a full exit sells all shares; a trim sells `−Δ / mark`. Buys are cash amounts `Δ`.
3. **Order of work in a session.** Sells, then buys, each in `security_id` order.
4. **Buy budget.** If total buy cash × (1 + cost) exceeds available cash after sells, scale every buy by one factor. No buy ever exceeds available cash.
5. **Execution (X1).** An order fills at the adjusted open of the first valid execution bar on or after F, within its window. The fill is capped by L1. The unfilled remainder waits under the same window.
6. **Expiry.** A buy expires after `BUY_WINDOW_SESSIONS` sessions, counting F (S-1). A sell stays live until filled. At the next F, every pending order is closed as `superseded`, and the new plan issues fresh orders.
7. **End of window.** Pending orders close as `open_at_end`. Holdings are reported at the last adjusted close ≤ the end date, with no liquidation.

### 2.3 Ledger

| Invariant | Rule |
|---|---|
| Holdings | `qty[s] = Σ filled quantity(s)`. No position exists without a fill. |
| Cash | `cash = initial − Σ(buy notional + cost) + Σ(sell notional − cost)`. `cash ≥ 0` after every fill. |
| Costs | 30 bps of each filled notional (brief §7), charged at the fill. |
| NAV | `NAV(s) = cash + Σ qty × last adjusted close ≤ s` |
| Reconciliation | Replaying the fill log gives the same holdings, cash and NAV as the running ledger, exactly (Decimal), at every session. |
| Units | Adjusted units: quantity × adjusted price is market value. A split or bonus needs no ledger event. A test shows `adj_qty × adj_price = raw_qty × raw_price` across MCX's 1:5 split. Cost basis is kept in the same units. |
| Realised and unrealised P&L | Average-cost basis per security. Realised P&L posts at each sell fill. |
| Dividends | Not modelled; the data holds no amounts (S-12). |
| Order states | `filled`, `partially_filled`, `pending`, `expired`, `superseded`, `open_at_end`. Every non-filled state carries its remaining notional or share count. |

### 2.4 The three properties the result must keep apart (direction §6)

| Property | Proven by | Not proven |
|---|---|---|
| Causal correctness | E1; X1; the look-ahead mutation test; every price dated on its execution session | — |
| Accounting correctness | The §2.3 invariants and the independent replay | — |
| Market realism | Not proven. The data is end-of-day OHLCV only, with no order book, auction depth or impact model. | The result shows participation, the cap, partial fills, non-trading weight and the lower bound, labelled "simulation assumptions". |

---

## 3. Universe and relative-strength specification

### 3.1 Reference equity universe (shared by the backtest and RS)

On a date t, a security belongs to the reference universe when all of these hold:

1. `exchange ∈ {NSE, BOTH}`. Dual-listed names use their NSE print; NSE is canonical ([`cross_listing.py`](../../../backend/src/momentum25/domain/research/cross_listing.py) rule 1).
2. It is an equity: `is_equity(isin)` is true, which excludes ISIN prefix `INF` (funds and ETFs).
3. Point in time: `listing_date ≤ t`, and not `t > delisting_date`. The current `is_active` flag is never used for history. This matches today's universe exactly on 8 sampled dates (`rs_ref.py`), so the change is a rule fix with no effect today.
4. Identity chain (S-5): an old row and its successor form one economic history. Until the chains exist, the result states this limitation.

**Strategy filters stay separate.** The brief's eligibility (12 months of history, Nifty 500 and T2T/ASM stubs) and the screener's gates (price, turnover, bars, staleness) apply after the reference universe. They never change it.

### 3.2 RS reference population and returns

The population on run date t is the reference universe (§3.1) restricted to names with valid RS inputs:

- at least 253 bars on or before t (R(252) needs `close[−252]`), with no window shortened to the bars available;
- not stale: `is_stale_as_of(t, last_bar)` is false (more than 30 days, [`data_quality.py:33`](../../../backend/src/momentum25/domain/research/data_quality.py#L33));
- prices are `close × adj_factor` (S-13).

**Returns, two options for S-4:**

| Option | R(d) | What it measures | Run 149 population | In-Sample effect (20 runs) |
|---|---|---|---|---|
| **C** | `close[t] / close[t − d own bars] − 1` (spec §8 as written) | The return over the name's own last d bars; for a gap name that is more than d sessions | 1,959 | Top-25 overlap with today 23.5 of 25; Top-25 return 28.1% against 29.0% (session-measured, 120 sessions) |
| **CA** | `close[t] / close(on or before exchange session t − d) − 1`. The anchor bar must sit within 5 sessions of that session, else the rating is `None` | The return over d exchange sessions, as the design intends ("252 ≈ 12 months") | 1,635 | Overlap 13.5 of 25; Top-25 return 17.1% |

Both options meet direction §3 on truncation, staleness, strategy independence and reproducibility. Only CA meets "comparison-date alignment". The In-Sample numbers show that CA removes the gap names that drive today's Top-25. Those names may be trade-for-trade names (§0 lead), and brief §1 would exclude them in the backtest. **Direction §10 forbids choosing between C and CA by historical performance.** The choice is about what RS should mean, so it is yours (S-4).

**Benchmark alignment.** The RS rating uses no benchmark. The RS line (`close / benchmark_close`) does, but no v3 rule reads it. The rule for the RS line: a benchmark close dated on the same session, else no value.

**New listings** get no rating until they have 253 bars. **Suspended or stale names** get no rating while stale.

### 3.3 Remaining R3-B-10 items

| Item | Rule | Kind of change |
|---|---|---|
| `rel_volume` | `volume[t] / avg_volume50`, both over bars t−49..t | Code fix; `INDICATOR_VERSION` 3 |
| EMA | SMA(n) seed at bar n; MACD signal seeded by SMA(9) of the MACD line; same warm-up as the browser fixture | Code fix; `INDICATOR_VERSION` 3 |
| Tie-break | S-7 | Code fix (default), or amend ADD and spec |
| Gate engines left out of scores | State it in spec §10 | Spec amendment only |

---

## 4. Methodology versioning and compatibility (reconciled with ADR-014 §10)

ADR-014 §10 (accepted) puts the market data (revision, calendar) and the engine (`INDICATOR_VERSION`, registry fingerprint) in one `data_version` hash. Runs are unique on `(strategy_id, run_date, data_version, config_hash)` ([`models.py:361`](../../../backend/src/momentum25/infrastructure/persistence/models.py#L361)), and runs are reused by that identity. §10 already requires a separate engine version, and `18cab43` shows the need: it changed every RS rating with no version change.

**Proposed identity schema 3 (amends ADR-014 §10; S-8):**

| Identity | Contents | Changes when |
|---|---|---|
| `market_data_version` (new, 12 hex) | revision, calendar version | Market data changes. Never on a commit. |
| `engine_identity` (new) | `ENGINE_VERSION` (new integer), `INDICATOR_VERSION`, rule-registry fingerprint, `RS_REFERENCE_VERSION` | Any analytical change |
| `data_version` (unchanged column, run key) | hash(schema 3, market identity, engine identity) | Either of the two above changes. A new engine on the same data therefore makes a new run and never reuses an old one. |
| `config_hash` | Strategy configuration | Unchanged rule |
| `build_id` | Image build or commit | Stored, never hashed (as §10) |
| Backtest identity | `market_data_version`, `BACKTEST_METHOD_VERSION`, the execution-policy constants (`BUY_WINDOW_SESSIONS`, `PARTICIPATION_CAP`, settlement), the reference-universe version, and the request | Any of these |
| Research run | Existing `:research:` runs carry the full schema-3 manifest | — |

**Compatibility rules:**

1. Schema 1 and 2 bodies keep their hash rules. Every stored key loads and replays; run 149's `8790a000bd4f` is reproduced in a test.
2. No stored run, rule row, explanation, manifest, forward return or audit file is rewritten or relabelled. Old results show the engine identity they were produced with, or "engine v1 (pre-schema-3)".
3. **No silent comparison.** Score and rank history, `/research/compare/runs`, `/research/compare/strategies`, Studio comparisons and the validation dashboard either refuse to compare results with different engine identities or show a labelled break.
4. **Caches.** The RS cache key becomes `m25:rs_ratings:v3:{engine_identity}:{market_data_version}:{rs_weights_hash}:{date}`. Today's key `(strategy_name, date)` would serve old ratings after an engine change, which is R3-B-14's class of bug. No other result cache may key on anything less than the run identity.
5. **In-Sample and hold-out.** The boundaries are unchanged. Sealed hold-outs stay sealed with their stored identity. Engine v2 never re-runs a sealed hold-out automatically (S-9).
6. **Backtest.** No backtest result is persisted today. The audit files `wf_1.json` and `wf_2.json` (SHA-256 `8da9853e…`) stay as method v1 evidence, reproducible from `2506150` at revision 133621. No v1 mode stays in code.

---

## 5. Financial impact and sensitivity

**These numbers show sensitivity to modelling choices. They are not evidence of investment performance (direction §10).** Benchmark: Nifty 500 Price Index (not TRI). Source: [`stageA_grid.json`](../../../audit-evidence/audit-r3/backend/decision-packet/stage-a/stageA_grid.json), [`t1.json`](../../../audit-evidence/audit-r3/backend/decision-packet/stage-a/t1.json).

### 5.1 Corrections applied one at a time (E1 on, buys at F only, sells retried)

| Configuration | 2025-01 → 2026-07 | 2021-01 → 2026-07 | Names scored per rebalance |
|---|---|---|---|
| Audit baseline (current engine) | −9.0% (stale fills 27.4%) | not run by the audit | 166–211 |
| U0: current universe and prices | +23.8% | +332% | 122–190 |
| U1: + dual-listed names, − funds | −7.9% | +334% | 1,153–1,808 |
| **U2: + computed prices (R3-B-30)** | **−8.5%** | **+281% (CAGR 27.1%)** | 1,283–1,919 |

### 5.2 Execution-policy sensitivity on U2

| Policy | 2025–26 return / max DD | 2021–26 return / CAGR / max DD | 2021–26 lower bound | Notes (2021–26) |
|---|---|---|---|---|
| Buys at F only | −8.5% / −29.4% | +281% / 27.1% / −21.6% | +148% | 11 buys cancelled (₹4.2 lakh) |
| Buy window 2 or 5 sessions | identical | identical | identical | 0 deferred buys |
| Buys until the next decision | −8.6% | +279% | +147% | 4 deferred buys |
| No sell retry (policy A) | −9.8% | +316% | +152% | Max single weight 11.8% |
| Cap 10% | −8.3% | +279% | +149% | 134 partial fills |
| Cap 2% | −7.7% | +267% | +145% | 585 partial fills |
| T+1 settlement | −10.0% | +259% / 25.8% | +132% | 1,352 buys one session late |
| No E1 (current signal rule) | −2.0% | +286% | +128% | Buys worth ₹1.85 crore cancelled; mean cash 10.8% |

Cash never goes below zero in any row. For the base policy (buys at F only, 2021–26): mean holdings 44.9 against a target of 30 (between 34.0 and 47.2 across the rows); **35% of end NAV in 18 non-trading holdings**, 13 of which never trade again in the data (`stuckA.json`); one-way turnover 2.8× a year.

**Reading.** The universe and price-source corrections, the non-trading valuation (+281% against +148%) and settlement move the result most. The buy window does not move it. A defensible headline needs R3-B-31 identity chains (S-5) more than any further execution refinement.

### 5.3 RS and screener impact, In-Sample only

20 runs, 2020-11-27 → 2022-06-30, forward exits ≤ 2022-12-30. The hold-out is not read. Source: [`rs_ref.json`](../../../audit-evidence/audit-r3/backend/decision-packet/stage-a/rs_ref.json), [`rs_align.json`](../../../audit-evidence/audit-r3/backend/decision-packet/stage-a/rs_align.json).

| RS population | Rated | Qualified | Top-25 overlap with today | Top-25 return, 120 sessions (stored / session) | Rank IC, 120 (stored) |
|---|---|---|---|---|---|
| A today | 1,842 | 255 | 25 | 31.2% / 29.0% | −0.047 |
| C | 1,385 | 275 | 23.5 | 31.0% / 28.1% | −0.044 |
| CA | 1,186 | 241 | 13.5 | 18.9% / 17.1% | — |

The paired difference C − A over 20 runs is −0.22 points (6 runs better, 11 worse, 3 equal), which is negligible. Eight more runs from 2020 to 2026 (packet §6.1) show the same pattern for C. These figures cannot separate In-Sample from Out-of-Sample effects, because the hold-out was not read (S-9).

---

## 6. Independent verification and acceptance-test plan

Every test uses fixtures built by hand or computed by the reference simulator ([`sim2.py`](../../../audit-evidence/audit-r3/backend/decision-packet/stage-a/sim2.py)). None imports the production code under test. Each test must fail before its fix.

| Area | Test |
|---|---|
| Decision-date bar | A name whose last bar is D−1 is not scored. |
| Next-session execution | No bar on F, a bar on F+2: the order fills at F+2's adjusted open. Every fill's bar is dated on its fill session. |
| Missing and stale prices | No price from another session is ever a fill price (property test over the 2021–2026 replay: 0 violations). |
| Pending and expired orders | A buy expires after `BUY_WINDOW_SESSIONS`. A sell persists and is superseded at the next F. `open_at_end` is reported. |
| Suspensions and delistings | A held name stops trading: it stays held, is marked at its last close, is flagged after 20 sessions, and appears in the lower bound. |
| Cash and positions | §2.3 invariants after every session; replay equals the ledger exactly; `cash ≥ 0`. |
| Partial fills and costs | Cap 10% with a known `turnover_value`: fill = 10%, the remainder waits; cost = 30 bps of filled notional only. |
| Dual-listed names | RELIANCE (`BOTH`) is in the universe and priced from its own bars. An ingestion test shows a BSE print never overwrites the NSE bar of a `BOTH` name. |
| Fund exclusion | EBBETF0425 and every `INF…` ISIN are absent. |
| Point-in-time universe | A name listed after t is absent; a name delisted before t is absent; `is_active` is never read for history. |
| Identity chains (after S-5) | TWL → TITAGARH: the position carries 1:1 on 2023-06-19; RS for TITAGARH in 2024 uses TWL's history. |
| RS completeness and freshness | Fixture: a 200-bar name, a stale name and an ETF all get no rating. C or CA anchor rules per S-4. |
| `rel_volume` | 50 known volumes: exact equality with `v[t] / mean(v[t−49..t])`. |
| EMA | Backend equals `golden-fixture.json` to 1e-9 for EMA10, EMA21 and MACD (line, signal, histogram), warm-up included. |
| Tie-break | Three tied names whose id order differs from symbol order: S-7 order. Run 149 replay: ranks unchanged. |
| Corporate actions | Across MCX's 1:5 split: holding value is continuous, and adjusted units equal raw units × factor. |
| Research immutability | Run 149's hashes, rules and key `8790a000bd4f` are unchanged after the upgrade. A schema-2 key still loads. A comparison across engine identities is refused or labelled. |
| Determinism | Two runs of the backtest and of a screen give byte-identical outputs. |
| Look-ahead | The leaky-provider mutation tests still raise `LookAheadError`, including on a deferred fill. |
| Reference agreement | The production backtest equals `sim2.py` with the approved parameters on the 2021–2026 replay: same fills, NAV to 1e-20. |

---

## 7. Prioritised implementation plan (Stage B, after approval)

Each step is one coherent local commit, or a short series, with its tests. Nothing is pushed or deployed.

| # | Step | Depends on | Changes results? |
|---|---|---|---|
| 1 | **Versioning first:** identity schema 3, `ENGINE_VERSION`, `market_data_version`, cache keys, comparison guards. ADR-014 §10 amendment. | S-8 | No (identity only) |
| 2 | **One adjusted-price rule** (S-13), used by the backtest, RS and indicators | 1 | Yes: engine v2 |
| 3 | **Reference equity universe** (§3.1): BOTH included, funds excluded, point-in-time listing. Shared by the backtest and RS. | 1 | Yes |
| 4 | **Backtest method v2:** E1, X1, L1, C1, the ledger (§2.3), order states and disclosures. `BACKTEST_METHOD_VERSION = 2`. API fields and TS types. | 2, 3, S-1 to S-3 | Yes (backtest only) |
| 5 | **Screener engine v2:** RS population (S-4), `rel_volume`, EMA, tie-break (S-7), `INDICATOR_VERSION` 3; read-path parity (R3-B-08). | 1–3, S-4, S-7 | Yes (new runs only) |
| 6 | **Identity chains** (R3-B-31): table, loader, ledger carry-over, RS history join | S-5 data source | Yes |
| 7 | **Provenance in the UI and research views:** engine identity on runs, history breaks, labelled comparisons | 1 | No |
| 8 | **Docs:** spec §8 and §10, brief addendum "execution method v2", ADR-014 §10, research index note, register, dashboard | all | No |
| 9 | **Benchmarks:** screen duration with the RS population change; backtest duration with the session loop (2021–2026 replay ran in under 60 s in the reference) | 4, 5 | — |

Steps 4 and 5 are independent once 1–3 land. Step 6 is the largest unknown: it needs an approved data source.

---

## 8. Status

- R3-B-09, R3-B-10 and R3-B-27 to R3-B-32 stay **open, awaiting owner decisions**. Nothing in this document is approved.
- Stage B starts only after explicit approval of the open choices in §1: S-1 to S-13, and the matrix rows marked Partial or CONFLICT.
- The [remediation register](REMEDIATION_REGISTER.md) and `.dashboard/index.html` are updated to this status.
