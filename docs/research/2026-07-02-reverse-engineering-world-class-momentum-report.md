# Research Program — Reverse Engineering World-Class Momentum Investing

**Date:** 2026-07-02  
**Scope:** Pure research / discovery. No production code or strategy config changes.  
**Objective:** Understand what behaviours the world's greatest momentum investors are attempting to identify, map those behaviours against Momentum25's current deterministic representation, and produce a prioritised roadmap of candidate characteristics for future walk-forward validation.

---

## Executive Recommendation (Deliverable 10)

**Continue the ranking-improvement freeze, but redirect research toward three specific missing-behaviour buckets that are under-represented in Momentum25 and do not depend on fixing the within-qualified-pool ranking inversion.**

The platform's current methodology already captures the core "Minervini trend template + relative strength" behaviour cluster well. The prior research cycle established that further linear re-composition of existing rules is exhausted and that the ranking mechanism's weak IC is the binding constraint. This program finds that the most promising *new* deterministic behaviours fall into three categories:

1. **Market and sector confirmation** (breadth, leadership, capital rotation) — currently almost unrepresented because sector/industry data and historical index constituents are unavailable.
2. **Volume-behaviour nuance beyond simple breakout confirmation** — volume dry-up during consolidation, volume expansion on breakout, institutional accumulation footprint, and supply/demand imbalance are only partially measured.
3. **Late-stage exhaustion / false-breakout avoidance** — the one coherent finding already identified (extension/acceleration/streak-length) is still poorly represented by a single loose `risk_extension` cap.

No candidate is ready for promotion. Every proposed characteristic requires walk-forward validation against a hold-out window that includes a genuine correction, which the current dataset cannot supply. The immediate next step is to use the existing corrected platform to *measure* the simplest candidate (a cross-sectional extension percentile cap) observationally, then wait for the 2026-H1 120-day forward window and additional regime diversity before any promotion decision.

---

## 1. Behavioural Momentum Taxonomy (Deliverable 1)

Momentum investing, at its root, is not about indicators. It is about identifying a recurring set of market behaviours that precede abnormal forward returns. The taxonomy below groups those behaviours into eight clusters. Each cluster is defined by the *economic or behavioural mechanism* it attempts to exploit, not by the formula used to measure it.

### Cluster A — Trend Quality
The behaviour: a security's price is rising in a sustained, ordered way rather than through chaotic spikes.

- **Trend persistence:** price remains above key moving averages for extended periods.
- **Trend smoothness:** the path of least resistance is upward with minimal violent reversals.
- **Trend maturity:** the move is early enough to have room, but mature enough to have proven itself.
- **Multi-timeframe agreement:** short-, medium-, and long-term trends point in the same direction.

### Cluster B — Relative Strength & Leadership
The behaviour: the security is outperforming peers, the sector, and the benchmark because capital is flowing into it preferentially.

- **Universe relative strength:** raw and risk-adjusted outperformance vs. the broad market.
- **Sector/industry leadership:** outperformance within the stock's own economic peer group.
- **Leadership persistence:** the security has remained a leader for multiple measurement windows.
- **Capital rotation:** money is moving from laggards to leaders at the sector/style level.

### Cluster C — Base / Consolidation Quality
The behaviour: after an advance, the stock pauses in a tight, constructive way that allows supply to be absorbed without destroying the trend.

- **Volatility contraction:** daily ranges shrink as the consolidation matures.
- **Volume dry-up:** participation declines during the consolidation, indicating limited selling pressure.
- **Base depth control:** the correction within the base is shallow enough to preserve trend structure.
- **Base width/time:** the consolidation is long enough to build a foundation.
- **Pattern recognition:** VCP, flat base, cup-with-handle, high-tight flag, ascending base.

### Cluster D — Breakout & Follow-Through
The behaviour: the stock transitions from consolidation to a new leg up with conviction.

- **Breakout quality:** price moves into the upper portion of its recent range.
- **Volume expansion on breakout:** above-average volume confirms institutional participation.
- **Follow-through:** price holds above the breakout level in subsequent sessions.
- **False-breakout avoidance:** the breakout does not immediately collapse back into the base.

### Cluster E — Momentum Quality & Acceleration
The behaviour: the rate of price change is healthy — building, but not parabolic.

- **Momentum persistence:** recent returns are positive and stable across multiple horizons.
- **Momentum acceleration:** shorter-horizon returns exceed longer-horizon returns (momentum building).
- **Momentum exhaustion:** the opposite — returns become too compressed into too short a window.
- **Risk-adjusted momentum:** high return per unit of realised volatility.

### Cluster F — Risk Asymmetry & Positioning
The behaviour: the entry point offers a favourable ratio of potential reward to likely risk, and the stock is not already over-owned.

- **Extension from key averages:** price is not too far above support.
- **Volatility level:** realised volatility is not so high that normal noise will stop the position out.
- **Risk-reward:** distance to a logical stop vs. distance to a logical target.
- **Crowding / positioning:** the move is not so obvious that everyone is already positioned.

### Cluster G — Market & Sector Confirmation
The behaviour: the stock's move is occurring in a supportive market and sector environment.

- **Market trend confirmation:** the broad index is in an uptrend or at least not in a severe correction.
- **Sector confirmation:** the stock's sector is also showing relative strength.
- **Breadth participation:** many stocks are participating in the advance, not just a narrow few.
- **Industry leadership:** the strongest names within a strong industry are preferred.

### Cluster H — Liquidity & Microstructure
The behaviour: there is enough liquidity to enter and exit without excessive slippage, and the price action is not dominated by illiquidity artefacts.

- **Minimum turnover:** average daily value traded is above a floor.
- **Volume behaviour around price moves:** volume expands with the trend and contracts on pullbacks.
- **Bid-ask / slippage proxy:** ADR% and ATR give indirect evidence of execution cost.

---

## 2. World-Class Momentum Decision Framework (Deliverable 2)

The investors and research sources named in the task can be reverse-engineered into a common decision sequence. Exceptional momentum investors do not ask "What is the RSI?" They ask a sequence of behavioural questions:

