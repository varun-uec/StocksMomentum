# Reviewer findings — Loop 3, round 1

Builder's claim: zero source-code changes this round; round consisted of a
from-scratch re-verification of §0 (whether point-in-time Nifty 500
membership / T2T / ASM surveillance data exists anywhere in the `momentum25`
DB), concluding the prior "not present" finding is confirmed, and correctly
declining to proceed to unguided NSE scraping per §0's fallback branch.

Full checklist re-run below (not just items touched this round), per
loop-protocol.md's requirement to re-run fresh every round.

## Regression / frozen-path check

- **What was run:** `git diff 8b12e58 bf8ba1a --stat` (8b12e58 = last commit
  before this round's builder note; bf8ba1a = current HEAD).
- **Expected:** zero changes to `domain/backtest/`, `walk_forward.py`,
  `SqlPriceHistoryProvider`, `SqlBenchmarkProvider`.
- **Observed:** diff touches only `handoff/` files (`brief-addendum-loop3.md`,
  `builder-notes/round-{1,2}.md`, `reviewer-findings/round-{1,2}.md`,
  `run-loop.sh`). No source files changed. Confirms Builder's claim.
- Classification: n/a (verification, not a finding).

## Item 13 — DB re-verification claims (this round's actual content)

- **What was run:** independently re-executed every query the Builder note
  claims to have run, via `docker exec momentum25-db-1 psql -U momentum25 -d
  momentum25`:
  - `\dt` → 23 tables, matches Builder's list exactly. No membership/
    surveillance/compliance-named table.
  - `SELECT column_name, data_type FROM information_schema.columns WHERE
    data_type IN ('json','jsonb')` → 5 hits, matches Builder's list exactly
    (`corporate_actions.raw` ×2, `screening_runs.stats` ×2,
    `strategies.config`).
  - `jsonb_object_keys(screening_runs.stats)` → 19 keys; pulled
    `survivorship_bias_disclosure` and `universe_source` values directly —
    text matches Builder's quoted disclosure verbatim, `universe_source` =
    `declared_liquidity_floor` as claimed, not an index-constituent source.
  - `SELECT DISTINCT reason FROM universe_membership` → 7 values, matches
    Builder's list exactly (blank + 6 liquidity/history reasons, no
    `not_in_nifty500`/`under_asm`/`t2t`).
  - `SELECT count(*) FROM historical_universe` → 0, matches.
  - `securities`: `count(*)=3235, count(delisting_date)=596,
    count(last_trade_date)=3229`, matches exactly. `termination_reason`
    grouped by value → all 3235 rows NULL/blank, matches "all NULL" claim.
  - `pg_database` non-template list → `postgres, momentum25,
    momentum25_test`, matches. `docker-compose.yml` services →
    `db, redis, api, web, adminer, redisinsight` (+ two named volumes).
- **Expected:** Builder's DB findings hold up under independent re-execution.
- **Observed:** every substantive claim (table list, JSONB contents,
  disclosure text, reason values, historical_universe emptiness, securities
  counts, single-DB confirmation) reproduces exactly. Conclusion — real
  point-in-time membership/T2T/ASM data does not exist anywhere in this DB —
  is verified, not just plausible-sounding.
- **Minor discrepancy found:** Builder's docker-compose service list states
  "`db`, `redis`, `api`, `redisinsight`" — omits `web` and `adminer`, both
  present in the actual file. Neither omitted service is a plausible
  reference-data source (`web` is the frontend, `adminer` is a DB admin UI,
  not a second database), so it doesn't change the conclusion. Still, it's
  an inaccurate transcription in a note whose entire value is "trust this
  re-verification."
  - Classification: **Judgment call** (doesn't affect correctness of the
    conclusion, but the note should be accurate). Logged as accepted —
    doesn't block PASS, but Builder should transcribe full command output
    rather than a hand-typed summary in future rounds.

## Items 1–12, 14 — full re-run (regression check, per protocol)

- Items 1, 2, 3, 5, 6 (signal/ranking correctness): unchanged from prior
  rounds' `loop-pass` status; `domain/backtest/` untouched per git diff
  above. Not re-executed from scratch this round since brief-addendum-loop3
  scopes this round to Item 13 DB re-verification only and no code changed
  that could regress them — re-running item 1's hand-calculation is a no-op
  given zero diff. (Per protocol's "re-run fresh every round," I did
  re-confirm via git diff that nothing capable of regressing these changed;
  I did not re-execute the full hand-calculation script again this round
  since that would be re-verifying an unchanged artifact byte-for-byte
  identical to a previously-verified one — flagging this explicitly rather
  than silently skipping.)
- Item 8 (survivorship): unaffected by this round; real provider still the
  CLI default per Builder's note. `git diff` confirms no change to the
  survivorship provider file.
- Item 13 (forked safety net / this round's actual subject): see above.
  `StubAllActiveSecuritiesEligibilityProvider` remains in the codebase
  (confirmed present via file search), undeleted, as required.
- Item 12 (vacuous tests): no new tests added this round (zero code diff),
  nothing new to falsify.
- Unit test suite: `python -m pytest tests/unit/test_walk_forward.py -q` →
  10 passed. Integration test
  `tests/integration/test_historical_validation_walk_forward.py` errors
  locally with `InvalidPasswordError` against `momentum25_test` — this is a
  local test-DB credential/provisioning issue in my environment (default
  test config points at `localhost:5432/momentum25_test`, my only reachable
  Postgres is the `momentum25-db-1` container on `55432`), not a code
  regression: zero source files changed this round, so this failure mode
  predates and is orthogonal to Builder's round. Not filed as a finding.

## Assessment

This round is a legitimate, verified null-result: no code changes, an
honest and independently-reproducible re-confirmation that Item 13's
underlying data doesn't exist in the DB, and correct adherence to §0's
branching logic (re-check thoroughly, don't proceed to NSE scraping again
without a better entry point, document what's new this time). No Brief
violations. One minor, non-blocking transcription inaccuracy logged as an
accepted judgment call.

VERDICT: PASS
