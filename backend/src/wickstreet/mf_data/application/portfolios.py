"""Acquire and publish monthly portfolio disclosures (doc 21 E4).

One AMC file is one run and, when any portfolio in it changed, one revision. A file
an AMC lists is fetched under the AMC's retrieval grant; a file a person downloaded
is imported under its storage grant alone. A file that gives no portfolio fails. From
an AMC whose layout is unverified, a portfolio that does not reconcile is held back.
Sheets join AMFI schemes by name, so the scheme list must be read first; a sheet filed
under a scheme's old name joins by the
sheet code the AMC's newest kept file gives that scheme.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.domain.rights import RightsDeniedError, Use
from wickstreet.mf_data.application.ingest import SETTLED, Outcome
from wickstreet.mf_data.domain.facts import scheme_keys
from wickstreet.mf_data.domain.model import HOLDINGS_CONTRACT, HOLDINGS_MONTH, Portfolios, RawFile
from wickstreet.mf_data.domain.ports import (
    MfStore,
    PortfolioSource,
    Provenance,
    RawStore,
    SourceError,
    SourceLayoutError,
)
from wickstreet.mf_data.domain.validation import RECONCILE_TOLERANCE, unreconciled


class IngestPortfolios:
    """Portfolio runs over the AMC sources, one store and the rights gate."""

    def __init__(
        self,
        sources: Mapping[str, PortfolioSource],
        store: MfStore,
        raw_store: RawStore,
        rights: RightsGate,
    ) -> None:
        """Ingest each source's files into ``store``, under ``rights``."""
        self._sources = sources
        self._store = store
        self._raw_store = raw_store
        self._rights = rights
        self._learnt: dict[str, dict[str, int]] = {}

    async def _grant(self, run_id: int, source: str, use: Use) -> int:
        try:
            return (await self._rights.require(source, use)).id
        except RightsDeniedError as exc:
            await self._store.close_run(run_id, "denied", error=str(exc))
            raise

    async def _publish(
        self,
        source: PortfolioSource,
        run_id: int,
        raw: RawFile,
        month_end: date,
        retrieval: int | None,
    ) -> Outcome:
        listed, amfi_codes = await self._store.scheme_keys()
        _, names = scheme_keys(listed, amfi_codes)
        try:
            found = source.parse_portfolios(raw, names, month_end, await self._codes(source, names))
            found = _trusted(source, raw, found)
        except SourceLayoutError as exc:
            await self._store.close_run(run_id, "failed", error=str(exc))
            return Outcome(month_end, "failed", error=str(exc))
        storage = await self._grant(run_id, source.name, Use.STORAGE)
        path = self._raw_store.save(source.name, HOLDINGS_MONTH, month_end, raw)
        provenance = Provenance(
            url=raw.url,
            fetched_at_iso=raw.fetched_at.isoformat(),
            raw_sha256=raw.sha256,
            raw_path=path,
            adapter_version=source.adapter_version,
            contract=HOLDINGS_CONTRACT,
            retrieval_grant_id=retrieval,
            storage_grant_id=storage,
        )
        published = await self._store.publish_portfolios(run_id, found, provenance)
        return Outcome(
            month_end,
            "published" if published.revision is not None else "unchanged",
            rows=len(found.holdings),
            inserted=published.inserted,
            superseded=published.superseded,
            anomalies=len(found.unmatched),
            revision=published.revision,
            error="; ".join(found.unmatched[:5]) or None,
        )

    async def _codes(self, source: PortfolioSource, names: Mapping[str, int]) -> dict[str, int]:
        """Sheet codes learnt from the AMC's newest kept file, where names are current."""
        newest = await self._store.latest_raw(source.name, HOLDINGS_MONTH)
        if newest is None:
            return {}
        if newest.path not in self._learnt:
            raw = RawFile(newest.url, newest.fetched_at, self._raw_store.load(newest.path))
            try:
                self._learnt[newest.path] = source.sheet_codes(raw, names)
            except SourceLayoutError:
                self._learnt[newest.path] = {}
        return self._learnt[newest.path]

    async def month(self, name: str, month_end: date, *, refetch: bool = False) -> Outcome:
        """Fetch and publish one AMC's file for ``month_end``."""
        source = self._sources[name]
        run = await self._store.open_run(name, HOLDINGS_MONTH, month_end, month_end)
        if run.status in SETTLED and not refetch:
            return Outcome(month_end, "skipped")
        retrieval = await self._grant(run.id, name, Use.AUTOMATED_RETRIEVAL)
        try:
            raw = await source.portfolio(month_end)
        except SourceError as exc:
            await self._store.close_run(run.id, "failed", error=str(exc))
            return Outcome(month_end, "failed", error=str(exc))
        if raw is None:
            await self._store.close_run(run.id, "unavailable")
            return Outcome(month_end, "unavailable")
        if raw.sha256 == run.raw_sha256:
            await self._store.close_run(run.id, "unchanged", raw_sha256=raw.sha256)
            return Outcome(month_end, "unchanged")
        return await self._publish(source, run.id, raw, month_end, retrieval)

    async def reparse(self, name: str, month_end: date) -> Outcome:
        """Re-derive a published month from its kept raw file with the current parser.

        For a parser fix: changed portfolios become a new revision and the old lines stay
        as history (MF-5). Nothing is fetched.
        """
        source = self._sources[name]
        if await self._store.run_status(name, HOLDINGS_MONTH, month_end) is None:
            return Outcome(month_end, "skipped")
        run = await self._store.open_run(name, HOLDINGS_MONTH, month_end, month_end)
        stored = await self._store.stored_raw(run.id)
        if stored is None:
            return Outcome(month_end, "skipped")
        raw = RawFile(stored.url, stored.fetched_at, self._raw_store.load(stored.path))
        if raw.sha256 != stored.sha256:
            error = f"Raw file {stored.path} does not match its recorded SHA-256."
            await self._store.close_run(run.id, "failed", error=error)
            return Outcome(month_end, "failed", error=error)
        # A reparse fetches nothing: it keeps the retrieval grant the file came under,
        # or none for a file a person imported.
        return await self._publish(source, run.id, raw, month_end, stored.retrieval_grant_id)

    async def import_file(self, name: str, raw: RawFile, month_end: date) -> Outcome:
        """Publish a file a person downloaded from AMC ``name``; Wickstreet fetched nothing."""
        source = self._sources.get(name)
        if source is None:
            known = ", ".join(sorted(self._sources))
            return Outcome(month_end, "failed", error=f"Unknown AMC {name!r}. Known: {known}.")
        run = await self._store.open_run(name, HOLDINGS_MONTH, month_end, month_end)
        if raw.sha256 == run.raw_sha256:
            return Outcome(month_end, "unchanged")
        return await self._publish(source, run.id, raw, month_end, None)


