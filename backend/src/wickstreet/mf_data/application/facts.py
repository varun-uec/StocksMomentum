"""Acquire and publish scheme facts from AMFI (doc 21 E1, E3).

Each dataset and period is one run and, when anything changed, one revision:

- the scheme list (ids and names), dated the day it is read;
- every scheme's summary document (SSD), read in one pass and dated that day;
- one month of daily TER, stored as change points;
- fund performance against the benchmark on one NAV date;
- index-fund tracking error on one NAV date.

Rights come first, as for NAVs: retrieval before a fetch, storage before a write.
A fact source joins rows to scheme ids from the stored list, so the list runs first.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.domain.rights import RightsDeniedError, Use
from wickstreet.mf_data.application.ingest import SETTLED, Outcome
from wickstreet.mf_data.domain.facts import compact, nav_index, scheme_keys
from wickstreet.mf_data.domain.model import (
    FACT_CONTRACT,
    MARKET_CAP,
    PERFORMANCE_DAY,
    SCHEME_LIST,
    SSD,
    TER_MONTH,
    TRACKING_ERROR_DAY,
    Fact,
    RawFile,
    SchemeFacts,
    SchemeRef,
)
from wickstreet.mf_data.domain.ports import (
    FactSource,
    MfStore,
    Provenance,
    RawStore,
    SourceError,
    SourceLayoutError,
)

Progress = Callable[[int, int], None]
RECENT_DAYS = 30
RECENT = timedelta(days=RECENT_DAYS)


class IngestFacts:
    """The scheme-fact runs over one source, store and rights gate."""

    def __init__(
        self, source: FactSource, store: MfStore, raw_store: RawStore, rights: RightsGate
    ) -> None:
        """Ingest ``source`` facts into ``store``, under ``rights``."""
        self._source = source
        self._store = store
        self._raw_store = raw_store
        self._rights = rights

    async def _grant(self, run_id: int, use: Use) -> int:
        try:
            return (await self._rights.require(self._source.name, use)).id
        except RightsDeniedError as exc:
            await self._store.close_run(run_id, "denied", error=str(exc))
            raise

    async def _run(
        self,
        dataset: str,
        start: date,
        end: date,
        fetch: Callable[[], Awaitable[RawFile]],
        parse: Callable[[RawFile], tuple[SchemeFacts, list[SchemeRef]]],
        *,
        refetch: bool,
    ) -> Outcome:
        run = await self._store.open_run(self._source.name, dataset, start, end)
        if run.status in SETTLED and not refetch:
            return Outcome(end, "skipped")
        retrieval = await self._grant(run.id, Use.AUTOMATED_RETRIEVAL)
        try:
            raw = await fetch()
        except SourceError as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(end, "failed", error=str(exc))
        path = self._raw_store.save(self._source.name, dataset, end, raw)
        if raw.sha256 == run.raw_sha256:
            await self._store.close_run(run.id, "unchanged", raw_sha256=raw.sha256)
            return Outcome(end, "unchanged")
        try:
            found, schemes = parse(raw)
        except SourceLayoutError as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(end, "failed", error=str(exc))
        storage = await self._grant(run.id, Use.STORAGE)
        provenance = Provenance(
            url=raw.url,
            fetched_at_iso=raw.fetched_at.isoformat(),
            raw_sha256=raw.sha256,
            raw_path=path,
            adapter_version=self._source.adapter_version,
            contract=FACT_CONTRACT,
            retrieval_grant_id=retrieval,
            storage_grant_id=storage,
        )
        published = await self._store.publish_facts(run.id, found, provenance, schemes)
        return Outcome(
            end,
            "published" if published.revision is not None else "unchanged",
            rows=len(found.facts) + len(schemes),
            inserted=published.inserted,
            superseded=published.superseded,
            anomalies=found.unmatched,
            revision=published.revision,
        )

    async def schemes(self, today: date, *, refetch: bool = False) -> Outcome:
        """Read every scheme id and name."""
        return await self._run(
            SCHEME_LIST,
            today,
            today,
            self._source.scheme_list,
            lambda raw: (SchemeFacts([]), self._source.parse_scheme_list(raw)),
            refetch=refetch,
        )

    async def ssds(
        self,
        today: date,
        *,
        refetch: bool = False,
        missing: bool = False,
        progress: Progress | None = None,
        stored: RawFile | None = None,
    ) -> Outcome:
        """Read the summary document of each listed scheme with a recent NAV, in one pass.

        A scheme counts as recent when its name matches the master name of a plan-option
        with a NAV in the last ``RECENT_DAYS``; closed series would take hours to read.
        With ``missing`` only schemes that have no stored SSD are read. ``stored`` is a
        combined file kept from an earlier pass; it is published without a fetch.
        """
        listed, codes = await self._store.scheme_keys()
        active = {compact(n) for n in await self._store.active_scheme_names(today - RECENT)}
        listed = [scheme for scheme in listed if compact(scheme.name) in active]
        if missing:
            # Only schemes with no stored SSD yet; the day's run is read again.
            listed = [scheme for scheme in listed if scheme.sd_id not in codes]
            refetch = True

        async def fetch() -> RawFile:
            if stored is not None:
                return stored
            found: dict[str, str] = {}
            url = ""
            for done, scheme in enumerate(listed, 1):
                raw = await self._source.ssd(scheme.sd_id)
                if raw is not None:
                    found[str(scheme.sd_id)] = raw.content.decode("utf-8-sig", "replace")
                    url = raw.url
                if progress is not None:
                    progress(done, len(listed))
            content = json.dumps(found, sort_keys=True).encode()
            return RawFile(url.rsplit("/", 1)[0] + "/SSD_*.xml", datetime.now(UTC), content)

        def parse(raw: RawFile) -> tuple[SchemeFacts, list[SchemeRef]]:
            documents = json.loads(raw.content)
            facts: list[Fact] = []
            isins: dict[str, int] = {}
            for sd_id, xml in sorted(documents.items(), key=lambda kv: int(kv[0])):
                try:
                    one = self._source.parse_ssd(
                        RawFile(raw.url, raw.fetched_at, xml.encode()), int(sd_id), today
                    )
                except SourceLayoutError:
                    continue
                facts.extend(one.facts)
                isins |= one.isins
            return SchemeFacts(facts, isins, unmatched=len(listed) - len(documents)), []

        return await self._run(SSD, today, today, fetch, parse, refetch=refetch)

    async def _keys(self) -> tuple[dict[str, int], dict[str, int]]:
        listed, codes = await self._store.scheme_keys()
        return scheme_keys(listed, codes)

    async def ter(self, month: date, *, refetch: bool = False) -> Outcome:
        """Read one month of daily TER (``month`` is the first of the month)."""
        codes, names = await self._keys()
        end = _month_end(month)
        return await self._run(
            TER_MONTH,
            month,
            end,
            lambda: self._source.ter_month(month),
            lambda raw: (self._source.parse_ter(raw, codes, names), []),
            refetch=refetch,
        )

    async def performance(
        self, day: date, *, closed_ended: bool = False, refetch: bool = False
    ) -> Outcome:
        """Read fund performance on the NAV date ``day``."""
        _, names = await self._keys()
        navs = nav_index(await self._store.scheme_navs(day))
        return await self._run(
            PERFORMANCE_DAY,
            day,
            day,
            lambda: self._source.performance(day, closed_ended=closed_ended),
            lambda raw: (self._source.parse_performance(raw, day, names, navs), []),
            refetch=refetch,
        )

    async def market_caps(self, period_end: date, *, refetch: bool = False) -> Outcome:
        """Read AMFI's market-cap list for the half-year ending ``period_end``."""
        run = await self._store.open_run(self._source.name, MARKET_CAP, period_end, period_end)
        if run.status in SETTLED and not refetch:
            return Outcome(period_end, "skipped")
        retrieval = await self._grant(run.id, Use.AUTOMATED_RETRIEVAL)
        try:
            raw = await self._source.market_caps(period_end)
        except SourceError as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(period_end, "failed", error=str(exc))
        if raw is None:
            await self._store.close_run(run.id, "unavailable")
            return Outcome(period_end, "unavailable")
        try:
            found = self._source.parse_market_caps(raw)
        except SourceLayoutError as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(period_end, "failed", error=str(exc))
        storage = await self._grant(run.id, Use.STORAGE)
        path = self._raw_store.save(self._source.name, MARKET_CAP, period_end, raw)
        provenance = Provenance(
            url=raw.url,
            fetched_at_iso=raw.fetched_at.isoformat(),
            raw_sha256=raw.sha256,
            raw_path=path,
            adapter_version=self._source.adapter_version,
            contract=FACT_CONTRACT,
            retrieval_grant_id=retrieval,
            storage_grant_id=storage,
        )
        published = await self._store.publish_market_caps(run.id, found, provenance)
        return Outcome(
            period_end,
            "published" if published.revision is not None else "unchanged",
            rows=len(found),
            inserted=published.inserted,
            superseded=published.superseded,
            revision=published.revision,
        )

    async def tracking_error(self, day: date, *, refetch: bool = False) -> Outcome:
        """Read index-fund tracking error on the NAV date ``day``."""
        _, names = await self._keys()
        return await self._run(
            TRACKING_ERROR_DAY,
            day,
            day,
            lambda: self._source.tracking_error(day),
            lambda raw: (self._source.parse_tracking_error(raw, day, names), []),
            refetch=refetch,
        )


def _month_end(month: date) -> date:
    following = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return date.fromordinal(following.toordinal() - 1)
