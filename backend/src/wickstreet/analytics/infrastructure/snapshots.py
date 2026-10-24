"""Stored metric snapshots, decoded once per process (MF-11).

A snapshot's payload never changes once stored, so the cache needs no invalidation.
Reads skip a retired snapshot: its row stays for audit, but it is never served.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import text

from platform_common.database import Database
from wickstreet.analytics.domain.snapshot import Encoded, Snapshot, decode

# ponytail: keeps every snapshot (~10 MB gzipped each); prune old ones when disk matters.
# ponytail: in-process cache of the two newest decoded snapshots; no Redis until SaaS.
_CACHE_SIZE = 2


class SqlSnapshotStore:
    """The ``metric_snapshot`` table as the runtime role."""

    def __init__(self, database: Database) -> None:
        """Store through ``database``."""
        self._database = database
        self._cache: dict[int, Snapshot] = {}

    async def exists(self, revision: int, method_version: int) -> bool:
        """Return whether the snapshot is stored."""
        async with self._database.engine.connect() as connection:
            found = await connection.scalar(
                text(
                    "SELECT 1 FROM wickstreet.metric_snapshot "
                    "WHERE revision_id = :r AND method_version = :m AND retired_at IS NULL"
                ),
                {"r": revision, "m": method_version},
            )
        return found is not None

    async def insert(
        self,
        revision: int,
        method_version: int,
        as_of: date,
        sources: Sequence[str],
        grant_ids: Sequence[int],
        encoded: Encoded,
    ) -> int | None:
        """Store a snapshot; ``None`` when another writer stored it first."""
        async with self._database.engine.begin() as connection:
            result = await connection.execute(
                text(
                    "INSERT INTO wickstreet.metric_snapshot (revision_id, method_version, as_of, "
                    "funds, sources, grant_ids, payload_sha256, payload) "
                    "VALUES (:r, :m, :as_of, :funds, :sources, :grants, :sha, :payload) "
                    "ON CONFLICT (revision_id, method_version) WHERE retired_at IS NULL "
                    "DO NOTHING RETURNING id"
                ),
                {
                    "r": revision,
                    "m": method_version,
                    "as_of": as_of,
                    "funds": encoded.funds,
                    "sources": sorted(sources),
                    "grants": list(grant_ids),
                    "sha": encoded.sha256,
                    "payload": encoded.payload,
                },
            )
            row = result.first()
        return None if row is None else int(row[0])

    async def find(self, revision: int | None, method_version: int) -> Snapshot | None:
        """Return the snapshot at ``revision``, or the latest when it is ``None``."""
        where = "retired_at IS NULL AND method_version = :m"
        if revision is not None:
            where += " AND revision_id = :r"
        async with self._database.engine.connect() as connection:
            snapshot_id = await connection.scalar(
                text(
                    f"SELECT id FROM wickstreet.metric_snapshot WHERE {where} "
                    "ORDER BY revision_id DESC LIMIT 1"
                ),
                {"m": method_version, "r": revision},
            )
            if snapshot_id is None:
                return None
            if snapshot_id in self._cache:
                return self._cache[snapshot_id]
            payload = await connection.scalar(
                text("SELECT payload FROM wickstreet.metric_snapshot WHERE id = :id"),
                {"id": snapshot_id},
            )
        snapshot = decode(snapshot_id, payload)
        self._cache[snapshot_id] = snapshot
        for old in sorted(self._cache)[:-_CACHE_SIZE]:
            del self._cache[old]
        return snapshot


async def retire_snapshot(database: Database, snapshot_id: int, *, by: str, reason: str) -> bool:
    """Stop serving a snapshot and keep its row; ``False`` when unknown or retired.

    Runs as the owner login: the runtime role cannot update snapshots.
    """
    async with database.engine.begin() as connection:
        retired = await connection.scalar(
            text(
                "UPDATE wickstreet.metric_snapshot "
                "SET retired_at = now(), retired_by = :by, retired_reason = :reason "
                "WHERE id = :id AND retired_at IS NULL RETURNING id"
            ),
            {"id": snapshot_id, "by": by, "reason": reason},
        )
    return retired is not None
