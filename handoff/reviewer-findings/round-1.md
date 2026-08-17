# Reviewer Findings — Loop 2, Round 1

Verified against `handoff/brief.md` + `handoff/brief-addendum-loop2.md` (both
FINAL) and `handoff/builder-notes/round-1.md` (Loop 2) as a claim to verify,
not a summary to relay. This overwrites the stale Loop-1 content that
previously lived at this same file path (`git log` confirms the current
`builder-notes/round-1.md` is the walk-forward-engine note, commit `5f93e89`,
not Loop 1's signal/ranking note).

## What exists this round

New: `domain/ports/walk_forward.py` (3 ports), `application/use_cases/walk_forward.py`
(`WalkForwardRunner`), `tests/unit/test_walk_forward.py` (7 tests, in-memory
fakes only). No real infrastructure adapter, no interface-layer caller.
Confirmed by `grep -rl "walk_forward" src/momentum25/infrastructure
src/momentum25/interface` → empty, matching Builder's own claim.

## Checklist results

**§0 — NSE reachability claim.** [RUN]
Re-ran two of Builder's exact commands independently, fresh: `curl -A
Mozilla https://www.nseindia.com` → **403** (matches claim). `curl -A Mozilla
https://archives.nseindia.com/content/historical/EQUITIES/2023/JAN/cm02JAN2023bhav.csv.zip`
→ **200** (matches claim). Builder's reachability finding reproduces. No
finding.

**Item 4 — Universe construction (real data).** [RUN attempted]
`grep -rl "EligibilityFactsProvider\|BenchmarkProvider\|PriceHistoryProvider"
src/momentum25/infrastructure` → empty. No real point-in-time membership
adapter exists; only the `Protocol` and test fakes. Cannot register a
synthetic instrument against a real pipeline this round — same class of gap
as Loop 1 item 4, one layer up. Classification: **Judgment call, accepted**
— this is the documented, human-decision-blocked gap from addendum §0/§1
(no free NSE endpoint for point-in-time Nifty 500 membership), not a silent
skip. Consistent with CLAUDE.md "Don't Guess."

**Item 4b — Universe construction (fake/synthetic).** [RUN]
Independently built a *different* survivorship scenario than Builder's test
(different securities, different cutoff, different growth rates, using
`DatedUniverse`-equivalent logic I wrote from scratch, not copy-pasted).
Also added a third case: an "IPO-like" security with price history starting
only 2023-01-01 (no 12m-ago price), eligibility facts otherwise marking it
eligible (400 listing days). Expected: dropped from every selection because
`_score` requires all 4 prices. Ran `runner.run(...)` → observed `selected`
never contains that security across 3 rebalances, `eligible_count=2` every
time (eligibility predicate doesn't know about missing prices, only `_score`
catches it) — confirms fail-closed happens at the price layer, not silently
via the eligibility predicate. No finding; this also resolves the Loop-1
"batch-level NaN/missing-data" judgment call that was previously undecided
pending orchestration — orchestration now exists and demonstrates fail-closed
end-to-end.

**Item 5 — NaN / missing-data, batch level.** [RUN]
See item 4b above — same experiment answers this. A security missing any of
its 4 required prices is silently excluded from `signals`, never crashes the
batch, never appears in `selected`. No finding. **Previously-open Loop-1
judgment call is now resolved, not just carried forward** — recording this
explicitly since the mechanical trigger "a finding that was marked fixed
recurs" only fires on regressions, and this is the inverse (a previously-open
item becoming closed); noting it so it isn't miscounted as new.

**Item 7 — Look-ahead, portfolio level.** [RUN]
Wrote a fresh leaky provider independent of Builder's `LeakyPrices`: `SneakyPrices`
returns a price dated `as_of + 1 day` only on the "current price" call
(`target == as_of`), and an earlier, clean price otherwise — a subtler leak
pattern than Builder's own test (which leaks unconditionally on every call).
Expected: `LookAheadError`. Observed: raised, with the correct security id
and dates in the message (`price for security 1 dated 2023-03-01 is after
decision date 2023-02-28`). No finding.

**Item 8 — Survivorship.** [RUN — synthetic, not real-data; see item 4 for
the real-data gap]
Independent scenario, different from Builder's test: swapped which security
survives/delists, different cutoff date, different growth rates. Confirmed
the departing security is selected pre-cutoff and never post-cutoff. No
finding on the mechanism; real-data survivorship (a real delisted ticker
pulled from NSE archives) is not runnable yet — same accepted gap as item 4.

**Item 9 — Corporate actions.** Not executable. No real adjusted-close
adapter is wired into these new ports this round (the existing
`infrastructure/providers/bhavcopy.py` / `ohlcv.py` pipeline is not yet
plugged into `PriceHistoryProvider`). Classification: **Judgment call,
accepted** — consistent scope-split, not a silent skip; Builder's note names
this explicitly as deferred.

