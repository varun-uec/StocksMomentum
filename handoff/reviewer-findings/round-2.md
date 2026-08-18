# Reviewer findings — round 2 (second independent pass)

Per `loop-protocol.md` Termination, this round exists to confirm round-1's
`PASS` with a second, independent pass and zero code changes in between,
verified by `git diff`, not either agent's word. Full checklist re-run fresh
per `reviewer-handoff.md` and `loop-protocol.md`'s "not just the items that
failed last time" requirement — nothing inferred from reading code alone;
every item below was executed.

## Finding 1 — `handoff/builder-notes/round-2.md` is stale and does not
describe the round-1 it claims to follow

- Checklist item: unlisted (process/file-layout integrity, not a signal or
  backtest-correctness item).
- Classification: **Judgment call** (accepted — does not block PASS, see
  reasoning below, but should be fixed going forward).
- What was run: `git log --oneline -15`, then `git show --stat` on each of
  `8b12e58`, `efc48a9`, `23ef183`, `cd40d40`, `bf8ba1a`, `1bc098e` to
  reconstruct which files each commit actually touched, then read the full
  content of `handoff/builder-notes/round-1.md`, `round-2.md`,
  `handoff/reviewer-findings/round-1.md`, `round-2.md` as they exist on disk
  at current `HEAD` (`1bc098e`).
- Expected: `builder-notes/round-2.md` (the file I was told to verify as
  "this round's claim") describes a no-op round following the round-1 that
  is currently recorded in `reviewer-findings/round-1.md`.
- Observed: it does not. `builder-notes/round-1.md` was rewritten twice —
  once by `8b12e58` (real `SqlSurvivorshipEligibilityProvider` + a documented
  9-endpoint NSE sourcing attempt for Item 13) and again by `bf8ba1a` (a
  second, later "round 1" that overwrites that description with a from-
  scratch DB re-verification per the revised `brief-addendum-loop3.md` §0).
  `reviewer-findings/round-1.md` was correspondingly rewritten by `1bc098e`
  to review the `bf8ba1a` content. But `builder-notes/round-2.md` and
  `reviewer-findings/round-2.md` on disk are still the **first** cycle's
  files (`23ef183`/`cd40d40`), written against the now-superseded
  `efc48a9` round-1 (the `SqlSurvivorshipEligibilityProvider`-description
  version, not the DB-re-verification version). `round-2.md`'s text
  literally says "`HEAD` remains `efc48a9`" — untrue at current `HEAD`
  (`1bc098e`) — and cites round-1 claims (Item 8 closed via a described
  provider-add, Item 13 nine-endpoint attempt) that are no longer what
  `reviewer-findings/round-1.md` currently says round 1 covered (DB
  re-verification only). No round-2 file was ever written against the
  `bf8ba1a`/`1bc098e` round-1 cycle.
- Why this doesn't block PASS: independent of which round-1 cycle is being
  cited, the underlying **source code has not changed at all** across every
  one of these commits. `git diff 8b12e58 HEAD --stat -- src/ tests/` and
  `git diff bf8ba1a HEAD --stat -- src/ tests/` are both empty — every
  commit in this sequence (`efc48a9`, `23ef183`, `cd40d40`, `bf8ba1a`,
  `1bc098e`) touched only `handoff/*.md` and `run-loop.sh`. So the
  protocol's actual substantive concern for a round-2 ("did code change
  between the two Reviewer passes?") is satisfiable by direct `git diff`
  regardless of which handoff file is stale — and it comes back empty. I
  re-verified every checklist item below fresh myself rather than trust
  either round-2 file's narration.
- Builder should regenerate `builder-notes/round-2.md` against the current
  `reviewer-findings/round-1.md` next round so the file trail is coherent,
  rather than leaving two rounds' worth of round-2 files pointing at a
  superseded round-1.

## Zero-code-change confirmation [RUN]

