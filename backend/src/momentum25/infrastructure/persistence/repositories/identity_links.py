"""Verified security identity links: load, check against the bars, import (R3-B-31).

Reads either the current tables (live paths) or the row versions visible at a
revision (point in time: the caller passes ``visible(...)`` subqueries). A link
the bars contradict is logged and never applied.
"""

from __future__ import annotations

import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from momentum25.domain.identity import IdentityLink, IdentityLinks
from momentum25.infrastructure.persistence.models import (
    OHLCVDailyModel,
    SecurityIdentityLinkModel,
    SecurityModel,
)

_logger = get_logger(__name__)
_SHA256 = re.compile(r"\b[0-9a-f]{64}\b")
IMPORT_COLUMNS = (
    "predecessor_id",
    "successor_id",
    "effective_date",
    "ratio",
    "evidence_source",
    "evidence_reference",
)


async def load_identity_links(
    session: AsyncSession, links: Any = None, bars: Any = None, as_of: date | None = None
) -> IdentityLinks:
    """The applicable links. ``links`` and ``bars`` default to the current tables.

    ``as_of`` limits the bar check to bars dated on or before it (point in time).
    """
    links = SecurityIdentityLinkModel.__table__ if links is None else links
    bars = OHLCVDailyModel.__table__ if bars is None else bars
    rows = (await session.execute(select(links))).all()
    if not rows:
        return IdentityLinks()
    candidates = IdentityLinks(
        IdentityLink(
            predecessor_id=row.predecessor_id,
            successor_id=row.successor_id,
            effective_date=row.effective_date,
            ratio=row.ratio,
            evidence_source=row.evidence_source,
            evidence_reference=row.evidence_reference,
        )
        for row in rows
    )
    ids = {link.predecessor_id for link in candidates} | {link.successor_id for link in candidates}
    query = select(bars.c.security_id, func.min(bars.c.date), func.max(bars.c.date)).where(
        bars.c.security_id.in_(ids)
    )
    if as_of is not None:
        query = query.where(bars.c.date <= as_of)
    spans = (await session.execute(query.group_by(bars.c.security_id))).all()
    first = {sid: lo for sid, lo, _ in spans}
    last = {sid: hi for sid, _, hi in spans}
    applicable, rejected = candidates.applicable(first, last)
    for link in rejected:
        _logger.warning(
            "identity_link_contradicted_by_bars",
            predecessor_id=link.predecessor_id,
            successor_id=link.successor_id,
            effective_date=link.effective_date.isoformat(),
        )
    return applicable


def read_import_file(path: Path) -> list[IdentityLink]:
    """Parse an owner-supplied link file; raise ``ValueError`` on any bad row.

    A CSV with the columns of ``IMPORT_COLUMNS``. ``evidence_reference`` must
    name the exchange document and carry its SHA-256. The whole set must
    validate (no self-links, duplicates or cycles) before anything is written.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(IMPORT_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        links = []
        for line, row in enumerate(reader, start=2):
            try:
                link = IdentityLink(
                    predecessor_id=int(row["predecessor_id"]),
                    successor_id=int(row["successor_id"]),
                    effective_date=date.fromisoformat(row["effective_date"].strip()),
                    ratio=Decimal(row["ratio"].strip() or "1"),
                    evidence_source=row["evidence_source"].strip(),
                    evidence_reference=row["evidence_reference"].strip(),
                )
            except (ValueError, InvalidOperation) as exc:
                raise ValueError(f"{path.name} line {line}: {exc}") from exc
            if not _SHA256.search(link.evidence_reference.lower()):
                raise ValueError(f"{path.name} line {line}: evidence_reference needs a SHA-256")
            links.append(link)
    IdentityLinks(links)  # validates the set
    return links


async def import_identity_links(session: AsyncSession, links: list[IdentityLink]) -> int:
    """Insert ``links``; every id must name an existing security. Returns the count.

    The caller commits. An existing predecessor row is never overwritten: a
    correction is a separate, reviewed change.
    """
    ids = {link.predecessor_id for link in links} | {link.successor_id for link in links}
    known = set(await session.scalars(select(SecurityModel.id).where(SecurityModel.id.in_(ids))))
    if unknown := sorted(ids - known):
        raise ValueError(f"unknown security ids: {unknown}")
    existing = await load_all_rows(session)
    IdentityLinks([*existing, *links])  # the combined set must still be consistent
    for link in links:
        session.add(
            SecurityIdentityLinkModel(
                predecessor_id=link.predecessor_id,
                successor_id=link.successor_id,
                effective_date=link.effective_date,
                ratio=link.ratio,
                evidence_source=link.evidence_source,
                evidence_reference=link.evidence_reference,
            )
        )
    await session.flush()
    return len(links)


async def load_all_rows(session: AsyncSession) -> list[IdentityLink]:
    """Every stored link, applicable or not."""
    rows = (await session.scalars(select(SecurityIdentityLinkModel))).all()
    return [
        IdentityLink(
            r.predecessor_id,
            r.successor_id,
            r.effective_date,
            r.ratio,
            r.evidence_source,
            r.evidence_reference,
        )
        for r in rows
    ]