### Step 1 — Is there a trend worth attaching to?
- **Minervini / O'Neil:** Is the stock above rising 50/150/200-day MAs? Is the long-term MA rising? This filters out stocks with no persistent demand.
- **Clenow / AQR:** Is the stock in the top percentile of trailing returns? This is the pure quantitative expression of the same behaviour.
- **Darvas:** Is the stock making a new high in a defined box? Box theory is a behavioural filter for trend emergence.

**Behaviour being exploited:** Persistent capital inflow creates serial correlation in returns (Jegadeesh & Titman 1993; Moskowitz & Grinblatt 1999). The trend itself is the market's way of revealing that information is being impounded gradually.

### Step 2 — Is the stock a leader within that trend?
- **Minervini / O'Neil:** RS rating ≥ 70–80; stock near 52-week highs while the market is also constructive.
- **Driehaus:** "Buy high, sell higher" — prefer stocks already outperforming because they attract further capital.
- **Alpha Architect / Quantopian:** Cross-sectional momentum sorts — the top decile of past winners continues to win.

**Behaviour being exploited:** Cross-sectional return persistence (Asness 1994; Carhart 1997). Investors underreact to firm-specific news, and capital chases visible winners, creating a self-reinforcing flow.

### Step 3 — Is the consolidation / base constructive?
- **Minervini:** VCP — volatility contracts, volume dries up, depth is controlled.
- **O'Neil:** Cup-with-handle, flat base, high-tight flag.
- **Ryan / Ritchie II:** Tight price action near highs is a sign of supply absorption.