def _trusted(source: PortfolioSource, raw: RawFile, found: Portfolios) -> Portfolios:
    """The portfolios of ``found`` that may be stored; :class:`SourceLayoutError` if none.

    A file must give at least one portfolio. From an AMC whose layout is unverified, a
    portfolio that does not reconcile is held back and listed: a line read wrongly
    shows in its total.
    """
    if not found.holdings:
        unmatched = found.unmatched[:5]
        named = f" Names that joined no scheme: {', '.join(unmatched)}." if unmatched else ""
        raise SourceLayoutError(
            f"No portfolio in {raw.url} joined an AMFI scheme. A sheet needs an ISIN "
            "column and a '% to net assets' header in its first 60 rows, with the scheme's "
            f"name above the header.{named} If the file is a month-end disclosure, its "
            "layout needs a parser."
        )
    off = [] if source.layout_verified else unreconciled(found.holdings)
    if not off:
        return found
    held_back = {(sd_id, day) for sd_id, day, _ in off}
    kept = [line for line in found.holdings if (line.sd_id, line.as_of) not in held_back]
    if not kept:
        raise SourceLayoutError(
            f"{source.name}'s layout is unverified, and none of its {len(off)} portfolios "
            f"sums to 100% within {RECONCILE_TOLERANCE:.0%} (scheme {off[0][0]}: "
            f"{off[0][2]:.2%}). Nothing was stored. Check the file; if it is genuine, its "
            "layout needs a parser fix before it can be imported."
        )
    notes = [
        f"scheme {sd_id} on {day} sums to {total:.2%}; held back (unverified layout)"
        for sd_id, day, total in off
    ]
    return Portfolios(kept, [*notes, *found.unmatched])
