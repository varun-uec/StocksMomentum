"""Acquire, validate and publish MF data (ADR-017 MF-6 to MF-10, ADR-022 §2.12).

One NAV date is one run and, when anything changed, one revision. The backfill and
the daily refresh are sequences of those runs under one lock, so they are resumable:
a settled date is skipped unless the caller asks to re-read it. An archive import
is one run per calendar month, under the same lock (ADR-023 U11).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.domain.rights import RightsDeniedError, Use
from wickstreet.mf_data.domain.model import (
    AMFI,
    ARCHIVE_TOLERANCE,
    NAV_CONTRACT,
    REFRESH,
    SCHEME_CONTRACT,
    Anomaly,
    NavRecord,
    RawFile,
)
from wickstreet.mf_data.domain.ports import (
    ArchiveSource,
    MfStore,
    NavSource,
    Provenance,
    RawStore,
    ReferenceSource,
    SchemeSource,
    SourceError,
    SourceLayoutError,
)
from wickstreet.mf_data.domain.validation import (
    BlockingError,
    Comparison,
    check_nav_day,
    check_scheme_master,
    compare_series,
    flag_anomalies,
)

# A run in one of these states is not re-read unless the caller asks.
SETTLED = frozenset({"published", "unchanged", "unavailable"})


class IngestionBusyError(Exception):
    """Another runner holds the ingestion lock."""


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one run did."""

    period: date
    status: str
    rows: int = 0
    inserted: int = 0
    superseded: int = 0
    anomalies: int = 0
    revision: int | None = None
    error: str | None = None
    conflicts: int = 0


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


class _Acquisition[S: SchemeSource]:
    """Shared steps: rights before fetch and before write, raw file kept."""

    def __init__(self, source: S, store: MfStore, raw_store: RawStore, rights: RightsGate):
        self._source = source
        self._store = store
        self._raw_store = raw_store
        self._rights = rights

    async def _require(self, run_id: int, use: Use) -> int:
        try:
            return (await self._rights.require(self._source.name, use)).id
        except RightsDeniedError as exc:
            await self._store.close_run(run_id, "denied", error=str(exc))
            raise

    def _provenance(
        self, raw: RawFile, path: str, contract: str, retrieval: int, storage: int
    ) -> Provenance:
        return Provenance(
            url=raw.url,
            fetched_at_iso=raw.fetched_at.isoformat(),
            raw_sha256=raw.sha256,
            raw_path=path,
            adapter_version=self._source.adapter_version,
            contract=contract,
            retrieval_grant_id=retrieval,
            storage_grant_id=storage,
        )


class IngestNavDay(_Acquisition[NavSource]):
    """Fetch, validate and publish every NAV filed for one date."""

    def __init__(
        self,
        source: NavSource,
        store: MfStore,
        raw_store: RawStore,
        rights: RightsGate,
        jump_threshold: Decimal,
    ) -> None:
        """Create the use case; ``jump_threshold`` is the anomaly limit (MF-8)."""
        super().__init__(source, store, raw_store, rights)
        self._jump_threshold = jump_threshold

    async def execute(self, day: date, *, refetch: bool = False) -> Outcome:
        """Ingest ``day``. ``refetch`` re-reads a settled date to catch corrections (MF-7)."""
        run = await self._store.open_run(self._source.name, NAV_CONTRACT, day, day)
        if run.status in SETTLED and not refetch:
            return Outcome(day, "skipped")
        retrieval = await self._require(run.id, Use.AUTOMATED_RETRIEVAL)
        try:
            raw = await self._source.nav_day(day)
        except SourceError as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(day, "failed", error=str(exc))
        if raw is None:
            await self._store.close_run(run.id, "unavailable")
            return Outcome(day, "unavailable")
        path = self._raw_store.save(self._source.name, NAV_CONTRACT, day, raw)
        if raw.sha256 == run.raw_sha256:
            await self._store.close_run(run.id, "unchanged", raw_sha256=raw.sha256)
            return Outcome(day, "unchanged")
        return await self._publish(run.id, day, raw, path, retrieval)

    async def reparse(self, day: date) -> Outcome:
        """Re-derive a published date from its kept raw file with the current adapter.

        For a parser fix: a changed value becomes a new revision under the new adapter
        version, and the old value stays as history (MF-5, MF-9). Nothing is fetched.
        """
        if await self._store.run_status(self._source.name, NAV_CONTRACT, day) is None:
            return Outcome(day, "skipped")
        run = await self._store.open_run(self._source.name, NAV_CONTRACT, day, day)
        stored = await self._store.stored_raw(run.id)
        if stored is None:
            return Outcome(day, "skipped")
        retrieval = await self._require(run.id, Use.AUTOMATED_RETRIEVAL)
        raw = RawFile(stored.url, stored.fetched_at, self._raw_store.load(stored.path))
        if raw.sha256 != stored.sha256:
            error = f"Raw file {stored.path} does not match its recorded SHA-256."
            await self._store.close_run(run.id, "failed", error=error)
            return Outcome(day, "failed", error=error)
        return await self._publish(run.id, day, raw, stored.path, retrieval)

    async def _publish(
        self, run_id: int, day: date, raw: RawFile, path: str, retrieval: int
    ) -> Outcome:
        try:
            records = check_nav_day(self._source.parse_nav(raw), day)
        except (SourceLayoutError, BlockingError) as exc:
            await self._store.close_run(run_id, "failed", error=str(exc))
            return Outcome(day, "failed", error=str(exc))
        storage = await self._require(run_id, Use.STORAGE)
        flags = flag_anomalies(records, await self._store.previous_navs(day), self._jump_threshold)
        anomalies = {(code, day): flag for code, flag in flags.items()}
        published = await self._store.publish_navs(
            run_id,
            records,
            anomalies,
            self._provenance(raw, path, NAV_CONTRACT, retrieval, storage),
        )
        return Outcome(
            day,
            "published" if published.revision is not None else "unchanged",
            rows=len(records),
            inserted=published.inserted,
            superseded=published.superseded,
            anomalies=len(anomalies),
            revision=published.revision,
        )


