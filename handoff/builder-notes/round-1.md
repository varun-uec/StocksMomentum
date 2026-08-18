# Builder round-1 — Loop 3 restart (Item 13 DB re-verification)

Note: this overwrites the prior loop-3 round-1.md, which covered a different
(already-passed) loop pass. This round starts fresh against the revised
`brief-addendum-loop3.md` (new §0 "Check the app database FIRST, thoroughly,
before touching NSE").

## What changed

Nothing in source code. This round did the required DB re-verification per
§0 and, on confirming the prior conclusion, stopped rather than spend the
round on unguided NSE scraping (permitted explicitly by §0's second branch:
"If this re-check confirms the prior finding ... proceed to §0b ... and
state in the round note explicitly what was checked this time that wasn't
checked before").

## Findings addressed

§0 required re-verifying, from scratch, whether point-in-time Nifty 500
membership / T2T / ASM surveillance data exists anywhere in the `momentum25`
Postgres DB, more thoroughly than the Approximations-loop check that first
concluded it doesn't.

Commands run (via `docker exec momentum25-db-1 psql -U momentum25 -d momentum25`):

1. `\dt` — full 23-table list. No table named for membership, constituents,
   surveillance, or compliance. New-since-last-check tables are only
   `*_snapshot_20260810` backups and `bse_scrip_junction` /
   `bse_legacy_ohlcv_daily` (BSE ISIN mapping / price history — not
   membership).
2. `SELECT column_name, data_type FROM information_schema.columns WHERE
   data_type IN ('json','jsonb');` across the whole schema — 5 hits:
   `corporate_actions.raw`, its snapshot, `screening_runs.stats`, its
   snapshot, `strategies.config`. **This is new coverage** — the prior check
   did not inspect JSONB contents. Dumped keys and values:
   - `screening_runs.stats.universe_source` = `declared_liquidity_floor`
     (not an index-constituent source).
   - `screening_runs.stats.survivorship_bias_disclosure` (verbatim from the
     DB): *"Universe excludes securities not yet listed as of as_of_date,
     but cannot exclude securities later delisted or dropped from the index
     (no historical index-constituent history is available). Results may
     still overstate historical performance for older dates."* — the app's
     own data documents this exact gap.
   - `strategies.config.universe` (all 7 strategies) = liquidity/history
     floor (`EQ` series, min price ₹20, min 252d history, min ₹1cr
     turnover) — not Nifty 500 constituency. `config.benchmark_index` =
     `NIFTY500`, a benchmark code only.
   - `corporate_actions.raw` keys = `{subject, symbol}` only, no
     surveillance content.
3. `universe_membership.reason` distinct values (438,901 rows), re-checked
   fresh: `(blank)`, `insufficient_history`, `not_yet_listed`, `stale_data`,
   `no_bar_on_trading_date`, `below_liquidity_floor`, `close_below_floor`.
   Still no `not_in_nifty500` / `under_asm` / `t2t` reason. Unchanged from
   prior finding.
4. `historical_universe` — still 0 rows.
5. `securities` re-check: `count(*)=3235`, `count(delisting_date)=596`
   (Item 8's real data, unaffected), `count(last_trade_date)=3229`.
   `termination_reason` column — **all 3235 rows NULL**. This column
   plausibly could have held status data; checked and it doesn't.
6. `survivorship_gap_event` — 9,902 rows, still trading-gap detection, not
   delisting/surveillance flags.
7. Whole-schema column-name regex scan for
   `asm|t2t|surveil|gsm|nifty|index|member|constituent|segment|series|status|flag|trade_to_trade|compliance`
   — 4 hits, all false positives (`benchmark_index_daily.index_code`,
   `corporate_action_inference_log.flagged`, `screening_runs(_snapshot).status`
   = run status completed/failed). **New coverage this round.**
8. `rule_results.rule_id` (24 distinct, all technical/momentum rules) and
   `explanation` free-text search for `nifty|index|asm|t2t|surveil|member` —
   0 rows. **New coverage this round.**
9. Second-database check: `SELECT datname FROM pg_database WHERE
   datistemplate=false` → `postgres, momentum25, momentum25_test` only.
   `docker-compose.yml` services: `db`, `redis`, `api`, `redisinsight`.
   No separate reference-data DB or back-office service exists on the
   evidence available. **New coverage this round** (§0's explicit ask about
   other databases/services).

**Conclusion: the prior finding is confirmed, not overturned.** Point-in-time
Nifty 500 membership, T2T status, and ASM/GSM surveillance status do not
exist anywhere in the `momentum25` database — not in a differently-named
table, not in a JSONB column, not in a text status column. The database's
own `survivorship_bias_disclosure` field states the gap outright.

Per §0's explicit fallback and §0b's caution against forcing coverage, this
round did not attempt NSE scraping. The prior loop-3 pass already tried
guessing NSE API paths (nine 404s, cookie session established but no valid
endpoint found) — repeating that without a better entry point would not be
a real attempt, just more guessing. That is a judgment call, not a silent
skip; flagged for a human below.

Item 13 remains a documented stub (`StubAllActiveSecuritiesEligibilityProvider`,
undeleted, per the addendum). Item 8 (survivorship) is unaffected — real,
unchanged, still the CLI default provider.

## Frozen paths — regression check

`git diff` on `domain/backtest/`, `walk_forward.py`, `SqlPriceHistoryProvider`,
`SqlBenchmarkProvider` is empty. No source files were touched this round.

## Commit

No commit this round — zero code changes. This note and the (uncommitted,
human-edited) addendum are the only artifacts.

## Open items for a human (not resolvable by another Builder round alone)

1. **NSE sourcing needs a real entry point.** Blind guessing at NSE API
   paths failed previously (9x 404). Productive next step: either (a) human
   drops raw NSE/niftyindices files into `data/raw/nse/` for Builder to
   parse, or (b) browser automation to observe the real request URLs NSE's
   site issues. Recommend deciding which before spending another round on
   this.
2. **Even with NSE data, expect partial coverage.** Per §0b, the known free
   membership file (`IndexInclExcl.xls`) reportedly stopped updating
   ~2020-07-31; ASM/GSM/T2T only has a current-snapshot source, no
   historical archive found. A full point-in-time fix across the whole
   2019–2026 backtest window is unlikely from free sources alone.
