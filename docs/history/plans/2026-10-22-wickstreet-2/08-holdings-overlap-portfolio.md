# 08 — Holdings, Overlap, Look-Through and Portfolio Intelligence

> Part of the [Wickstreet 2.0 blueprint](README.md). Status: Proposed. Governing decisions: ADR-017 (holdings point in time), ADR-019 (portfolio and look-through). All formulas are methodology and need owner approval.

## 1. Holdings intelligence (per fund)

Input: the scheme's **visible disclosure** at `as_of` = greatest `published_at ≤ as_of` (ADR-017). Every view names the `portfolio_date` and its age ("Portfolio as of 30 Sep 2026, published 9 Oct 2026, 13 days old").

| View | Definition |
|---|---|
| Asset mix | Σ `pct_of_nav` by `asset_type`; residual to 100% shown as "unreported" |
| Top holdings | Equity lines sorted by `pct_of_nav`, tie-break ISIN |
| Sector / industry | Equity lines grouped by **our** classification of the resolved security at `as_of`. Lines we cannot resolve fall back to the AMC's `industry_as_reported`, marked "AMC label". Two taxonomies are never mixed silently. |
| Market-cap split | Equity lines grouped by the AMFI bucket in force at the portfolio date; foreign and unlisted equity as separate buckets |
| Concentration | `top10_wt`; effective number of holdings `eff_holdings = 1 ÷ Σ wᵢ²` on equity weights rescaled to sum to 1 |
| Changes | Compared with the scheme's previous disclosure: **new** (ISIN absent before), **exited**, **increased**/**reduced** (by quantity, not weight, so price moves do not look like trades; corporate actions between the two dates scale the old quantity first) |
| Resolution report | Count and weight of lines whose ISIN did not resolve to a security or fund plan |

## 2. Fund → stock look-through journey

The signature journey: **Discover fund → Holdings → select stock → Chart → Momentum25 → back to fund → Compare.**

| Step | Screen | Context carried |
|---|---|---|
| 1 | Fund screener row → `/fund/120503` | `from=/?tab=funds&screen=…` |
| 2 | Holdings tab → click a holding | `/stock/ABC?from=/fund/120503%3Ftab%3Dholdings%26disclosure%3D88` |
| 3 | Company page shows a **context bar**: "Viewing ABC from *Fund X* (4.2% of NAV, portfolio 30 Sep 2026) ← Back to Fund X" | The fund, the disclosure id, the weight |
| 4 | Chart tab or Alt+C → `/chart/ABC?from=…` | Same `from`; chart adds a marker band for the disclosure dates when this fund held the stock (optional overlay "Held by Fund X") |
| 5 | Momentum25 tab: existing Assessment panel | — |
| 6 | Back → the fund's holdings tab, same disclosure, same scroll row | Restored from `from` |
| 7 | "Compare with…" → `/compare/funds?plans=120503,…` | The fund pinned |

**Historical context.** With `as_of` set (replay or a historical screen), step 2 shows the disclosure visible at that date, never today's. A stock held today but not then shows "not in the portfolio visible on 12 Mar 2022".

**Reverse journey.** On any company page, "Held by N funds" opens `/stock/ABC/held-by`: funds whose visible disclosure holds the stock, weight, change since previous disclosure, scheme AUM × weight = approximate rupee holding, sorted by weight. This uses the `(security_id, disclosure_id)` index.

## 3. Overlap

For two schemes A and B, each at its visible disclosure:

- **Weight overlap** = Σ over common securities of min(w_A,s, w_B,s), with w on total NAV (not rescaled), in %. This is the convention used by common Indian overlap tools.
- **Common holdings** = count of securities held by both, and that count ÷ the smaller fund's number of equity holdings.
- **Matrix** for up to 5 funds: weight overlap for each pair.
- **Guards:** the disclosure dates are shown in the header. If they differ by more than 31 days, a warning says the comparison mixes dates. Securities match on resolved `security_id`, falling back to ISIN; an unresolved line never matches by name.
- **Words, not numbers only:** "Fund A and Fund B hold 23 of the same stocks. Those make up 41% of Fund A's money." Bands for the summary line: < 20% low, 20–50% moderate, > 50% high. The bands are editorial and labelled so.

## 4. Portfolio intelligence

### 4.1 Holdings intake

