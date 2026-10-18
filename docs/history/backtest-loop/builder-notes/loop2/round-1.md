# Builder Notes — Loop 2, Round 1

Scope: `brief-addendum-loop2.md` (walk-forward engine + historical data). Frozen
`domain/backtest/` untouched. This is a proposal, not a PASS — Reviewer disposes.

## 1. NSE reachability finding (checked FIRST, per the addendum)

**Result: NSE archive hosts are reachable; the interactive site is not.** This
environment is NOT on a restrictive allowlist that blocks NSE. Actual commands
and observed HTTP codes:

| Target | Command | Result |
|---|---|---|
| `www.nseindia.com` (site root) | `curl -A Mozilla https://www.nseindia.com` | **HTTP 403** (anti-automation on the interactive site) |
| `archives.nseindia.com` legacy bhavcopy | `curl .../content/historical/EQUITIES/2023/JAN/cm02JAN2023bhav.csv.zip` | **HTTP 200, 89 KB**, unzipped to a real 2384-row EOD CSV (`SYMBOL,SERIES,OPEN,...,ISIN`) |
| `nsearchives.nseindia.com` UDiFF bhavcopy | `curl .../content/cm/BhavCopy_NSE_CM_0_0_0_20240702_F_0000.csv.zip` | **HTTP 200, 164 KB** |
| current Nifty 500 constituent list | `curl .../content/indices/ind_nifty500list.csv` | **HTTP 200, 32 KB**, real header `Company Name,Industry,Symbol,Series,ISIN Code` |
| `niftyindices.com` constituent file | `curl .../IndexConstituent/ind_nifty500list.csv` | HTTP 200 |
| generic control (`google.com`) | — | HTTP 200 |

So: raw daily OHLC (back to 1994 via legacy archive), UDiFF ISINs, corporate
actions, and the *current* constituent list are all fetchable. Reachability is
NOT the blocker.

**The real, data-availability blocker (a scope-limiting discovery, per addendum
§0):** two inputs this loop needs most are not published by NSE as historical,
point-in-time time series:

- **Point-in-time Nifty 500 membership.** NSE publishes only *today's*
  constituent list (`ind_nifty500list.csv`). There is no free NSE endpoint that
  returns "the Nifty 500 as of 2021-04-01". Applying today's list backward is
  exactly the survivorship bias `brief.md` §9 / checklist item 8 forbid.
- **Historical ASM/GSM/T2T surveillance.** NSE publishes the *current*
  surveillance lists only; historical daily snapshots are not archived freely.
  This is the same gap Loop 1 flagged in `eligibility.py`.

Both need a human decision: a licensed vendor (point-in-time index membership +
surveillance history) or a manual dated-snapshot drop. I did not fabricate
either — consistent with `eligibility.py`'s existing "never default-assume clean
status silently" contract.

## 2. Ladder check — what already exists (reused, not rebuilt)

The repo already has a production market-data pipeline. I did **not** rebuild it:

- Adjusted-close prices: `infrastructure/persistence/repositories/ohlcv.py`
  (`get_series(..., as_of)`), `domain/entities/market_data.py::compute_adjustment_factors`.
- Bhavcopy fetch incl. legacy-archive routing to 1994 and UDiFF: `infrastructure/providers/bhavcopy.py`.
- Corporate actions (ratio parsing): same provider + `repositories/corporate_actions.py`.
- Benchmark index: `repositories/benchmark_index.py`.
- Trading calendar: `infrastructure/calendar/nse_calendar.py`.

Per addendum §1 the price/corp-action/benchmark providers of §1 substantially
already exist; the genuinely missing seam was the **walk-forward runner** and the
**as-of-enforcing ports** it drives. That is what I built.

## 3. What changed (built this round)

- **`domain/ports/walk_forward.py`** (new) — three driven ports, each carrying an
  explicit `as_of` decision date:
  - `PriceHistoryProvider.price_on_or_before(security_id, target, as_of)` →
    `PricePoint(security_id, session_date, adj_close)`. Returns the session date
    so look-ahead is *detectable*, not just documented.
  - `EligibilityFactsProvider.facts_as_of(decision_date)` → point-in-time
    `EligibilityFacts` (the survivorship-critical port; real impl blocked on §1).
  - `BenchmarkProvider.level_on_or_before(target, as_of)` — reporting only.

- **`application/use_cases/walk_forward.py`** (new) — `WalkForwardRunner`, wired
  to the frozen domain modules (`is_eligible`, `compute_momentum_signal`,
  `rank_signals`, `select_portfolio`, `plan_equal_weight_rebalance`) with zero
  changes to them. Properties enforced in code, not just intent:
  - **Fill timing (brief §5):** decision date = the session immediately before
    the rebalance date; fill date = the first session of the month. Fill date is
    a strictly later date than the decision date — never same-day.
  - **Look-ahead enforcement (brief §9):** `_price()` re-checks every returned
    `session_date <= as_of` and raises `LookAheadError` on a leak. The runner does
    NOT trust the provider to obey `as_of`.
  - **Fail-closed scoring:** a security missing any of its 4 required prices is
    dropped, never scored on a forward-filled or defaulted value.
  - **Independent equity reconstruction (addendum §3, item 14):** the reported
    `total_return` comes from `_reconstruct_nav_from_trades()`, which replays only
    the trade log + prices and ignores any NAV the loop tracked.
  - Fill-price approximation flagged with a `ponytail:` comment: uses adjusted
    *close* on the fill date (the adjusted series has no open); the date is still
    strictly post-decision, so no look-ahead. A held name unpriceable at
    rebalance is marked to zero (conservative, look-ahead-free) — also flagged.

- **`tests/unit/test_walk_forward.py`** (new) — 7 deterministic tests, in-memory
  fakes only. These make Reviewer checklist items runnable per addendum §4:
  item 7 (leaky provider → `LookAheadError`), item 8 (point-in-time universe:
  a name is scored while in-index, absent once it leaves), item 10 (fill date >
  decision date on every trade), item 13 (as-of price call fires on the real run
  path with `as_of == decision_date`, via a spy), item 14 (independent NAV
  replay equals the engine's reported `final_nav`), plus determinism (same inputs
  → identical outputs).

## 4. Completed vs. explicitly scoped out

Completed: addendum §2 (walk-forward runner) and §3 (per-rebalance log, trade
log, trade-log-reconstructed summary) as data structures + logic, wired to the
frozen domain, with the §4 falsification tests runnable against fakes.

Scoped out this round, with reason (NOT a silent skip):
- **Real point-in-time membership + historical surveillance providers** —
  blocked on data availability (§1). Ports defined; real impls need a vendor or a
  human-provided dated dataset. This is the item to escalate for a human.
- **Real DB/NSE-backed adapter for the new ports + a live historical run** — a
  full walk-forward over real data cannot be *correct* without point-in-time
  membership, so building an adapter that silently uses today's list would bake
  in survivorship bias. Deferred rather than done wrong. Price/benchmark real
  impls already exist and can wrap into these ports once membership is resolved.
- **Benchmark TRI vs price index:** brief §8 wants Nifty 500 **TRI**; the
  existing `fetch_benchmark` (nsemine) returns the price index. TRI is a separate
  source (niftyindices.com). Flagged; not resolved this round.

## 5. Validation run

- `ruff check` new files — All checks passed.
- `mypy src/.../walk_forward.py` (port + use case) — Success, no issues.
- `pytest tests/unit/test_walk_forward.py` — 7 passed.
- `pytest tests/unit` (full suite, regression check) — **516 passed**.

## 6. Commit

`loop: round 1 (builder)` — hash recorded on commit (see git log; this note is
part of that commit).