- What was run: `git diff 8b12e58 HEAD --stat -- src/ tests/` and
  `git diff bf8ba1a HEAD --stat -- src/ tests/` (both plausible "round-1
  reviewed" base points, given Finding 1).
- Expected: empty (no source/test changes since either candidate round-1).
- Observed: both empty. `git status`: clean. Confirms no code changed
  regardless of which round-1 cycle is treated as the reference point.

## Full test suite [RUN]

- What was run: `M25_DATABASE_URL=postgresql+asyncpg://momentum25:momentum25@localhost:55432/momentum25_test python -m pytest -q`
  from `src`'s project root (repo root, not a `backend/` subdirectory — the
  latter doesn't exist; confirmed with `ls`).
- Expected: full pass, matching round-1's reported 633.
- Observed: `633 passed, 1 warning in 10.70s`. Matches exactly, obtained
  independently in a fresh shell.

## Item 8 — Survivorship (delisted securities) [RUN]

- Classification: no finding (independently re-verified, holds).
- What was run:
  - `grep` confirms `SqlSurvivorshipEligibilityProvider` is defined in
    `src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py`
    and imported/used (not just defined) in
    `src/momentum25/interface/cli/main.py` (`universe = await
    SqlSurvivorshipEligibilityProvider.load(session)`), i.e. wired to the
    live CLI path, not a forked-safety-net.
  - Queried the prod DB directly: `SELECT id, delisting_date FROM securities
    WHERE symbol='GRUH'` → `(9992, 2019-10-15)`.
  - Instantiated the real provider against the live prod DB in a fresh
    scratch script (not copy-pasted from any prior round's script) and
    called `facts_as_of(date(2019,10,15))` vs `facts_as_of(date(2019,10,16))`.
    Observed: security id `9992` present in the `before` set, absent from
    the `after` set — matches the brief's "included up to and including
    delisting date, excluded from the day after" semantics.
- Expected vs observed: match. Independently reproduced, not relayed from
  either round-2 file or round-1's note.

## Item 13 — Point-in-time Nifty 500 / T2T / ASM membership [RUN]

- Classification: Judgment call (accepted) — re-verified, unchanged from
  round-1's conclusion.
- What was run: independently re-executed the DB queries `\dt`,
  `SELECT count(*) FROM historical_universe`, and
  `SELECT DISTINCT reason FROM universe_membership` against
  `momentum25-db-1` via `docker exec ... psql`.
- Expected vs observed: `historical_universe` count = `0` (matches round-1's
  claim); `universe_membership.reason` distinct values are 7
  liquidity/history reasons (`below_liquidity_floor`, `close_below_floor`,
  `insufficient_history`, `no_bar_on_trading_date`, `not_yet_listed`,
  `stale_data`, blank) — no membership/T2T/ASM-flavored value present,
  matching round-1's claim that no point-in-time membership/surveillance
  data exists in this DB. `StubAllActiveSecuritiesEligibilityProvider`
  remains present in `src/` and `tests/` per `grep`, undeleted, as the
  addendum requires.
- No new sourcing attempt was made or required this round (no code
  changed), so nothing new to evaluate beyond re-confirming the prior
  documented-attempt outcome still matches the code and DB state, which it
  does.

## Regression on frozen paths [RUN]

- What was run: `git diff 8b12e58 HEAD --stat -- src/`.
- Expected: empty.
- Observed: empty — `domain/backtest/`, `walk_forward.py`,
  `SqlPriceHistoryProvider`, `SqlBenchmarkProvider`, and every other source
  file are untouched across the entire commit range covering both round-1
  cycles.

## Summary

Every checklist item re-run this round reproduces independently, from fresh
commands against live DB/CLI/test state, not from reading either stale
round-2 handoff file. Zero source-code changes anywhere in the commit range
under review. The one real defect found this round is a documentation/
process one (Finding 1: `round-2.md` is stale and narrates a superseded
round-1), not a signal, ranking, or backtest-integrity defect — it does not
change any of the underlying facts, which all independently check out.

VERDICT: PASS