| Route | Detail |
|---|---|
| Manual | Add a transaction or an **opening balance** (instrument, units, average cost, date) |
| CSV | `transactions-v1` contract ([04 §7](04-data-sources.md#7-import-contracts-source-neutral)); a preview shows parsed rows, resolved instruments and errors before commit |
| CAS | Local parse of the user's CAS PDF with the password typed once and held in memory only (§6). Folio transactions become `fund_plan` transactions |
| Broker export | One adapter per broker tradebook/holdings CSV layout, mapped into `transactions-v1` |

Every import is one `import_batch_id`. "Undo import" deletes that batch only. Instrument resolution: ISIN first, then exchange symbol, then AMFI plan code. Unresolved rows are rejected with a reason; nothing is guessed by name.

### 4.2 Derivation

- **Lots** by FIFO per instrument. Sells consume the oldest lots. A sell larger than the open quantity is rejected at import.
- **Corporate actions** on equities after the trade date scale lot quantity and unit cost (split, bonus), from `corporate_actions`. Total cost never changes.
- **Valuation at date D:** equity = quantity × traded close at D; ETF = same; fund plan = units × NAV at D (latest NAV on or before D, with its date shown when older than D).
- **Cash** is an explicit instrument when the user records it. Wickstreet does not infer cash.

### 4.3 Returns

| Measure | Definition |
|---|---|
| Absolute return | (current value + realised proceeds + income − total invested) ÷ total invested |
| CAGR | Only for a single lump-sum position: (value ÷ cost)^(365 ÷ days) − 1 |
| XIRR | Rate *r* solving Σ CFᵢ ÷ (1 + r)^((dᵢ − d₀) ÷ 365) = 0, with buys negative, sells, income and the terminal value positive |
| Benchmark XIRR | The same cash flows invested in the benchmark TRI; the difference is shown |

**XIRR solver.** Bracketed bisection on r ∈ (−0.9999, 10) to |NPV| < ₹0.01 or 200 iterations, then reported to 2 dp. Bisection is slower than Newton but has no starting-point dependence, so the result is deterministic. No sign change in the bracket → `NM (no unique rate)`. Holding period < 365 days → XIRR shown with the note "annualised from N days".

### 4.4 Allocation and exposure

| View | Rule |
|---|---|
| Asset class | Equity (direct), ETF, mutual fund by SEBI asset class, cash |
| Look-through exposure | §5 |
| Sector, market cap | Computed on look-through exposure, so a stock held directly and via two funds counts once in total |
| Concentration | Top-10 look-through securities and their share; effective number of holdings on the look-through equity sleeve |
| Overlap | Pairwise fund overlap (§3) for every pair of held funds; plus "stocks you hold directly that your funds also hold" |
| Drawdown | Daily portfolio value series from transactions; max drawdown computed on a cash-flow-neutral index (time-weighted daily returns), never on raw value, because deposits look like gains |
| Drift and rebalancing | Against an optional `target_allocation` (asset class or instrument level): current weight − target weight; the trades in ₹ that would restore target, ignoring tax and loads, with that limitation stated |

## 5. Look-through without double counting

For valuation date D:

```text
exposure(s) = direct_value(s)
            + Σ_f value(f) × w(f, s)            for each fund or ETF f held
            + Σ_f Σ_g value(f) × w(f, g) × w(g, s)   one more level for fund units g held by f (FoF, ETF inside a fund)
```

- w(f, s) comes from f's disclosure visible at D (published ≤ D). If none is visible, f's whole value goes to "Fund X — holdings not available".
- Recursion stops after two levels. A cycle (f holds g holds f) is cut at the repeat and reported.
- A fund-unit line inside f (w(f, g)) is **replaced** by g's holdings, never counted as both a unit and its contents.
- Non-equity lines (debt, cash, derivatives, REIT/InvIT) stay as named buckets.
- The residual Σ (1 − Σ reported weights) is the **"unreported"** bucket.
- **Invariant (tested):** Σ exposure over all securities and buckets = total portfolio value, to the paisa. A property-based test checks it on random portfolios and disclosures.
- Exposure uses disclosure weights × today's fund value. Weights drift with prices between disclosures. The screen says so: "Based on portfolios published up to 9 Oct 2026; actual weights move daily."

## 6. Privacy and security

- Portfolio tables live in the local database only. No endpoint sends holdings anywhere.
- CAS passwords: accepted in the request body over loopback, used once, never logged (a log filter test checks the field name), never stored.
- Uploaded files are parsed in memory and discarded; only the derived transactions and the file hash are stored.
- Backups include portfolio tables; `operations/backup.md` gets a line saying so.

## 7. Tests

| Test | Checks |
|---|---|
| FIFO and corporate actions | Golden ledger through a 1:2 split and a 1:1 bonus; cost basis unchanged |
| XIRR | Known cash-flow sets with published answers (including spreadsheet XIRR parity to 1e-6); no-sign-change → NM |
| Look-through invariant | Property test: exposure sums to value; no double counting of FoF units |
| PIT holdings | A disclosure published after D is invisible at D; before the first disclosure exposure is `NA` |
| Overlap | Symmetric; equals Σ min weights; unresolved lines never match |
| Import | Preview/commit/undo per batch; rejected rows reported; no guessing by name |
| Privacy | Password never in logs or DB; no outbound call (network-disabled test run) |
| E2E | Import CSV → allocation → overlap → click stock → chart → back to portfolio keeps tab and filters |
