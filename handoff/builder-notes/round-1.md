# Builder Notes — Round 1 (Approximations Loop)

Round 1 of the loop opened by `brief-addendum-approximations.md` (and its
Postgres-data follow-up). No `reviewer-findings/round-0.md` exists for this
loop — this round implements what the addendum asks for, verified against
real data first per its own instruction ("check before assuming the
approximation applies").

## What I checked before writing any code

Queried the real `momentum25` Postgres instance (`momentum25-db-1`,
`M25_DATABASE_URL`), per the addendum's pointer, before deciding whether the
documented approximations still apply:

- `ohlcv_daily.adj_close`: 2,651,179 / 3,076,892 rows populated (86%). Real,
  usable adjusted-close history. **Closes the price-data gap.**
- `benchmark_index_daily` (`NIFTY500`): 2,858 rows, 2015-01-01 → 2026-08-07.
  Levels (6786.10 on 2015-01-01, 23712.10 on 2026-08-07) match the publicly
  known Nifty 500 **price** index range for this period — a TRI series would
  print materially higher over an 11-year span from compounded dividends. No
  TRI series exists anywhere in this database to diff against row-for-row, so
  this is a magnitude/plausibility check, stated as such, not a full
  reconciliation. **Confirms the "Price Index (not TRI)" label still applies
  — does not disprove it.**
- `securities.delisting_date`: **0 of 3,235 rows populated.** The addendum's
  framing ("securities has delisting_date... usable to test survivorship
  handling") does not hold up against the actual data — there is no delisted
  ticker in this table to test against. `survivorship_gap_event` (9,902 rows)
  has real trading-gap data but that's a proxy for suspension/inactivity, not
  a delisting flag, and nothing in the frozen `EligibilityFacts` dataclass
  has a slot for it.
- `universe_membership` (438,901 rows) / `historical_universe` (0 rows,
  unpopulated): `universe_membership.reason` values are
  `below_liquidity_floor`, `close_below_floor`, `insufficient_history`,
  `no_bar_on_trading_date`, `not_yet_listed`, `stale_data` — a **different
  production strategy's** screening gates (liquidity/history), not Nifty 500
  index constituency or ASM/T2T surveillance status. Backfilling
  `historical_universe` from this table would misrepresent "Nifty 500
  constituent" as "passed some other strategy's liquidity filter" — a
  fabrication, not an approximation.
- Grepped the full codebase for any Nifty 500 constituent list or ASM/GSM/T2T
  data, current or historical: **none exists anywhere** — not a table, not a
  column, not an ingestion adapter. This is a stronger statement than
  `brief-addendum-approximations.md`'s framing assumed (it describes an
  already-built "current list applied retroactively" provider to confirm;
  Loop 2 built no such provider — the port was left entirely unimplemented,
  which its Reviewer round-2 accepted as a carried-forward judgment call).

## What I built

`backend/src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py`:

- **`SqlPriceHistoryProvider`** — real `PriceHistoryProvider` backed by
  `ohlcv_daily.adj_close`. `load()` (async) pulls the full date range in one
  query at construction; `price_on_or_before()` (sync, per the port's
  contract) answers via bisect over an in-memory, per-security sorted series.
  One query instead of one round trip per (security, date) — a rebalance
  needs 4 prices × every eligible security. Rows with `adj_close IS NULL`
  (14% of the table) are excluded at load time — fail closed, same policy the
  runner already applies to a missing price, never fall back to unadjusted
  `close`.
- **`SqlBenchmarkProvider`** — real `BenchmarkProvider` backed by
  `benchmark_index_daily`. Same load-once/bisect pattern. Carries a `.label`
  attribute (`BENCHMARK_LABEL = "Nifty 500 Price Index (not TRI)"`).
- **`WalkForwardResult.benchmark_label`** (new field, `application/use_cases/walk_forward.py`) —
  threaded from `getattr(self._benchmark, "label", None)` so the label
  travels with `benchmark_return` wherever the result is consumed, per the
  addendum's "must appear next to the number itself" requirement. The
  `BenchmarkProvider` Protocol itself is untouched (duck-typed via
  `getattr`), so the existing in-memory test fakes in `test_walk_forward.py`
  need no changes and stay valid.

Verified both providers end-to-end against the **real** `momentum25` database
(not just the test DB) in a throwaway script: `SqlPriceHistoryProvider`
returned a real adjusted close for a real security/date; `SqlBenchmarkProvider`
returned a real NIFTY500 level with the price-index label attached.

`EligibilityFactsProvider` has **no adapter**. Per the reasoning above, no
data source exists — current or historical — for Nifty 500 constituency or
T2T/ASM status, so `in_nifty_500`/`is_t2t`/`is_under_surveillance` cannot be
populated truthfully. Setting `in_nifty_500=True` for every actively-traded
security in `ohlcv_daily` would silently redefine the universe from "Nifty
500 constituents" to "everything this ingestion pipeline tracks" — a brief
violation risk, not an approximation the addendum licensed. This is the same
gap loop-2's Reviewer accepted as a judgment call in round-1/round-2
(`handoff/reviewer-findings/loop2/round-2.md`), carried forward unchanged,
now with the sharper, verified statement above rather than "not yet
point-in-time."

## Tests

- `backend/tests/integration/test_walk_forward_market_data_providers.py`
  (new, 4 tests, against the real `_test` Postgres DB via the `db_session`
  fixture): latest-close-on-or-before lookup, as-of horizon winning over a
  later `target` (checklist item 7's mechanism, exercised against a real SQL
  load this time, not a fake), null-`adj_close` exclusion, benchmark label
  presence.
- `pytest tests/unit -q` → 516 passed (unchanged count — no unit tests
  touched; `test_walk_forward.py`'s fakes are untouched and still exercise
  the runner in isolation).
- `pytest tests/integration/test_walk_forward_market_data_providers.py
  tests/unit/test_walk_forward.py -q` → 11 passed.
- `ruff check` / `mypy` on both new/changed source files → clean.

## Findings addressed

No `round-0.md` findings exist for this loop — this is the initial
implementation per `brief-addendum-approximations.md` and its Postgres
follow-up.

## Commit

`c5966da` — `loop: round 1 (builder) — real Postgres-backed price/benchmark providers`
(3 files changed: `walk_forward_market_data.py` new,
`test_walk_forward_market_data_providers.py` new,
`walk_forward.py` +`benchmark_label` field).
