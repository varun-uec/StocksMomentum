# Wickstreet MF data recovery

This runbook covers PostgreSQL restoration, raw-file recovery and source reacquisition. See [as-built data architecture](../current/mf-data-architecture.md) and [source runbooks](mf-source-runbooks.md) for source details and CLI syntax.

## Recovery set and boundaries

Keep these together, outside the repository:

1. PostgreSQL custom-format dump. It includes `wickstreet` source data, rights rows, revisions, publication pointer, snapshots and tenant-owned normalized portfolio data, as well as the other application schema in the shared database.
2. A copy of the configured `WICKSTREET_RAW_DIR` tree. Database revisions store absolute raw paths and SHA-256 values; without the matching raw tree, reads still work but parser replays cannot.
3. The repository revision and the local environment/role secrets from the secure store. `pg_dump` does not include cluster roles or their passwords. Never put `.env`, URLs or credential files in Git.

The raw tree contains public source payloads, not CAS files. The CAS original/password is not stored by Wickstreet; a DB backup does contain the user's normalized portfolio transactions and should be protected accordingly.

A full DB loss cannot be rebuilt from the raw directory by a single CLI importer: the current CLI uses raw files for corrections while matching ingestion runs/revisions still exist. For a new empty schema, use the source reacquisition sequence below. Do not claim raw-only replay for a dataset without an explicit reparse command.

## Backup

Choose a private backup directory outside the repository. The Docker DB container supplies `POSTGRES_USER` and `POSTGRES_DB`. Set `RAW_DIR` to the host path configured in Compose (`WICKSTREET_RAW_DIR`, default `~/.wickstreet/raw`); Compose's `.env` file is not automatically loaded into the interactive shell.

```bash
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "$BACKUP_DIR/momentum25-$STAMP.dump"
RAW_DIR="$HOME/.wickstreet/raw" # set this to the Compose WICKSTREET_RAW_DIR if customized
mkdir -p "$RAW_DIR"
tar -C "$(dirname "$RAW_DIR")" -czf "$BACKUP_DIR/wickstreet-raw-$STAMP.tar.gz" "$(basename "$RAW_DIR")"
docker compose exec -T db pg_restore --list - \
  < "$BACKUP_DIR/momentum25-$STAMP.dump" > /dev/null
```

If `WICKSTREET_RAW_DIR` is customized, archive that exact directory instead of the default. Retain raw archive and SQL dump from the same backup interval; raw files are immutable/write-once, so extra unreferenced raw files are harmless. Store database role secrets through the deployment's secure secret store.

## Restore into a separate database first

The following uses a new target database so the source DB remains intact. It was exercised with an ephemeral PostgreSQL 16 container and no mounted Docker volume.

1. Start/confirm the PostgreSQL service and ensure the cluster roles named in the dump exist. On the original cluster they already exist. On a new cluster recreate them from the secure deployment configuration before `pg_restore`; the database dump does not create roles:

   ```bash
   docker compose up -d db
   docker compose run --rm --entrypoint wickstreet wickstreet-migrate db-roles
   ```

   `db-roles` uses the configured admin, owner and app URLs; it does not apply migrations or touch the dump.
2. Create a fresh target DB owned by the configured database administrator. Substitute only the target database name; use credentials from local environment, never a committed value:

   ```bash
   docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" wickstreet_restore_test'
   ```

3. Restore the custom dump. This is destructive only to the newly-created target DB:

   ```bash
   docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d wickstreet_restore_test --exit-on-error' \
     < "$BACKUP_DIR/momentum25-latest.dump"
   ```

4. Extract the raw archive back to its configured absolute path so every stored `raw_path` resolves. Keep the source/target database and raw tree paired:

   ```bash
   RAW_DIR="$HOME/.wickstreet/raw" # same configured host path used for backup
   tar -C "$(dirname "$RAW_DIR")" -xzf "$BACKUP_DIR/wickstreet-raw-latest.tar.gz"
   ```

   If restoring to a different path, update `WICKSTREET_RAW_DIR` in the local Compose environment and use a recovery script to relocate paths in revision rows; the present code does not rewrite absolute raw paths automatically. Prefer restoring to the original absolute path.

5. Point a temporary CLI environment at `wickstreet_restore_test` using the configured runtime/owner role credentials, but set the database name in both URLs to `wickstreet_restore_test` and the Compose hostname to `db`. Then run the read-only report and a raw replay for a retained date:

   ```bash
   docker compose run --rm \
     -e WICKSTREET_DATABASE_URL="$RESTORE_APP_DATABASE_URL" \
     -e WICKSTREET_MIGRATION_DATABASE_URL="$RESTORE_OWNER_DATABASE_URL" \
     api wickstreet mf report
   # Find one retained AMFI NAV date whose source file is present in the raw archive.
   printf '%s\n' "SELECT r.period_start FROM wickstreet.ingestion_run AS r JOIN wickstreet.revision AS v ON v.id = r.revision_id WHERE r.source = 'amfi' AND r.dataset = 'nav-v1' ORDER BY r.period_start DESC LIMIT 1;" \
     | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d wickstreet_restore_test -At'
   # Copy the returned date into REPLAY_DAY.
   REPLAY_DAY=YYYY-MM-DD
   docker compose run --rm \
     -e WICKSTREET_DATABASE_URL="$RESTORE_APP_DATABASE_URL" \
     -e WICKSTREET_MIGRATION_DATABASE_URL="$RESTORE_OWNER_DATABASE_URL" \
     api wickstreet mf reparse --start "$REPLAY_DAY" --end "$REPLAY_DAY"
   ```

   Choose dates known to have raw files. Expect zero failures, `unchanged` for a raw file parsed identically, or a new revision/snapshot if the parser now produces a correction. A SHA mismatch or missing path is a failed verification; recover the matching raw archive before serving the restored system.

