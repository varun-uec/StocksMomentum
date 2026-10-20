# Brief Addendum — Execution Method v2 (R3-B-09)

Approved by the owner on 2026-10-20 (Stage A, questions S-1 to S-3 and B09-1 to B09-8; see `audit-evidence/audit-r3/STAGE_A_FINANCIAL_METHODOLOGY_SPEC.md`). It extends `brief.md` and its three addenda. Signal (§2), ranking (§3), equal weight (§4), fill timing (§5), buffer (§6), costs (§7) and the benchmark (§8) are unchanged. This addendum fixes how a planned trade becomes a fill, and how the portfolio is valued and accounted. `BACKTEST_METHOD_VERSION = 2`.

## 1. Universe

The candidate set on a decision date D is the reference equity universe (`IMPLEMENTATION_SPEC.md` §8): `exchange` NSE or BOTH, an equity ISIN, listed by D and not delisted by D. §1's twelve-month rule then applies. Nifty 500 membership and T2T/ASM status are still stubs, labelled in every result.

## 2. Prices

Adjusted open and close are `raw × adj_factor` for every stored bar. A bar is a **valid execution bar** on session s when it is dated s, `open > 0`, `volume > 0` and `low ≤ open ≤ high`.

## 3. Signal (E1)

A security is scored on D only if it has a valid bar dated D. Lookback prices keep `brief.md` §2 and the documented rule: the last bar on or before the target date.

## 4. Orders

1. At the fill date F, each holding is marked at its adjusted open on F, or else at its last adjusted close on or before D (a stale mark).
2. Target value = NAV before trading / number of target names. A buy is a cash amount. A sell is a share count: all shares for an exit, `−Δ / mark` for a trim.
3. Sells run before buys, each in `security_id` order.
4. No leverage. If total buy cash × (1 + cost) exceeds available cash, every buy is scaled by one factor. A fill never takes cash below zero.

## 5. Execution (X1, L1)

- An order fills at the adjusted open of the first valid execution bar on or after F. No price from any other session is ever a fill price.
- **Liquidity cap (S-3):** a fill is at most 10% of that session's `turnover_value`. The rest waits as a pending order.
- **Buy window (S-1):** a buy may fill on F and the next 4 sessions (5 sessions in all). After that, the rest expires and its cash stays cash.
- **Sells** retry at every later session until filled.
- At the next F, every pending order is closed as `superseded` and the new plan issues fresh orders.
- **Settlement (S-2):** a sale's proceeds fund buys in the same session. This is a simplification, and every result says so.

## 6. Ledger

- Holdings change only through fills. Cash = initial − Σ(buy notional + cost) + Σ(sell notional − cost).
- Costs: 30 bps of each filled notional (§7), charged at the fill.
- Replaying the fill log reproduces holdings, cash and NAV exactly (Decimal) at every session.
- Quantities are in adjusted units: quantity × adjusted price is market value. A split or bonus needs no ledger event.
- Dividends are not modelled (no dividend amounts exist). The return is a price return, like the benchmark.

## 7. Valuation and end of window

- NAV(s) = cash + Σ quantity × the last adjusted close on or before s.
- A **non-trading holding** has no bar for more than 20 sessions. It stays held and marked at its last close; it is never sold at a stale price and never written off automatically (S-6). Every result reports the NAV share in non-trading holdings and a lower bound with those holdings at zero.
- A held security joined to a successor by a verified identity link carries over on the link's effective date: the successor receives shares × ratio, its live orders move with it (a sell's shares × ratio), and no cash or cost moves. The trade-log replay applies the same transfer before that session's fills. From the effective date, the successor's price history before its first bar is the predecessor's, price ÷ ratio. A security without a link is flagged "no verified identity link".
- At the end date, pending orders close as `open_at_end`. Holdings are valued, not liquidated.

## 8. What a result reports

`method_version`, the policy constants above, `market_data_version`, `build_id`, the universe label, the survivorship warning, and the following counts: orders, fills, partial fills, deferred fills, expired buys, superseded and open orders, unfilled notional, fills above 10% participation (always 0 under the cap), the non-trading holdings with their identity status, the zero-mark lower bound, CAGR and maximum drawdown.

**Market realism is not proven.** The data is end-of-day OHLCV only. The cap, the partial fills and the disclosures bound the error; they do not remove it.