**Item 10 — Fill timing.** [RUN]
Independent stress test: built a calendar where the 1st of every month is a
non-session (holiday-on-rebalance-day edge case, not in Builder's test) to
try to force an off-by-one into a same-day fill. Ran 6 rebalances across
Mar–Aug 2023. Expected: `fill_date > decision_date` always. Observed: true
for all 6 (e.g. decision `2023-02-28` → fill `2023-03-02`, decision
`2023-06-30` → fill `2023-07-03`). No finding — the strict-inequality
enforcement holds even under calendar irregularity, not just the smooth
weekday-only calendar Builder's own tests use.

**Item 12 — Vacuous test check.** [RUN]
Mutated the source (not the test) twice, ran the target test each time on
the real (non-copied) file, then reverted with `git checkout --`:
1. Replaced the `LookAheadError` raise condition with `if False:` →
   `test_look_ahead_provider_is_rejected` went from PASS to **FAIL** ("DID
   NOT RAISE LookAheadError").
2. Changed `facts_as_of(decision_date)` call to always pass a future dummy
   date (`date(2099,1,1)`) → `test_survivorship_point_in_time_universe_used`
   went from PASS to **FAIL** (`assert False` on the early-selection check).
`git status --short` confirmed clean revert both times. Both tests can
actually fail; neither is vacuous. No finding.

**Item 13 — Forked safety net.** [RUN]
The item-7 fresh `SneakyPrices` test above already proves the as-of check
fires on the real `.run()` path (not an isolated unit call) — it raised from
inside `runner.run()`, not from a standalone call to `_price`. Also
independently confirmed via `prices.calls` spy in the existing
`test_asof_enforcement_runs_on_real_path` (re-read, not re-run — identical
mechanism to what I already exercised in items 7/8b). No finding.

**Item 14 — Benchmark/attribution.** [RUN]
Re-derived NAV independently for the missing-price scenario built in item
4b (not Builder's `_build_runner` fixture): replayed `result.trades` by hand
in a fresh script (cash -= notional + cost, accumulate qty, mark survivors at
`end`), compared to `result.final_nav`. Matched exactly. Also note (not a
finding): `_reconstruct_nav_from_trades` calls
`prices.price_on_or_before(sid, end, end)` directly, bypassing the runner's
`_price()` look-ahead-checking wrapper. This is intentional per Builder's
docstring (independence from engine bookkeeping) and `target == as_of == end`
here, so there's no as-of violation — but flagging for the record that this
function trusts the provider for its final mark, unlike every other price
read in the runner. Not a finding: the "no info dated on/after decision
date" rule (brief §9) doesn't apply here since `end` is the backtest's own
end-of-run bound, not a rebalance decision date, and there is no later
information available in a finite historical run for `end` itself to leak.

**Item 3 (signal-level look-ahead, carried from Loop 1, frozen code) —
regression check.** [RUN] `domain/backtest/momentum_signal.py` untouched
(`git diff a516be0 HEAD -- backend/src/momentum25/domain/backtest/momentum_signal.py`
→ empty). No finding.

**Full regression suite.** [RUN]
`pytest tests/unit/test_walk_forward.py -v` → 7/7 passed (fresh run).
`pytest tests/unit -q` (full suite) → **516 passed** (fresh run, matches
Builder's claim exactly).
`ruff check` on both new files + test file → all checks passed (fresh run).
`mypy` on both new files → Success, no issues (fresh run).

## Scope note (items 4, 8, 9 — real-data gap)

Builder correctly declined to build a real point-in-time-membership /
surveillance / corporate-action adapter rather than fake one against today's
data (which would silently bake in survivorship bias — exactly what
addendum §1 warns against). This is a genuine, documented, human-decision
blocker (vendor or manual dated-snapshot needed), not a scope dodge: Builder
ran the reachability check first as instructed, found NSE only publishes
*current* membership/surveillance lists, and stopped rather than guess.
Classification: **Judgment call, accepted.**

## Summary

- Findings requiring action: **0**
- Judgment calls logged: 3 — real point-in-time membership/surveillance
  provider (items 4, 8), real corporate-action adapter (item 9), all
  accepted, all blocked on the same documented human decision (vendor vs.
  manual dataset drop). Carried forward, not silently dropped.
- Previously-open item closed: Loop-1's batch-level NaN/missing-data
  judgment call is now demonstrated fail-closed end-to-end (item 4b/5).
- Reviewer overreach: 0
- All independently-run scenarios used numbers/security IDs/calendars
  different from Builder's own tests, including two source-mutation kill
  tests (item 12) and one adversarial leak pattern more subtle than
  Builder's own `LeakyPrices` (item 7).
- Tooling (ruff, mypy, pytest, full 516-test suite) independently re-run and
  clean.
- NSE reachability claims independently reproduced via fresh `curl` calls.

VERDICT: PASS
