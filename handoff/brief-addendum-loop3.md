# Brief Addendum — Loop 3: Real Point-in-Time Membership, Surveillance & Delisting Data

This extends `brief.md`, `brief-addendum-loop2.md`, and
`brief-addendum-approximations.md`. It does not touch `domain/backtest/`,
`walk_forward.py`, `SqlPriceHistoryProvider`, or `SqlBenchmarkProvider` — all
verified and frozen across Loops 1–2 and the Approximations loop. This loop
replaces the two accepted-but-unresolved judgment calls (Item 13's
`EligibilityFactsProvider` stub, Item 8's survivorship data gap) with real
implementations, or ends in an honest "still not obtainable" verdict backed
by documented attempts — not a silent skip either way.

## Why this loop exists

Every prior loop correctly refused to fabricate this data. That was right —
but it means the current backtest is a documented approximation, not a real
answer. This loop's job is to go get the real data, so the two remaining
"accepted judgment calls" can either close for good or be replaced with a
sharper, evidence-backed statement of exactly what's obtainable and what
isn't.

## 0. Data sourcing is in scope for round 1 (same as Loop 2)

As with Loop 2, finding and fetching real data is part of round 1's work,
not a precondition someone else must satisfy first.

**Sources to check, roughly in order of expected cost/effort:**

1. **NSE historical index reconstitution files.** NSE periodically publishes
   which stocks were added to / removed from the Nifty 500 and on what
   effective date. Check `nseindia.com`'s indices/circulars section and the
   NSE archives. If these exist in a structured, dated format, this closes
   the membership half of Item 13 directly.
2. **NSE ASM/GSM/T2T daily circulars.** Published as daily PDF/CSV circulars,
   not a queryable historical API. Likely needs a scraper that walks
   historical circular archive pages and parses them into a
   (security, date, status) table. Bounded but real engineering work.
3. **NSE/BSE delisted-companies lists.** Both exchanges publish
   delisted-company registers. Smaller, more static dataset than #1/#2 —
   should be the easiest of the three.
4. **Price history for delisted names.** Once you have *which* securities
   delisted and *when*, check whether `ohlcv_daily` (or a paid vendor) has
   price history for them up to the delisting date. If the current ingestion
   pipeline only tracks currently-active securities, this may need a
   separate backfill even after #3 is solved.
5. **Paid vendor fallback.** If any of #1–#4 turns out to be genuinely
   unobtainable free (NSE stops publishing historical reconstitution data
   beyond some point, archives are incomplete, etc.), document exactly what
   was tried and what failed, then evaluate a paid vendor for that specific
   gap only — don't default to a vendor for the whole problem if free
   sources cover most of it.

**Known practical risk, same as Loop 2:** confirm network reachability to
`nseindia.com` (and any vendor API) from the Builder environment before
spending the round on integration code that can never run. If blocked,
either add the domain to the network allowlist or have the human pre-download
the raw files into a known repo path (e.g. `data/raw/nse/`) for Builder to
parse instead of fetching live.

## 1. What "done" looks like for each gap

### Item 13 — Point-in-time Nifty 500 membership + T2T/ASM status

- A new `EligibilityFactsProvider` adapter, real (not a stub), backed by
  data sourced per §0.
- Given a `security_id` and `decision_date`, returns the **actual** historical
  `in_nifty_500`, `is_t2t`, `is_under_surveillance` values as of that date —
  not today's status applied retroactively.
- `StubAllActiveSecuritiesEligibilityProvider` (built in the Approximations
  loop) stays in the codebase as a documented fallback/dev tool, but the CLI
  and any production path should default to the real provider once it
  exists. Do not delete the stub — future rounds or environments without
  full data access may still need it.
- If full point-in-time coverage isn't achievable for the entire backtest
  window (e.g. NSE's reconstitution archive only goes back to some year),
  document the actual coverage window achieved, and the CLI/report should
  state the coverage window explicitly rather than silently applying the
  real provider outside its verified range.

### Item 8 — Survivorship (delisted securities)

- At least one real delisted security, with real price history up to its
  delisting date, present in the database.
- `securities.delisting_date` should be populated for real delisted names
  (or an equivalent field/table if the schema needs extending — that's a
  legitimate round-3 schema change, not scope creep, since Item 8 has been
  blocked on exactly this since Loop 1).
- Once populated, checklist item 8's original test becomes runnable for
  real: confirm a known-delisted ticker appears in the historical universe
  provider's output for a date before its delisting, and confirm the
  walk-forward runner actually includes it in eligibility evaluation for
  that date.

## 2. What Reviewer checks this round

Same evidentiary bar as every prior loop — [RUN], not read-and-infer.

- **Point-in-time correctness, not just presence.** Pick a specific
  historical date and a specific security. Independently verify (from the
  raw source file/table, not by reading the provider's code) whether that
  security was actually a Nifty 500 constituent / under T2T / under ASM on
  that date, and confirm the new provider returns the same answer.
- **Coverage honesty.** If coverage is partial (e.g. reconstitution data only
  goes back to 2018), confirm the code/report actually states this
  limitation rather than silently returning data outside the verified range.
- **Survivorship, for real this time.** Pick the actual delisted security
  Builder sourced. Confirm it appears in the eligible universe for a
  rebalance date before delisting, and confirm it's correctly excluded (or
  correctly handled per brief.md, e.g. liquidated at last traded price) for
  dates at/after delisting — this is the actual mechanism checklist item 8
  was written for, finally executable.
- **Regression on everything frozen.** Same as every prior round — re-run
  the full suite, confirm `domain/backtest/`, `walk_forward.py`, and the two
  existing SQL providers are untouched (`git diff` against the last
  Approximations-loop commit should show zero changes to those paths unless
  a specific, justified reason is given).

## 3. Explicitly out of scope for Loop 3

- TRI benchmark data — still a separate, already-documented gap
  (`brief-addendum-approximations.md`), not part of this loop unless Builder
  finds it while sourcing membership data and flags it as an easy add-on.
- Strategy changes (weights, buffer size, universe rules) — brief.md changes
  only, not a Loop 3 code task.
- Live trading / broker integration — still out of scope per the original
  scoping decision.

---
**Before Loop 3's round 1 starts:** confirm network reachability to NSE (or
wherever the data will come from), same check as Loop 2. If this loop
concludes that full point-in-time data genuinely isn't obtainable for free,
that's a legitimate outcome — document exactly what was tried, and revisit
the paid-vendor option with a specific, narrowed scope rather than "buy
everything."
