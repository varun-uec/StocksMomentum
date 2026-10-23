"""Builds the MF ingestion and analytics graphs across contexts; the CLI and the app share them.

Cross-context wiring lives here, at the composition level, so no context reaches
into another context's adapters (A3 §5.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_common.database import Database
from wickstreet.analytics.application.research import ComputeSnapshot, Research
from wickstreet.analytics.infrastructure.snapshots import SqlSnapshotStore
from wickstreet.config import WickstreetSettings
from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.infrastructure.register import SqlRightsRegister
from wickstreet.mf_data.application.ingest import (
    Backfill,
    CrossCheck,
    DailyRefresh,
    ImportArchive,
    ImportRates,
    IngestNavDay,
    IngestSchemeMaster,
    Reparse,
)
from wickstreet.mf_data.infrastructure.amfi import AmfiAdapter
from wickstreet.mf_data.infrastructure.mfapi import MfapiAdapter
from wickstreet.mf_data.infrastructure.raw_store import FileRawStore
from wickstreet.mf_data.infrastructure.rbi import RbiAdapter
from wickstreet.mf_data.infrastructure.reader import SqlMfReader
from wickstreet.mf_data.infrastructure.store import SqlMfStore
from wickstreet.mf_data.infrastructure.tigzig import TigzigAdapter


@dataclass(frozen=True)
class Ingestion:
    """The MF ingestion use cases over the source adapters and one store."""

    store: SqlMfStore
    sources: tuple[AmfiAdapter, TigzigAdapter, MfapiAdapter]
    backfill: Backfill
    refresh: DailyRefresh
    archive: ImportArchive
    crosscheck: CrossCheck
    reparse: Reparse
    rates: ImportRates

    async def aclose(self) -> None:
        """Close every adapter's HTTP client."""
        for source in self.sources:
            await source.aclose()


def build_ingestion(settings: WickstreetSettings, database: Database) -> Ingestion:
    """Wire the sources, the raw store, the MF store and the rights gate for the mode."""
    rights = RightsGate(SqlRightsRegister(database, settings.mode))
    interval = settings.http_min_interval_seconds
    timeout = settings.http_timeout_seconds
    attempts = settings.http_max_attempts
    raw_dir = Path(settings.raw_dir).expanduser()
    amfi = AmfiAdapter(
        min_interval_seconds=interval, timeout_seconds=timeout, max_attempts=attempts
    )
    tigzig = TigzigAdapter(
        work_dir=raw_dir / "tigzig" / "work",
        min_interval_seconds=interval,
        timeout_seconds=timeout,
        max_attempts=attempts,
    )
    mfapi = MfapiAdapter(
        min_interval_seconds=interval, timeout_seconds=timeout, max_attempts=attempts
    )
    store = SqlMfStore(database)
    raw_store = FileRawStore(raw_dir)
    day = IngestNavDay(amfi, store, raw_store, rights, settings.nav_jump_threshold)
    master = IngestSchemeMaster(amfi, store, raw_store, rights)
    archive_master = IngestSchemeMaster(tigzig, store, raw_store, rights, fill_only=True)
    return Ingestion(
        store=store,
        sources=(amfi, tigzig, mfapi),
        backfill=Backfill(day, master, store, amfi, rights),
        refresh=DailyRefresh(day, master, store, settings.nav_lookback_days),
        archive=ImportArchive(
            tigzig, store, raw_store, rights, archive_master, settings.nav_jump_threshold
        ),
        crosscheck=CrossCheck(mfapi, store, raw_store, rights),
        reparse=Reparse(day, store),
        rates=ImportRates(RbiAdapter(), store, raw_store, rights),
    )


@dataclass(frozen=True)
class Analytics:
    """Snapshot computation and research reads over one reader and snapshot store."""

    compute: ComputeSnapshot
    research: Research


def build_analytics(settings: WickstreetSettings, database: Database) -> Analytics:
    """Wire the MF reader, the snapshot store and the rights gate for the mode."""
    rights = RightsGate(SqlRightsRegister(database, settings.mode))
    reader = SqlMfReader(database)
    snapshots = SqlSnapshotStore(database)
    return Analytics(
        compute=ComputeSnapshot(reader, snapshots, rights),
        research=Research(reader, snapshots, rights),
    )
