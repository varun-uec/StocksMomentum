# Plan: Supabase Free feasibility audit (docs only)

## Context
Decide if Wickstreet's local Postgres can move to Supabase Free. Audit only. No migration, no writes, no Supabase contact.

## Evidence already gathered (read-only)
- DB: PG 16.15, `pg_database_size` 4614 MB. Free limit is 500 MB (to re-verify in current docs). Ratio ~9x. Full migration (option A) does not fit.
- Top tables: rule_results 1314 MB, legacy_ohlcv_daily 1139, bse_legacy_ohlcv_daily 981, ohlcv_daily 619, ohlcv_adj_snapshot_20260810 247, forward_returns 206. Rest < 50 MB.
- `ohlcv_daily` alone (619 MB) already exceeds 500 MB. Growth ~2.7k bars/day, ~0.4 MB/day, ~100 MB/yr for that table.
- Never-scanned indexes: legacy pkeys (599 MB), snapshot index (93 MB). Do not drop them; report only.
- Extensions: pg_trgm only (Supabase supports it). Single superuser role. No advisory locks, no FOR UPDATE, no COPY, no LISTEN/NOTIFY, no partitioning.
- Driver: asyncpg, pool 10+5, no SSL, no `statement_cache_size`. Supabase transaction pooler needs the cache off. Session pooler/direct does not.
- Discrepancies to resolve: live DB `alembic_version` is 0021, not 0024. The repo has no code for the five `*_snapshot_*` tables (they are ad-hoc DB tables). Dev DB `alembic check` shows 45 diffs.
- Benchmarks (NFR-11) are synthetic, 10 symbols, local DB. Not real-scale, not remote.
- Rights: `docs/audits/2026-10-19-m16-nse-data-use.md` and ADR-012 say hosting data remotely is unresolved. Cloud storage is not verified as permitted.

## Steps
1. Fetch current Supabase docs (WebSearch/WebFetch): Free DB limit, pause policy, backups, IPv6/IPv4 pooler, connection limits, egress, extension and role limits. Cite URLs.
2. Fill the gaps with light read-only queries: exact sizes of the five snapshot tables, forward_returns rows, WAL settings, 3/6/12-month projection (see below), data-dir 13.7 GB vs 4.6 GB DB cause.
3. Check the 0022–0024 migration files and `history.py` triggers for Supabase compatibility (superuser needs, `DO $$`, PK rewrite lock).
4. Write the reports to `audit-evidence/supabase-feasibility/` (follow `audit-evidence/README.md`): `FEASIBILITY_VERDICT.md` (A, G, five answers), `CAPACITY_REPORT.md` (B), `COMPATIBILITY_MATRIX.md` (C), `PERFORMANCE_ASSESSMENT.md` (D, with benchmark suite, labelled "predicted, not measured"), `ARCHITECTURE_COMPARISON.md` (E, options A–D), `MIGRATION_RUNBOOK.md` (F, not executed), `queries.sql` and raw outputs.
5. Update `.dashboard/index.html` to "feasibility assessment" (own entry only). Per global CLAUDE.md, use the dashboard-builder subagent (standing permission).
6. Commit docs only if `docs/README.md` governance allows. Never push.

## Expected verdict (to be confirmed by step 1–2)
- Q1 No (4.6 GB vs 500 MB). Q2 No. Q3 Hybrid cuts chart and screener workloads off remote latency. Per-security N+1 bar fetches over ~3k symbols would suffer on a remote DB.
- Hybrid (B) is the only Free-viable shape, and it still leaves ohlcv_daily (619 MB) local. That leaves only small user-data tables on Supabase. Gain is small, and it adds cross-DB consistency risk. Likely recommendation: **NOT VIABLE / stay local (D)**, with hybrid as a documented fallback for user-generated tables only.
- The NSE/BSE licence question blocks any cloud copy of market data regardless of size.

## Owner decisions (draft)
1. Accept stay-local, or fund a paid tier (Pro 8 GB) for evaluation.
2. Legal position on storing NSE/BSE data in a third-party cloud.
3. Whether to document the hybrid fallback for user-data tables.

## Verification
- Every number in the reports traces to a saved query output file.
- `git status` shows only new files under `audit-evidence/supabase-feasibility/` and the dashboard. No DB writes occurred (queries run with `default_transaction_read_only=on`).