6. Compare table counts and newest published revision with the source backup before changing the app's database configuration. Switch configuration only after all checks pass. The migration version table should remain at `0010_snapshot_retirement` for this repository state.

The restore test ran with synthetic NAV rows only: source report returned 2 current NAV rows on one date, no missing dates or failed runs; `mf reparse` on the restored raw returned `unchanged`, 2 rows, 0 inserted, 0 superseded. It verified PostgreSQL dump/restore, app-role report access, and the stored AMFI raw-path replay. It did not test live provider access or real-money portfolio data.

## Fresh database: reacquire source data

Use when no usable DB dump is available. This sequence reconstructs from provider data and operator files; it does not recover old revision history or exact former raw hashes.

1. Start the DB and apply the separate Wickstreet and Momentum25 migrations:

   ```bash
   docker compose up -d db redis
   make mf-migrate
   make migrate
   ```

   `make mf-migrate` creates/updates `wickstreet_owner` and `wickstreet_app` then applies Wickstreet migrations. Configure role passwords in the local Compose environment before it runs.

2. Verify/record rights in the local DB with the owner login (owner decisions are not provider licences). Grant retrieval/storage for intended sources, and `derived_metrics`/`display` for sources that will appear in the product.
3. Reacquire the NAV foundation in dependency order; default dates are the last ten years plus seven days through yesterday:

   ```bash
   docker compose run --rm api wickstreet mf backfill
   docker compose run --rm api wickstreet mf archive
   ```

   To restore the full currently advertised archive coverage, explicitly widen both date ranges (the normal default is ten years, not 2006):

   ```bash
   docker compose run --rm api wickstreet mf backfill --start 2006-04-01 --end 2026-10-23
   docker compose run --rm api wickstreet mf archive --start 2006-04-01 --end 2026-10-23
   ```

   The AMFI command records its available date range; the TigZig command requires a stored AMFI cutoff. Review each summary for failed/unavailable runs and conflicts.

4. Load AMFI fact dependencies: `schemes` before SSD, then TER, performance and tracking error; IDCW and market caps can follow once source IDs/NAVs exist. Some endpoints only retain current disclosures, so a new rebuild cannot recreate old versions that their source no longer serves.
5. Load monthly AMC holdings for the desired historical span. If automated retrieval is unavailable, use the registered manual-import route in the [AMC runbook](mf-source-runbooks.md#manual-portfolio-import), confirm the source has its storage-only owner decision, then import the owner-downloaded disclosure with its true source URL. Preserve the file for raw recovery and independently verify a source's first layout before classifying it as operational. Load RBI handbook and auction HTML files manually through `mf import-rates`.
6. Run `mf report`, review per-dataset ingestion statuses, and compute `mf metrics`. Each successful CLI publication normally computes the snapshot automatically; `mf metrics` is safe to run again and is a no-op if current.
7. Start the app only after a clean report and a current snapshot. The Compose API mounts the host raw directory; confirm `WICKSTREET_RAW_DIR` points to the same path used by CLI jobs.

See [MF source runbooks](mf-source-runbooks.md) for exact provider endpoints, layouts, date semantics, AMC format quirks and import commands.

## Failure recovery

| Symptom | Action |
|---|---|
| `failed` ingestion run | Inspect CLI error and run row, retain raw file. Fix transient network/temporary provider failure and rerun the same command; unsettled failures retry. A parser/layout failure requires adapter update and fixture test. |
| `unavailable` date/month | Expected for source gaps or not-yet-published periods. NAV refresh retries its seven-day lookback; for older periods use the provider-specific refetch/reacquisition path. |
| Raw SHA-256 mismatch | Do not reparse modified bytes. Restore the exact compressed raw file from the paired archive, confirm the decompressed content hash against `revision.raw_sha256`, then retry. |
| Missing raw file | Published database data remain readable; parser-only correction is unavailable. Restore the paired raw backup or reacquire the provider file. |
| Schema/layout changed | Keep provider response in the external raw store, compare with adapter expectations, add/update parser fixture and runbook, bump adapter version. Reprocess only through supported command in architecture table. |
| New data revision but no metrics snapshot | Check `derived_metrics` grants and DB logs; run `wickstreet mf metrics` after granting rights. Do not delete old revision/snapshot rows to “fix” a missing snapshot. |
| App missed daily slot | In-process scheduler catches up at startup if due. Otherwise run `wickstreet mf refresh`; it uses durable date checkpoints and re-reads the lookback. |

Do not use `docker compose down -v` as a recovery step: it deletes the Compose PostgreSQL and Redis volumes.