**Behaviour being exploited:** After an advance, weak holders exit and strong holders absorb supply. A tight base indicates that supply has been exhausted and the next leg can begin with less resistance (Livermore's "line of least resistance").

### Step 4 — Is the breakout genuine?
- **Minervini / O'Neil:** Volume expansion on breakout; price holds the breakout level.
- **Driehaus:** Follow-through days and confirmation of demand.

**Behaviour being exploited:** Breakouts reveal new information or a shift in the supply/demand balance. Genuine breakouts are accompanied by expanded volume because institutional participation is required to move price out of a well-defined range.

### Step 5 — Is the entry asymmetric?
- **Minervini:** Extension cap (not too far above SMA50); ADR% cap; risk-reward check.
- **Livermore:** Don't chase; wait for the pivot where risk is small and reward is large.
- **Antonacci:** Dual-momentum combines absolute (trend) and relative (strength) filters to avoid asymmetrically bad entries.

**Behaviour being exploited:** Late-stage entries have negative skew — the stock has already discounted much of the good news, and any disappointment causes large drawdowns. Early-stage entries have positive skew because the trend is young and the base is fresh.

### Step 6 — Is the market and sector environment supportive?
- **O'Neil:** Follow the market direction; three out of four stocks follow the market.
- **Minervini:** Prefer leading stocks in leading groups.
- **Driehaus:** Sector themes and macro confirmation matter.

**Behaviour being exploited:** Momentum is a cross-sectional phenomenon, but its payoff is conditional on the market regime (Daniel & Moskowitz 2016; momentum crashes in panics). Sector confirmation reduces the chance that a stock's strength is idiosyncratic and fragile.

### Step 7 — Is liquidity sufficient?
- **Clenow / professional systematic:** Minimum turnover, capacity constraints, slippage estimates.
- **Market microstructure:** The signal must be tradable at the intended size.

**Behaviour being exploited:** Illiquidity creates noise, gap risk, and implementation shortfall. A momentum signal that cannot be executed is not a real signal.

---

## 3. Behaviour Coverage Matrix (Deliverable 3)

The matrix maps each behaviour from the taxonomy to Momentum25's current rules/engines, using evidence from the prior research programs.

| Behaviour | Current Representation | Engine / Rule | Coverage Verdict | Evidence |
|---|---|---|---|---|
| **Trend persistence** | Fully represented | `tt_close_above_sma50/150/200`, `tt_sma_stack`, `tt_sma200_uptrend`, `mq_trend_persistence` | Fully represented | All 8 trend_template rules have positive return deltas; engine-level all-passed return +2.9pp to +3.6pp higher than some-fail. |
| **Multi-timeframe agreement** | Fully represented | Trend Template stack + RS multi-timeframe blend | Fully represented | SMA50 > SMA150 > SMA200 + 63/126/189/252d RS weights capture short/medium/long agreement. |
| **Trend smoothness** | Missing | None | Missing | No measure of how orderly the price path is (e.g., linear trend R², consecutive up/down days, drawdown profile). |
| **Trend maturity** | Partially represented | `tt_above_52w_low` (≥30% off low), `tt_near_52w_high` (≤25% below high) | Partially represented | Captures "not too early, not too extended" but only at two fixed points; no dynamic measure of where the stock is in its move. |
| **Universe relative strength** | Fully represented | `rs_rating`, `tt_rs_rating_min` | Fully represented | Strongest single rule delta (+4.09pp); strongest engine gap (+6.50% vs +2.41%). |
| **RS leadership persistence** | Partially represented | `rs_rating_trend`, `rs_line_slope` | Partially represented | `rs_line_slope` is computed but not used in any active rule; `rs_rating_trend` is categorical and coarse. |
| **Sector/industry leadership** | Missing | `rs_sector_relative`, `rs_industry_relative` are dead | Missing | No sector/industry classification data ingested; rules removed from config. |
| **Capital rotation** | Missing | None | Missing | No sector-momentum or style-rotation measurement. |
| **Base depth control** | Partially represented | Pattern detectors use depth thresholds | Partially represented | VCP (≤35%), flat base (≤15%) measure depth, but evidence is mixed/negative on predictive value. |
| **Base width/time** | Partially represented | Pattern detectors enforce minimum lengths | Partially represented | Flat base requires 25–65 days; VCP uses 80-bar lookback; but no standalone "consolidation quality" score. |
| **Volatility contraction** | Partially represented | VCP detector, `adr_pct` | Poorly measured | RP3 explicitly rejected volatility contraction as a predictor; VCP's contraction logic is segment-based and may be too coarse. |
| **Volume dry-up** | Missing | `vol_accumulation_days` measures net up/down volume, not dry-up | Missing | No rule for "volume declining into a consolidation low." |
| **Pattern recognition** | Partially represented | VCP, flat base, cup-handle, ascending base | Partially represented / poorly measured | Pattern rules show mixed/negative deltas; VCP/flat_base trend positive, cup/ascending trend negative. |
| **Breakout quality** | Fully represented | `bo_pivot_breakout` | Fully represented | +3.44pp return delta; strong positive signal. |
| **Volume expansion on breakout** | Partially represented | `vol_breakout_confirm` (rel_volume ≥ 1.4x) | Partially represented | Positive delta (+2.63pp), but only a single-day relative-volume check; no multi-day expansion footprint. |
| **Follow-through** | Fully represented | `bo_followthrough` | Fully represented | +2.33pp return delta. |
| **False-breakout avoidance** | Partially represented | `bo_false_breakout` | Partially represented | Positive delta (+2.11pp), but measured as "close above midpoint" — a simple proxy, not a true failure test. |
| **Momentum persistence** | Fully represented | `mq_trend_persistence`, RS blend | Fully represented | `mq_trend_persistence` has small positive delta; RS blend captures persistence across horizons. |
| **Momentum acceleration** | Poorly measured | `mq_acceleration` (20d > 63d return) | Poorly measured | Negative contribution-level IC (-0.0233, p<0.01); RP3 found more acceleration predicts worse returns. |
| **Momentum exhaustion** | Partially represented | `risk_extension` (≤25% above SMA50) | Partially represented | Failures average 27.5% extension vs. 17.9% for winners; current cap is too loose. |
| **Risk-adjusted momentum** | Missing | None | Missing | No Sortino-like or Sharpe-like characteristic in scoring. |
| **Extension from key averages** | Partially represented | `risk_extension` | Partially represented | Same as exhaustion — one loose cap on SMA50 extension. |
| **Volatility level** | Partially represented | `risk_atr` (ADR% ≤ 8%) | Poorly measured | Large negative rule delta (-22.6pp) driven by tiny fail group; likely outlier-driven, not a stable signal. |
| **Risk-reward** | Partially represented | `risk_rr` | Partially represented | Negative contribution-level IC; uses ATR-based stop and 20-day high target — a rough proxy. |
| **Crowding / positioning** | Missing | None | Missing | No measure of how consensus or over-owned a stock is. |
| **Market trend confirmation** | Partially represented | Regime classification exists but is not used in scoring | Partially represented | Regime labels (bull_low_vol, bear_low_vol, etc.) are computed for research but do not feed the strategy. |
| **Sector confirmation** | Missing | Dead rules, no data | Missing | Same sector/industry data gap. |
| **Breadth participation** | Missing | None | Missing | No advance/decline, new highs/lows, or participation breadth measures. |
| **Industry leadership** | Missing | Dead rules, no data | Missing | Same sector/industry data gap. |
| **Minimum turnover** | Fully represented | `vol_liquidity_min` (₹1cr gate) | Fully represented | Gate rule; near-threshold evidence supports current floor. |
| **Volume behaviour around moves** | Partially represented | `vol_breakout_confirm`, `vol_accumulation_days` | Partially represented | Measures expansion and net accumulation, but not dry-up or institutional footprint. |
| **Slippage / execution cost** | Missing | ADR% is used as risk, not cost | Missing | No explicit slippage or capacity estimate. |

### Summary of coverage

- **Fully represented (8):** trend persistence, multi-timeframe agreement, universe RS, breakout quality, follow-through, momentum persistence, minimum turnover.
- **Partially represented (11):** trend maturity, RS leadership persistence, base depth/width, volume expansion on breakout, false-breakout avoidance, momentum exhaustion, extension, risk-reward, market confirmation, volume behaviour around moves.
- **Poorly measured (3):** trend smoothness, volatility contraction, volatility level.
- **Missing (9):** sector/industry leadership, capital rotation, volume dry-up, risk-adjusted momentum, crowding/positioning, sector confirmation, breadth participation, industry leadership, slippage/execution cost.

---

## 4. Missing Behaviour Report (Deliverable 4)

This section lists the behaviours that are either missing or poorly measured, grouped by cluster. For each, it states the economic/market rationale, supporting literature, and why the current representation is insufficient.

### A. Trend Smoothness
**Behaviour description:** How orderly and uninterrupted the price path is. Smooth trends indicate controlled, institutional accumulation; choppy trends indicate conflict between buyers and sellers.

**Economic rationale:** Information-driven moves tend to be smooth because informed buyers accumulate gradually. Noise-driven moves are choppy. Smoothness should predict lower forward volatility and higher risk-adjusted returns.

**Market rationale:** A stock that rises in a tight channel is behaving differently from one that rises through large gaps and reversals. The former suggests supply is being absorbed; the latter suggests speculation.

**Supporting literature:** 
- Baltas & Kosowski (2013) on trend-following and volatility-adjusted momentum.
- Lemperiere et al. (2014) on trend quality and risk-adjusted returns.

**Current gap:** No measure of price-path smoothness exists. `mq_trend_persistence` counts days above an MA but does not measure the *quality* of the path.

### B. Volume Dry-Up During Consolidation
**Behaviour description:** Volume declines meaningfully as a stock consolidates near highs, indicating that sellers are exhausted and the float is being held by strong hands.

**Economic rationale:** Low volume in a base means the marginal seller is absent. When demand returns, there is less supply to absorb, so the breakout can be more explosive.

**Market rationale:** Minervini's VCP explicitly requires volume contraction. Momentum25's VCP detector checks segment-volume decline but does not produce a standalone, continuous "volume dry-up" score.

**Supporting literature:** 
- Minervini, *Trade Like a Stock Market Wizard* (VCP definition).
- O'Neil, *How to Make Money in Stocks* (base-on-base, volume dry-up).

**Current gap:** `vol_accumulation_days` measures net buying pressure, not dry-up. No rule uses the lowest-volume percentile within a consolidation.

### C. Sector / Industry Leadership & Confirmation
**Behaviour description:** The stock is outperforming within its own sector and industry, and those groups are themselves showing relative strength.

**Economic rationale:** Sector momentum is often stronger than individual-stock momentum because industry-wide factors (commodity prices, regulation, demand cycles) affect many firms simultaneously (Moskowitz & Grinblatt 1999).

**Market rationale:** A leading stock in a leading group has tailwinds from both stock-specific and group-specific capital flows. A leading stock in a weak group is fighting the tide.

**Supporting literature:** 
- Moskowitz & Grinblatt (1999), "Do Industries Explain Momentum?"
- Asness (1994), "The Power of Past Returns."

**Current gap:** `rs_sector_relative` and `rs_industry_relative` are dead because sector/industry classification data is not ingested. The RS pipeline computes sector/industry percentiles only in non-batch mode, which is not the production path.

### D. Capital Rotation / Style Momentum
**Behaviour description:** Money is rotating into the styles/sectors that have recently shown strength (e.g., small-cap vs. large-cap, value vs. growth, cyclical vs. defensive).

**Economic rationale:** Institutional capital rebalances slowly across sectors and styles, creating persistence in style returns.

**Market rationale:** A stock's momentum is more reliable when it aligns with the current capital-rotation theme.

**Supporting literature:** 
- Asness (1997), "The Interaction of Value and Momentum Strategies."
- Bhojraj & Swaminathan (2006) on style momentum.

**Current gap:** No style or sector rotation measurement exists.

### E. Risk-Adjusted Momentum
**Behaviour description:** The stock's recent return is high relative to the volatility required to earn it.

**Economic rationale:** Investors should prefer high return per unit of risk. A stock that rises 20% with 1% daily ranges is a better bet than one that rises 20% with 5% daily ranges.

**Market rationale:** Lower-volatility momentum has historically delivered better risk-adjusted returns and smaller drawdowns.

**Supporting literature:** 
- Blitz & van Vliet (2008), "Global Tactical Cross-Asset Allocation."
- Asness et al. (2013), "The Devil in HML's Details."

**Current gap:** No Sortino-like or Sharpe-like characteristic is part of the score. `risk_atr` attempts to cap volatility but is poorly calibrated.

### F. Crowding / Positioning
**Behaviour description:** The stock is not so universally owned or discussed that a disappointment will cause a rapid unwind.

**Economic rationale:** Overcrowded trades have asymmetric downside — when everyone who wants to own it already does, the marginal buyer is gone.

**Market rationale:** Exceptional momentum investors often find stocks *before* they become obvious. A deterministic proxy is needed for "not yet obvious."

**Supporting literature:** 
- Stein (2009), "Presidential Address: Sophisticated Investors and Bubbles."
- Greenwood & Hanson (2015) on crowded trades.

**Current gap:** No proxy for crowding exists (e.g., volume vs. market cap, media/social attention, institutional ownership concentration).

### G. Breadth Participation
**Behaviour description:** The market advance is broad, with many stocks participating, not just a narrow leadership group.

**Economic rationale:** Broad participation indicates healthy demand and reduces reliance on a few names. Narrow participation often precedes market tops.

**Market rationale:** A stock's breakout is more reliable when confirmed by broad market strength.

**Supporting literature:** 
- Zweig (1970s) on advance-decline lines.
- McClellan (1999) on breadth oscillators.

**Current gap:** No breadth measures exist.

### H. True False-Breakout / Failure Test
**Behaviour description:** After a breakout, the stock pulls back to a logical support level and holds, confirming that the breakout level has become support.

**Economic rationale:** A breakout that immediately fails indicates that supply was merely hidden, not absorbed. A successful retest confirms demand.

**Market rationale:** Minervini and O'Neil both emphasise buying on follow-through, not on the first thrust.

**Supporting literature:** 
- Minervini, *Think & Trade Like a Champion*.
- Edwards & Magee, *Technical Analysis of Stock Trends*.

**Current gap:** `bo_false_breakout` only checks whether close is above the 20-day midpoint. It does not test a retest of the breakout level or a volume dry-up on the pullback.

### I. Momentum Exhaustion (Late-Stage Extension)
**Behaviour description:** The stock has moved too far, too fast, and is statistically extended from its base — increasing the probability of a sharp correction.

**Economic rationale:** Short-term returns are bounded; a stock that has already discounted a large amount of good news has worse forward skew.

**Market rationale:** RP3 found failures average 27.5% above SMA50 vs. 17.9% for winners. The current 25% cap is too loose.

**Supporting literature:** 
- Hong & Stein (1999) on gradual information diffusion and eventual reversal.
- Daniel, Hirshleifer & Subrahmanyam (1998) on overreaction.

**Current gap:** Only `risk_extension` measures this, and its threshold is static and loose. No cross-sectional percentile cap or multi-metric exhaustion score exists.

### J. Slippage / Capacity
**Behaviour description:** The signal is tradable at the intended size without excessive market impact.

**Economic rationale:** Even a genuine momentum signal can be eroded by implementation costs.

**Market rationale:** Professional systematic investors explicitly model capacity. Discretionary investors implicitly avoid illiquid names.

**Supporting literature:** 
- Frazzini, Israel & Moskowitz (2018) on trading costs and momentum.
- Korajczyk & Sadka (2004) on capacity constraints.

**Current gap:** `vol_liquidity_min` is a binary floor, not a continuous capacity score.

---

## 5. Candidate Deterministic Characteristics (Deliverable 5)

For each missing/poorly measured behaviour, this section proposes the *simplest* deterministic measurement that captures the behaviour. Candidates are designed to use existing data where possible.

### Candidate C1 — Trend Smoothness Score
**Behaviour:** Trend smoothness.  
**Measurement:** Linear regression R² of log(close) over the last 50 sessions, or equivalently the ratio of trend return to total absolute daily movement (path efficiency).  
**Algorithm:**
```
log_prices = log(close[-50:])
x = 0..49
slope, intercept = linear_regression(x, log_prices)
predicted = slope * x + intercept
r_squared = 1 - sum((log_prices - predicted)^2) / sum((log_prices - mean(log_prices))^2)
smoothness_score = clamp(r_squared, 0, 1)
```
**Required data:** OHLCV close series (already available).  
**Expected predictive value:** Positive for risk-adjusted forward returns; likely weak alone, stronger as a tie-breaker.  
**Interaction:** Complements `mq_trend_persistence` and Trend Template by adding path-quality information.  
**Complexity:** Low — pure pandas/numpy, no new data.  
**Validation:** Correlation with forward return and forward volatility; decile test.  
**Failure modes:** Low-volatility stocks may score high without momentum; must be combined with trend filters.

### Candidate C2 — Volume Dry-Up Score
**Behaviour:** Volume dry-up during consolidation.  
**Measurement:** Ratio of current 5-day average volume to the 25-day average volume, inverted and normalised. A low ratio indicates recent volume contraction.  
**Algorithm:**
```
vol_5 = mean(volume[-5:])
vol_25 = mean(volume[-25:])
dry_up_ratio = vol_5 / vol_25 if vol_25 > 0 else 1
dry_up_score = clamp(1 - dry_up_ratio, 0, 1)
# Only apply when price is consolidating near highs (e.g., pct_below_high_52w <= 10 and ADR% below median)
```
**Required data:** Volume series (already available).  
**Expected predictive value:** Positive for breakout success; should improve `vol_breakout_confirm` by filtering to genuine dry-up.  
**Interaction:** Works with VCP/flat_base and breakout engines.  
**Complexity:** Low.  
**Validation:** Compare forward returns of high dry-up vs. low dry-up within the qualified set.  
**Failure modes:** Volume can dry up because a stock is simply forgotten, not because supply is exhausted — must be conditioned on being near highs and in an uptrend.

### Candidate C3 — Sector / Industry RS Resurrection (Conditional on Data)
**Behaviour:** Sector and industry leadership.  
**Measurement:** Re-enable `rs_sector_relative` and `rs_industry_relative` once sector/industry classification is ingested. Use the existing RS pipeline's sector/industry percentile computation.  
**Algorithm:**
```
sector_rs_percentile = percentile rank of stock's composite RS within its sector
industry_rs_percentile = percentile rank within its industry
pass if sector_rs_percentile >= 50 and industry_rs_percentile >= 50
score = mean(sector_rs_percentile, industry_rs_percentile) / 100
```
**Required data:** Sector and industry classification for every security (currently unavailable from free NSE sources).  
**Expected predictive value:** Moderate to strong; Moskowitz & Grinblatt found industry momentum explains much of individual momentum.  
**Interaction:** Adds a second layer of relative strength beyond universe RS.  
**Complexity:** Medium — requires data acquisition, not algorithmic complexity.  
**Validation:** Rule-level return delta; engine-level all-passed vs. some-failed gap.  
**Failure modes:** Sector classification can be stale or noisy; must use a stable source.

### Candidate C4 — Capital Rotation / Style Momentum
**Behaviour:** Sector/style capital rotation.  
**Measurement:** Momentum score of a sector/style basket vs. the market. Use sector proxies built from the existing universe (once sector data exists) or style proxies (market-cap quintiles).  
**Algorithm:**
```
for each sector, compute equal-weight 63d return
sector_momentum_score = z-score of sector's 63d return vs. all sectors
stock_score = stock's own RS rating * (1 + sector_momentum_score / 10)
```
**Required data:** Sector classification and historical constituents.  
**Expected predictive value:** Moderate; improves selection when sector themes are strong.  
**Interaction:** Multiplicative or additive interaction with RS engine.  
**Complexity:** Medium.  
**Validation:** Regime-conditional analysis; compare returns when sector momentum aligns vs. conflicts.  
**Failure modes:** Style momentum can reverse sharply; must be used as a tilt, not a hard gate.

### Candidate C5 — Risk-Adjusted Momentum (Momentum per Unit Volatility)
**Behaviour:** High return per unit of realised risk.  
**Measurement:** Trailing 63d return divided by trailing 20d ADR%.  
**Algorithm:**
```
ret_63 = close / close[-63] - 1
adr_20 = mean(high/low - 1 over last 20) * 100
risk_adj_momentum = ret_63 / max(adr_20, 0.01)
score = clamp((risk_adj_momentum - median) / (90th percentile - median), 0, 1)
```
**Required data:** OHLCV (already available).  
**Expected predictive value:** Positive for risk-adjusted returns; may reduce drawdowns.  
**Interaction:** Replaces or augments `risk_atr` and `mq_acceleration`.  
**Complexity:** Low.  
**Validation:** Compare Sharpe/Sortino of top-quartile vs. bottom-quartile selections.  
**Failure modes:** Low-volatility stocks with tiny positive returns can score high; must be combined with absolute momentum filters.

### Candidate C6 — Crowding Proxy (Volume-to-Market-Cap Anomaly)
**Behaviour:** Avoid over-crowded names.  
**Measurement:** Recent turnover velocity vs. historical average, or volume spikes not explained by price moves.  
**Algorithm:**
```
# Simple proxy: 20-day turnover as % of average 6-month turnover, conditioned on recent return
recent_turnover = sum(volume * close over last 20d)
hist_turnover = mean(daily turnover over last 126d) * 20
turnover_ratio = recent_turnover / hist_turnover
crowding_score = clamp((turnover_ratio - 1.5) / 2.0, 0, 1)  # high ratio = crowded
```
**Required data:** OHLCV (already available); market cap would improve it but is not required for a first proxy.  
**Expected predictive value:** Negative — high crowding predicts lower forward returns or higher drawdowns.  
**Interaction:** Penalty in risk engine.  
**Complexity:** Low.  
**Validation:** Compare forward returns and drawdowns of high-crowding vs. low-crowding qualified stocks.  
**Failure modes:** Breakout volume will also raise turnover; must distinguish "breakout volume" from "exhaustion volume" by context (e.g., extension level).

### Candidate C7 — Breadth Participation Filter
**Behaviour:** Market advance is broad, not narrow.  
**Measurement:** Percentage of the qualified universe making new 20-day highs, or advance-decline ratio of the universe.  
**Algorithm:**
```
new_highs = count(securities where close == high_20d) / count(securities)
breadth_score = new_highs
# Use as a market-regime input, not a stock-level gate
```
**Required data:** OHLCV for the full universe (already available).  
**Expected predictive value:** Positive when high; negative when very low (correction risk).  
**Interaction:** Regime-conditional adjustment to position sizing or gate strictness.  
**Complexity:** Low.  
**Validation:** Compare strategy returns in high-breadth vs. low-breadth months.  
**Failure modes:** A few strong leaders can still outperform in narrow markets; a breadth filter may increase false negatives.

### Candidate C8 — Breakout Retest / Failure Test
**Behaviour:** Confirm that a breakout level has become support.  
**Measurement:** After price enters the top 30% of the 20-day range, count sessions where the low stays above the 20-day high (the breakout level).  
**Algorithm:**
```
recent_high_20 = max(high[-20:])
if close[-1] > recent_high_20 * 0.98:  # near breakout
    retest_sessions = count(low[-5:] > recent_high_20)
    retest_score = retest_sessions / 5
else:
    retest_score = 0
```
**Required data:** OHLCV (already available).  
**Expected predictive value:** Positive for avoiding false breakouts.  
**Interaction:** Replaces or augments `bo_false_breakout`.  
**Complexity:** Low.  
**Validation:** Compare forward returns of stocks with retest confirmation vs. those without.  
**Failure modes:** Requires a few sessions after breakout; may exclude very fast movers that never retest.

### Candidate C9 — Cross-Sectional Extension Percentile Cap
**Behaviour:** Avoid late-stage, over-extended names.  
**Measurement:** Instead of a fixed 25% cap above SMA50, use the per-run percentile of extension among qualified stocks and exclude the top N%.  
**Algorithm:**
```
ext_pct = (close - sma50) / sma50 * 100
ext_percentile = percentile_rank(ext_pct within qualified set)
exclude if ext_percentile >= 85  # top 15% most extended
```
**Required data:** SMA50 and close (already available).  
**Expected predictive value:** Positive for reducing failure-tier drawdowns; may reduce raw return if it excludes some winners.  
**Interaction:** Replaces the static `risk_extension` gate with a dynamic, cross-sectional filter.  
**Complexity:** Low.  
**Validation:** Walk-forward with pre-registered threshold grid {70, 80, 85, 90, 95} percentile; measure precision, recall, failure rate, and Sharpe.  
**Failure modes:** In a strong trending market, the most extended names can keep running; a percentile cap may increase false negatives. This is exactly why RP-000 failed on a benign hold-out.

### Candidate C10 — Multi-Metric Exhaustion Score
**Behaviour:** Combine extension, acceleration, and streak length into a single late-stage exhaustion signal.  
**Measurement:** Weighted average of extension percentile, acceleration percentile, and consecutive qualifying months.  
**Algorithm:**
```
ext_score = percentile_rank((close - sma50) / sma50 * 100)
accel_score = percentile_rank(ret_20 - ret_63)
streak_score = min(consecutive_qualifying_months / 6, 1)
exhaustion_score = 0.5 * ext_score + 0.3 * accel_score + 0.2 * streak_score
exclude if exhaustion_score >= 0.80
```
**Required data:** Close, SMA50, historical RS/qualification status (already available).  
**Expected predictive value:** Stronger than any single metric because RP3 found all three point in the same direction.  
**Interaction:** Replaces `risk_extension` and `mq_acceleration` with a unified exhaustion signal.  
**Complexity:** Medium.  
**Validation:** Walk-forward; compare failure-rate reduction and return impact.  
**Failure modes:** More complex than C9; risk of overfitting if weights are tuned to the sample. Must pre-register weights.

### Candidate C11 — Slippage / Capacity Score
**Behaviour:** Ensure the stock is tradable.  
**Measurement:** Estimated daily value at risk from ADR% and average turnover, or simply a continuous liquidity score.  
**Algorithm:**
```
daily_turnover_inr = avg_volume50 * close
adr_pct = mean(high/low - 1 over 20) * 100
capacity_score = daily_turnover_inr / (adr_pct + 0.01)  # higher is better
score = clamp((capacity_score - p10) / (p90 - p10), 0, 1)
```
**Required data:** OHLCV (already available).  
**Expected predictive value:** Positive for net-of-cost returns; likely weak in small-account backtests but important for real capital.  
**Interaction:** Replaces the binary `vol_liquidity_min` with a continuous liquidity preference.  
**Complexity:** Low.  
**Validation:** Compare implementation-cost-adjusted returns.  
**Failure modes:** May simply replicate the existing liquidity gate; must be tested for marginal value.

---

## 6. Behaviour Prioritisation Matrix (Deliverable 6)

Candidates are ranked by: (1) behavioural importance from source literature, (2) strength of prior evidence, (3) feasibility with existing data, (4) expected interaction with current engines, (5) validation cost.

| Rank | Candidate | Behaviour | Importance | Evidence | Data Feasibility | Interaction | Validation Cost | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | C9 — Cross-sectional extension percentile cap | Momentum exhaustion | High | Strong (RP3) | High (existing data) | Replaces `risk_extension` | Low | **Highest-priority candidate for walk-forward validation** |
| 2 | C10 — Multi-metric exhaustion score | Momentum exhaustion | High | Strong (RP3) | High | Replaces `risk_extension` + `mq_acceleration` | Medium | Second-highest priority; more complex than C9 |
| 3 | C2 — Volume dry-up score | Base quality / breakout | High | Moderate (VCP literature) | High | Augments volume/breakout engines | Low | Strong candidate; low risk |
| 4 | C1 — Trend smoothness score | Trend quality | Medium | Weak (not yet tested) | High | Augments trend/momentum_quality | Low | Worth testing as tie-breaker |
| 5 | C8 — Breakout retest / failure test | Breakout quality | High | Moderate (technical literature) | High | Replaces `bo_false_breakout` | Low | Strong candidate; directly addresses false breakouts |
| 6 | C5 — Risk-adjusted momentum | Risk asymmetry | Medium | Moderate (academic) | High | Augments risk engine | Low | Worth testing; may reduce drawdowns |
| 7 | C3 — Sector/industry RS | Sector leadership | High | Strong (academic) | **Blocked** (no data) | Adds relative_strength rules | Medium | **Blocked on data acquisition** |
| 8 | C4 — Capital rotation | Style/sector momentum | Medium | Moderate | **Blocked** (no data) | Multiplicative RS tilt | Medium | **Blocked on data acquisition** |
| 9 | C7 — Breadth participation | Market confirmation | Medium | Moderate | High (full universe data) | Regime-conditional input | Low | Useful, but regime-conditional research is frozen |
| 10 | C6 — Crowding proxy | Positioning | Low-Moderate | Weak | High | Penalty in risk engine | Low | Exploratory; low priority |
| 11 | C11 — Slippage/capacity score | Liquidity | Low-Moderate | Weak | High | Replaces liquidity gate | Low | Operational, not alpha-generating |

### Prioritisation rationale

- **C9 and C10** are top priority because they build on the single strongest, most coherent finding from the prior research cycle (extension/acceleration/streak-length predicts failure). They use existing data and require only a strategy-config change.
- **C2 and C8** are next because they address well-documented behaviours (volume dry-up, breakout retest) with simple deterministic algorithms and existing data.
- **C1 and C5** are lower priority because the evidence for their incremental value is weaker, but they are cheap to test.
- **C3 and C4** are high behavioural importance but blocked by the sector/industry data gap.
- **C7** is feasible but regime-conditional, and the Research Program Director froze regime-conditional research pending more data.
- **C6 and C11** are exploratory and lower priority.

---

## 7. Research Roadmap (Deliverable 7)

### Immediate (next 1–2 research cycles, existing data only)
1. **Walk-forward validate C9 (cross-sectional extension percentile cap).**
   - Pre-register threshold grid: exclude top {10%, 15%, 20%, 25%, 30%} most extended.
   - Use a hold-out window distinct from the 81-run ICv2 dataset.
   - Acceptance criteria: statistically significant reduction in failure-tier rate or improvement in Sharpe/Sortino, with no material drop in winner capture.
2. **Walk-forward validate C10 (multi-metric exhaustion score).**
   - Pre-register weights (e.g., 0.5 extension, 0.3 acceleration, 0.2 streak).
   - Compare against C9 to determine whether the added complexity is justified.
3. **Test C2 (volume dry-up score) observationally.**
   - Compute within qualified set; compare forward returns of high dry-up vs. low dry-up.
   - If positive, design a walk-forward experiment.
4. **Test C8 (breakout retest) observationally.**
   - Compare forward returns of stocks that hold above the 20-day high for multiple sessions vs. those that do not.

### Medium-term (requires data acquisition or regime diversity)
5. **Acquire sector/industry classification data.**
   - Evaluate paid vendors or scrapable sources.
   - Once ingested, re-enable C3 (sector/industry RS) and validate.
6. **Acquire historical index constituents.**
   - Required for true survivorship-bias-free backtesting and for sector-basket construction.
7. **Revisit C4 (capital rotation) and C7 (breadth participation)** once sector data and more regime diversity are available.
   - These are regime-conditional by nature and cannot be validated on the current dataset.

### Long-term (structural)
8. **Investigate the ranking mechanism itself.**
   - The prior cycle found IC ≈ 0.028, weak and non-monotonic. If new characteristics do not fix this, consider whether the problem is the scoring formula's linear weighting or a fundamental limit on predictability from public, deterministic signals.
9. **Extend historical coverage beyond 2019-10-01.**
   - The NSE bhavcopy floor is the binding constraint on regime diversity. A paid vendor or the passage of time is required.

### What NOT to do
- Do not add new engines or rules without walk-forward validation.
- Do not tune weights or thresholds to the existing sample.
- Do not promote any candidate that fails pre-registered acceptance criteria on a hold-out window.

---

## 8. Engineering Specifications (Deliverable 8)

All candidates are designed to fit the existing ADR-005 strategy-as-config architecture. No new engine core is required for the top-priority candidates.

### C9 — Cross-Sectional Extension Percentile Cap
- **Implementation location:** New rule in `risk.py` or modification of `risk_extension` to accept a `percentile_cap` parameter.
- **Config change:** Add a new rule `risk_extension_pct` to the `risk` engine, or extend `risk_extension` params with `use_percentile: true` and `max_percentile: 85`.
- **Computation:** After all securities in the qualified set are scored, compute the percentile of `ext_pct` and fail the rule for the top N%.
- **Determinism:** Percentile is computed over the same qualified set every run; reproducible.
- **Persistence:** New rule result rows in `rule_results`; no schema change.
- **Tests:** Unit test for percentile computation; golden test for deterministic rank order.

### C10 — Multi-Metric Exhaustion Score
- **Implementation location:** New rule in `risk.py` or new engine `exhaustion`.
- **Config change:** Add an `exhaustion` engine with one rule combining extension, acceleration, and streak length.
- **Computation:** Requires historical qualification status (consecutive qualifying months). This is not currently persisted per security; would require a new query or a derived field from `screening_results` history.
- **Determinism:** All inputs are deterministic; streak length is computed from persisted historical runs.
- **Persistence:** May require adding a `qualification_streak` field to the indicator context or computing it in the orchestrator.
- **Tests:** Unit test for exhaustion score; integration test for streak computation.

### C2 — Volume Dry-Up Score
- **Implementation location:** New rule in `volume_accumulation.py`.
- **Config change:** Add `vol_dry_up` rule with params `short_window: 5`, `long_window: 25`.
- **Computation:** `1 - mean(volume[-5:]) / mean(volume[-25:])`, clamped.
- **Determinism:** Pure OHLCV math.
- **Persistence:** New rule result rows.
- **Tests:** Unit test for dry-up ratio.

### C8 — Breakout Retest / Failure Test
- **Implementation location:** New rule in `breakout.py`.
- **Config change:** Add `bo_retest` rule with params `lookback: 20`, `hold_sessions: 5`.
- **Computation:** Count sessions in the last N where low > 20-day high.
- **Determinism:** Pure OHLCV math.
- **Persistence:** New rule result rows.
- **Tests:** Unit test for retest count.

### C1, C5, C6, C7, C11
- All can be implemented as new rules within existing engines (trend_template, momentum_quality, risk, volume_accumulation) or as new standalone engines.
- No schema changes required beyond new `rule_results` rows.
- All use existing `IndicatorSet` fields or simple OHLCV series computations.

### C3, C4
- **Blocked on data:** Require sector/industry classification and historical constituents.
- **Implementation location:** `relative_strength.py` (re-enable dead rules) and new `rotation` engine.
- **Schema impact:** May require new `sectors` table or extension of `securities` metadata.

---

## 9. Expected Stock Selection Improvement (Deliverable 9)

### What can realistically be improved
The prior research cycle established that the *gate* (Trend Template + liquidity) is effective, but the *ranking* within the qualified pool is weak. The candidates in this report are not expected to fix the ranking inversion directly. Instead, they are expected to:

1. **Reduce the failure rate** among selected stocks by excluding late-stage, over-extended names (C9, C10).
2. **Improve breakout quality** by requiring volume dry-up and retest confirmation (C2, C8).
3. **Add defensive characteristics** that may improve risk-adjusted returns (C5, C11).
4. **Unlock new alpha** once sector/industry data is available (C3, C4).

### Quantitative expectations (calibrated, not promised)
Based on the prior cycle's evidence:
- **C9:** A well-calibrated percentile cap could reduce the failure-tier rate from ~13.9% to ~10–11% if the top 15% most extended names are excluded. The impact on raw return is uncertain — RP-000 found no North Star improvement on a benign hold-out, but the mechanism should matter more in correction regimes.
- **C10:** Could be 10–20% more effective than C9 at identifying exhaustion because it combines three corroborated signals. However, added complexity increases overfitting risk.
- **C2 / C8:** Individually likely small effects (+1–2pp forward return within the subset where they apply). Combined, they may improve the consistency of breakout entries.
- **C5:** Likely improves Sharpe/Sortino more than raw return by reducing volatility of selected names.
- **C3 / C4:** Potentially the largest impact once data is available. Moskowitz & Grinblatt found industry momentum explains roughly half of individual momentum profits.

### What is unlikely to improve
- **Linear re-composition of existing rules:** Exhausted by RP-000 through RP-003.
- **Adding more pattern detectors without validation:** Pattern engine already shows mixed evidence.
- **Regime-conditional filters:** Cannot be validated until more regime diversity is available.

### Honest conclusion
The expected improvement from the top-priority candidates (C9, C10) is **modest and conditional**. The largest gains are likely behind a data-acquisition wall (sector/industry classification, longer history). The platform should pursue the low-cost, high-evidence candidates now while waiting for the data conditions that unlock the larger opportunities.

---

## 10. Executive Recommendation (Deliverable 10, restated)

**Do not promote any production change today.** The platform is safe, deterministic, and its current methodology is well-understood. The ranking-improvement freeze should remain in place.

**Do pursue the following research actions immediately:**
1. Walk-forward validate **C9 (cross-sectional extension percentile cap)** on a hold-out window that includes the 2022 correction and the matured 2026-H1 window.
2. If C9 shows promise, compare it against **C10 (multi-metric exhaustion score)** to decide whether added complexity is justified.
3. Observationally test **C2 (volume dry-up)** and **C8 (breakout retest)** within the qualified set.

**Do treat the following as blocked until data conditions change:**
- Sector/industry leadership (C3, C4) — blocked on classification data.
- Regime-conditional breadth/filters (C7) — blocked on more regime diversity.
- Any ranking-quality breakthrough — blocked on the 2026-H1 forward window maturing and/or a second correction-era stratum.

**Final conclusion:** Momentum25 already captures the core behaviours that world-class momentum investors exploit: trend quality, relative strength, breakout quality, and liquidity. The next tier of improvement lies in (a) better measuring late-stage exhaustion, (b) better measuring volume-behaviour nuance around breakouts, and (c) acquiring the sector/industry data required for leadership confirmation. These are deterministic, explainable, and reproducible extensions — but they require validation before any promotion.

---

## References

- Asness, C. (1994). "The Power of Past Returns." *Journal of Portfolio Management.*
- Asness, C. (1997). "The Interaction of Value and Momentum Strategies."
- Asness, C., et al. (2013). "The Devil in HML's Details." *Journal of Portfolio Management.*
- Baltas, A.-N., & Kosowski, R. (2013). "Momentum Strategies in Futures Markets and Trend-Following Funds."
- Bhojraj, S., & Swaminathan, B. (2006). "Macromomentum: Returns Predictability in International Equity Indices."
- Blitz, D., & van Vliet, P. (2008). "Global Tactical Cross-Asset Allocation."
- Carhart, M. (1997). "On Persistence in Mutual Fund Performance." *Journal of Finance.*
- Daniel, K., & Moskowitz, T. (2016). "Momentum Crashes." *Journal of Financial Economics.*
- Daniel, K., Hirshleifer, D., & Subrahmanyam, A. (1998). "Investor Psychology and Security Market Under- and Overreactions." *Journal of Finance.*
- Frazzini, A., Israel, R., & Moskowitz, T. (2018). "Trading Costs of Asset Pricing Anomalies."
- Greenwood, R., & Hanson, S. (2015). "Waves in Ship Prices and Investment."
- Hong, H., & Stein, J. (1999). "A Unified Theory of Underreaction, Momentum Trading, and Overreaction in Asset Markets." *Journal of Finance.*
- Jegadeesh, N., & Titman, S. (1993). "Returns to Buying Winners and Selling Losers." *Journal of Finance.*
- Korajczyk, R., & Sadka, R. (2004). "Are Momentum Profits Robust to Trading Costs?" *Journal of Finance.*
- Lemperiere, Y., et al. (2014). "Two Centuries of Trend Following."
- McClellan, T. (1999). "The McClellan Oscillator."
- Minervini, M. (2013). *Trade Like a Stock Market Wizard.*
- Minervini, M. (2016). *Think & Trade Like a Champion.*
- Moskowitz, T., & Grinblatt, M. (1999). "Do Industries Explain Momentum?" *Journal of Finance.*
- O'Neil, W. (1988). *How to Make Money in Stocks.*
- Stein, J. (2009). "Presidential Address: Sophisticated Investors and Bubbles."
- Zweig, M. (1986). *Winning on Wall Street.*
