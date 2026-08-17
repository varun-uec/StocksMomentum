# Builder note — Loop 3, round 1

## What changed

1. **Archived the Approximations-loop round files** so Loop 3 restarts round
   numbering from 1, same pattern as the loop-2 archive: `handoff/builder-notes/round-{1..4}.md`
   → `handoff/builder-notes/approximations/round-{1..4}.md`, same for
   `handoff/reviewer-findings/`. `handoff/run-loop.sh` updated to point Builder
   and Reviewer prompts at `brief-addendum-loop3.md` (this was already
   uncommitted in the working tree at round start; kept and finished it).

2. **Item 8 (survivorship) closed for real.** Ran
   `scripts/rp012_populate_survivorship_dates.py` (a pre-existing, deterministic,
   data-derived script already in the repo from prior RP-012 research — not new
   code) against `momentum25-db-1`. It classifies every security's
   `listing_date`/`last_trade_date`/`delisting_date` from observed bar coverage
   in `ohlcv_daily` ∪ `legacy_ohlcv_daily`, using a 60-trading-day gap rule
   (`domain/research/survivorship.classify_survivorship`, pure, already
   reviewed). Result: `securities_classified=3229 delisted=596 active=2630
   indeterminate_boundary=3`. Spot-checked plausibility against known real
   events: GRUH Finance (delisting_date 2019-10-15, merged into Bandhan Bank),
   IL&FS Engineering/IL&FS Transportation (2018-10-15 / 2019-03-29, IL&FS
   crisis) — dates match public record. `is_active` was confirmed NOT reliable
   as a delisting signal (some `is_active=TRUE` rows already carry a populated
   `delisting_date` — the ingestion flag and the observed-data-derived date
   disagree; the script documents this and correctly does not treat it as
   ambiguous).

   Added `SqlSurvivorshipEligibilityProvider`
   (`infrastructure/persistence/repositories/walk_forward_market_data.py`):
   includes a security for a decision date iff
   `listing_date <= decision_date <= (delisting_date or +inf)`, using the
   now-populated columns instead of `is_active`. Wired into the CLI
   (`interface/cli/main.py`) as the walk-forward command's eligibility
   provider, replacing `StubAllActiveSecuritiesEligibilityProvider` there.
   Per `brief-addendum-loop3.md` §1 Item 13, **the stub itself is untouched
   and still exported** — it stays as a documented fallback/dev tool, just no
   longer the CLI's default.

3. **Item 13 (point-in-time Nifty 500 / T2T / ASM membership) — still not
   obtainable this round, documented attempt below (not a silent skip).**
   Membership/surveillance in `EligibilityFacts` remains stub
   (`is_t2t=False`, `is_under_surveillance=False`, `in_nifty_500=True` for
   every security), same as the Approximations loop. `SURVIVORSHIP_ELIGIBILITY_WARNING`
   replaces `ELIGIBILITY_STUB_WARNING` as the CLI's runtime warning — it states
   plainly that survivorship is now real and membership/surveillance is not,
   rather than bundling both under one blanket "stub" label as before.

## Real attempt made on Item 13 (NSE data sourcing)

- `nseindia.com` is TCP/TLS-reachable from this environment but the bare
  homepage returns `403` without a browser session; a warm-up GET (cookie jar
  + realistic `User-Agent`) against the homepage, then a follow-up request
  with those cookies, does work — `GET /api/corporates-corporateActions`
  returned `200` with real, current corporate-action rows. So the network/
  anti-bot problem flagged as a risk in `brief-addendum-loop2.md` is
  surmountable for at least some endpoints.
- Tried nine plausible endpoint names for (a) a delisted-companies register
  and (b) historical index reconstitution, under the same warmed-up session:
  `/api/live-analysis-delistedCompanies`, `/api/comp-delisting`,
  `/api/companies-listing-delisting`, `/api/CorporatesDelisting`,
  `/api/corporate-delisting`, `/api/liveEquity-derivatives?index=delisted`,
  `/market-data/security-wise-delisting`, plus two `archives.nseindia.com`
  CSV path guesses for `eq_delisted_companies.csv`. All returned `404` (or
  `000`/timeout for one `archives` host). None of these are documented public
  API paths I could find from this environment — I was guessing plausible
  URL shapes against a live site with no API reference available here, which
  is an unreliable way to find a real data feed and I stopped rather than
  keep guessing indefinitely.
- No ASM/GSM/T2T daily-circular archive endpoint or historical index
  constituent-change endpoint was found or fetched this round.
- Conclusion for this round: Item 13 genuinely isn't closed. The blocker is
  not network reachability (that part works) — it's not knowing NSE's actual
  API surface for these two specific datasets without either a documented
  reference or a browser-based session to observe real requests being made.
  A follow-up round with either (a) a human providing the correct endpoint
  paths / a manually-downloaded circular archive dropped in `data/raw/nse/`,
  or (b) browser automation to observe the real request URLs the NSE website
  itself makes when a human loads the delisting/reconstitution pages, would
  very likely close this — guessing REST paths blind is not the right next
  step and I did not keep escalating that approach.
- Per `brief-addendum-loop3.md` §0 item 5 (paid vendor fallback): not
  evaluated this round — free-source attempts were not exhausted enough
  (see above) to justify moving to a paid vendor for this specific gap yet.

## What Reviewer should check this round

- `git diff` against `d37cbb5` (last Approximations-loop commit) touches only
  `walk_forward_market_data.py` (new class + docstring), `interface/cli/main.py`
  (provider swap), the new test file additions, and `handoff/` files — zero
  changes to `domain/backtest/`, `application/use_cases/walk_forward.py`,
  `SqlPriceHistoryProvider`, or `SqlBenchmarkProvider`.
- `securities.delisting_date` is populated from real data (not fabricated) —
  re-run `scripts/rp012_populate_survivorship_dates.py --dry-run` and confirm
  the same counts; spot-check GRUH/IL&FS dates above against public record
  independently.
- `SqlSurvivorshipEligibilityProvider.facts_as_of()` actually excludes a
  delisted name post-delisting and includes it pre-delisting, and the CLI
  (`walk-forward` command) is the one actually using it now, not just a
  provider that exists but isn't wired (checklist item 13's "forked safety
  net" pattern from prior rounds).
- The membership/T2T/ASM gap is still honestly labeled at the point the
  benchmark/warning text reaches a human (CLI stdout), not just in this note.

## Tests / verification run

- `pytest tests/integration/test_walk_forward_market_data_providers.py -q`
  → 9 passed (3 new: delisted-before-eligible, delisted-after-excluded,
  `is_active` ignored).
- Full suite: `pytest -q` → 633 passed.
- Manual CLI run: `walk-forward 2024-01-01 2024-03-01` against the real DB —
  completes, prints the new warning text, 3 rebalances / 103 trades, non-zero
  return. Output captured above.

## Commit

Not yet committed — will commit after this note is written, as
`git diff --stat` shows: `walk_forward_market_data.py` (+98/-?),
`interface/cli/main.py`, `test_walk_forward_market_data_providers.py` (+49),
`handoff/run-loop.sh`, plus the archive renames and this note.

Not marking anything PASS or resolved — that's Reviewer's call.