class IngestSchemeMaster(_Acquisition[SchemeSource]):
    """Fetch the scheme master and record changed attributes as of ``snapshot``."""

    def __init__(
        self,
        source: SchemeSource,
        store: MfStore,
        raw_store: RawStore,
        rights: RightsGate,
        *,
        fill_only: bool = False,
    ) -> None:
        """Create the use case; ``fill_only`` writes only codes with no master row yet."""
        super().__init__(source, store, raw_store, rights)
        self._fill_only = fill_only

    async def execute(self, snapshot: date, *, refetch: bool = False) -> Outcome:
        """Ingest the master for the ``snapshot`` date."""
        run = await self._store.open_run(self._source.name, SCHEME_CONTRACT, snapshot, snapshot)
        if run.status in SETTLED and not refetch:
            return Outcome(snapshot, "skipped")
        retrieval = await self._require(run.id, Use.AUTOMATED_RETRIEVAL)
        try:
            raw = await self._source.scheme_master()
        except SourceError as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(snapshot, "failed", error=str(exc))
        path = self._raw_store.save(self._source.name, SCHEME_CONTRACT, snapshot, raw)
        if raw.sha256 == run.raw_sha256:
            await self._store.close_run(run.id, "unchanged", raw_sha256=raw.sha256)
            return Outcome(snapshot, "unchanged")
        try:
            records = check_scheme_master(self._source.parse_schemes(raw))
        except (SourceLayoutError, BlockingError) as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(snapshot, "failed", error=str(exc))
        storage = await self._require(run.id, Use.STORAGE)
        published = await self._store.publish_schemes(
            run.id,
            snapshot,
            records,
            self._provenance(raw, path, SCHEME_CONTRACT, retrieval, storage),
            fill_only=self._fill_only,
        )
        return Outcome(
            snapshot,
            "published" if published.revision is not None else "unchanged",
            rows=len(records),
            inserted=published.inserted,
            superseded=published.superseded,
            revision=published.revision,
        )


@dataclass
class Summary:
    """Totals over a sequence of runs."""

    statuses: Counter[str] = field(default_factory=Counter)
    rows: int = 0
    inserted: int = 0
    superseded: int = 0
    anomalies: int = 0
    conflicts: int = 0
    failures: list[Outcome] = field(default_factory=list)
    first_served: date | None = None

    def add(self, outcome: Outcome) -> None:
        """Count one run."""
        self.statuses[outcome.status] += 1
        self.rows += outcome.rows
        self.inserted += outcome.inserted
        self.superseded += outcome.superseded
        self.anomalies += outcome.anomalies
        self.conflicts += outcome.conflicts
        if outcome.status == "failed":
            self.failures.append(outcome)


Progress = Callable[[Outcome], None]


class Backfill:
    """Acquire history over a date range: the master first, then one run per date."""

    def __init__(
        self,
        days: IngestNavDay,
        master: IngestSchemeMaster,
        store: MfStore,
        source: NavSource,
        rights: RightsGate,
        *,
        max_consecutive_failures: int = 5,
    ) -> None:
        """Create the backfill; it stops after ``max_consecutive_failures`` failed dates."""
        self._days = days
        self._master = master
        self._store = store
        self._source = source
        self._rights = rights
        self._max_failures = max_consecutive_failures

    async def _first_served(self, start: date, end: date) -> date | None:
        """Find the earliest served date in ``[start, end]``, assuming service is contiguous.

        The source serves recent history only, so a binary search costs about a dozen
        requests instead of one per unserved date.
        """
        if await self._source.nav_day(end) is None:
            return None
        if await self._source.nav_day(start) is not None:
            return start
        low, high = start, end  # low is unserved, high is served
        while (high - low).days > 1:
            middle = low + (high - low) / 2
            if await self._source.nav_day(middle) is None:
                low = middle
            else:
                high = middle
        return high

    async def execute(
        self, start: date, end: date, today: date, progress: Progress | None = None
    ) -> Summary:
        """Backfill ``[start, end]``; dates already settled are skipped."""
        summary = Summary()
        async with self._store.exclusive() as held:
            if not held:
                raise IngestionBusyError
            await self._rights.require(self._source.name, Use.AUTOMATED_RETRIEVAL)
            master = await self._master.execute(today)
            summary.add(master)
            if progress:
                progress(master)
            first = await self._first_served(start, end)
            summary.first_served = first
            if first is None or first > start:
                gap_end = end if first is None else first - timedelta(days=1)
                gap = await self._store.open_run(self._source.name, NAV_CONTRACT, start, gap_end)
                await self._store.close_run(gap.id, "unavailable")
            if first is None:
                return summary
            failures = 0
            for day in _days(first, end):
                outcome = await self._days.execute(day)
                summary.add(outcome)
                if progress:
                    progress(outcome)
                failures = failures + 1 if outcome.status == "failed" else 0
                if failures >= self._max_failures:
                    break
        return summary


class Reparse:
    """Re-derive stored dates from their raw files, under the ingestion lock."""

    def __init__(self, days: IngestNavDay, store: MfStore) -> None:
        """Create the use case over the per-date ingestion."""
        self._days = days
        self._store = store

    async def execute(self, start: date, end: date, progress: Progress | None = None) -> Summary:
        """Reparse every published date in ``[start, end]``, in date order."""
        summary = Summary()
        async with self._store.exclusive() as held:
            if not held:
                raise IngestionBusyError
            for day in _days(start, end):
                outcome = await self._days.reparse(day)
                summary.add(outcome)
                if progress:
                    progress(outcome)
        return summary


class DailyRefresh:
    """The 11:30 IST job: the master, then every date from the last one stored (ADR-022 §2.12).

    It re-reads a trailing look-back window, so late NAVs and corrections become new
    revisions; an unchanged file is a no-op. After downtime it starts from the day
    after the latest stored date instead.
    """

    def __init__(
        self, days: IngestNavDay, master: IngestSchemeMaster, store: MfStore, lookback_days: int
    ) -> None:
        """Create the refresh with its look-back window in days."""
        self._days = days
        self._master = master
        self._store = store
        self._lookback = timedelta(days=lookback_days)

    async def execute(self, today: date, progress: Progress | None = None) -> Summary:
        """Refresh up to yesterday; NAVs for ``today`` are not final until tonight."""
        summary = Summary()
        async with self._store.exclusive() as held:
            if not held:
                raise IngestionBusyError
            run = await self._store.open_run(AMFI, REFRESH, today, today)
            outcomes = [await self._master.execute(today, refetch=True)]
            start = today - self._lookback
            last = await self._store.last_nav_day()
            if last is not None and last + timedelta(days=1) < start:
                start = last + timedelta(days=1)
            for day in _days(start, today - timedelta(days=1)):
                outcomes.append(await self._days.execute(day, refetch=True))
            for outcome in outcomes:
                summary.add(outcome)
                if progress:
                    progress(outcome)
            failed = [f"{o.period}: {o.error}" for o in summary.failures]
            await self._store.close_run(
                run.id, "failed" if failed else "completed", error="; ".join(failed) or None
            )
        return summary


def _month_end(day: date) -> date:
    return (day.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)


class ImportArchive(_Acquisition[ArchiveSource]):
    """Publish a whole-history archive, one calendar month per run (ADR-023 U11).

    Before ``cutoff``, the first date the direct source serves, the archive is the
    source of record, so a later archive's different value supersedes. From
    ``cutoff`` on it only fills codes and dates the direct source lacks, and counts
    values that differ from the stored ones as conflicts. The direct source wins.
    """

    def __init__(
        self,
        source: ArchiveSource,
        store: MfStore,
        raw_store: RawStore,
        rights: RightsGate,
        master: IngestSchemeMaster,
        jump_threshold: Decimal,
    ) -> None:
        """Create the import; ``master`` ingests the archive's scheme master first."""
        super().__init__(source, store, raw_store, rights)
        self._master = master
        self._jump_threshold = jump_threshold

    async def execute(
        self,
        start: date,
        end: date,
        cutoff: date,
        today: date,
        progress: Progress | None = None,
        *,
        refetch: bool = False,
    ) -> Summary:
        """Import ``[start, end]``; settled months are skipped unless ``refetch``."""
        summary = Summary()

        def report(outcome: Outcome) -> None:
            summary.add(outcome)
            if progress:
                progress(outcome)

        async with self._store.exclusive() as held:
            if not held:
                raise IngestionBusyError
            await self._rights.require(self._source.name, Use.AUTOMATED_RETRIEVAL)
            report(await self._master.execute(today, refetch=refetch))
            raw = await self._source.archive()
            path = self._raw_store.save(self._source.name, NAV_CONTRACT, today, raw)
            batch: list[tuple[date, list[NavRecord]]] = []
            for day, records in self._source.parse_archive(raw, start, end):
                if batch and _segment(batch[0][0], cutoff) != _segment(day, cutoff):
                    report(await self._month(raw, path, batch, start, end, cutoff, refetch))
                    batch = []
                batch.append((day, records))
            if batch:
                report(await self._month(raw, path, batch, start, end, cutoff, refetch))
        return summary

    async def _month(
        self,
        raw: RawFile,
        path: str,
        batch: list[tuple[date, list[NavRecord]]],
        start: date,
        end: date,
        cutoff: date,
        refetch: bool,
    ) -> Outcome:
        first = batch[0][0]
        fill = first >= cutoff
        if fill:
            period = (max(first.replace(day=1), start, cutoff), min(_month_end(first), end))
        else:
            period = (
                max(first.replace(day=1), start),
                min(_month_end(first), end, cutoff - timedelta(days=1)),
            )
        run = await self._store.open_run(self._source.name, NAV_CONTRACT, *period)
        if run.status in SETTLED and not refetch:
            return Outcome(period[0], "skipped")
        # A fill month's conflicts depend on the stored values too, so it is always rechecked.
        if raw.sha256 == run.raw_sha256 and not fill:
            await self._store.close_run(run.id, "unchanged", raw_sha256=raw.sha256)
            return Outcome(period[0], "unchanged")
        retrieval = await self._require(run.id, Use.AUTOMATED_RETRIEVAL)
        try:
            days = [(day, check_nav_day(records, day)) for day, records in batch]
        except BlockingError as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(period[0], "failed", error=str(exc))
        storage = await self._require(run.id, Use.STORAGE)
        # ponytail: in-month previous NAVs never expire, unlike previous_navs' 15-day window.
        latest = dict(await self._store.previous_navs(period[0]))
        anomalies: dict[tuple[str, date], Anomaly] = {}
        records: list[NavRecord] = []
        for day, rows in days:
            for code, flag in flag_anomalies(rows, latest, self._jump_threshold).items():
                anomalies[(code, day)] = flag
            latest.update({r.amfi_code: r.nav for r in rows if r.nav is not None and r.nav > 0})
            records.extend(rows)
        published = await self._store.publish_navs(
            run.id,
            records,
            anomalies,
            self._provenance(raw, path, NAV_CONTRACT, retrieval, storage),
            fill_only=fill,
        )
        return Outcome(
            period[0],
            "published" if published.revision is not None else "unchanged",
            rows=len(records),
            inserted=published.inserted,
            superseded=published.superseded,
            anomalies=len(anomalies),
            revision=published.revision,
            conflicts=published.conflicts,
        )


def _segment(day: date, cutoff: date) -> tuple[int, int, bool]:
    return day.year, day.month, day >= cutoff


class CrossCheck:
    """Compare stored NAVs with a reference source, code by code (ADR-023 U11).

    Nothing is published: the reference only measures the store. Its files are kept
    in the raw store, so every comparison can be repeated.
    """

    def __init__(
        self, reference: ReferenceSource, store: MfStore, raw_store: RawStore, rights: RightsGate
    ) -> None:
        """Create the check over one reference source."""
        self._reference = reference
        self._store = store
        self._raw_store = raw_store
        self._rights = rights

    async def execute(
        self, codes: Sequence[str], start: date, end: date, today: date
    ) -> list[Comparison]:
        """Compare each code over ``[start, end]``."""
        name = self._reference.name
        await self._rights.require(name, Use.AUTOMATED_RETRIEVAL)
        await self._rights.require(name, Use.STORAGE)
        results: list[Comparison] = []
        for code in codes:
            raw = await self._reference.history(code)
            self._raw_store.save(name, NAV_CONTRACT, today, raw)
            theirs = {
                day: nav
                for day, nav in self._reference.parse_history(raw).items()
                if start <= day <= end
            }
            ours = await self._store.current_navs(code, start, end)
            results.append(compare_series(code, ours, theirs, ARCHIVE_TOLERANCE))
        return results
