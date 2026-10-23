"""A metric snapshot: every fund's fields at one (revision, method version) (MF-11).

The encoding is deterministic: sorted keys, floats as ``repr``, gzip without a
timestamp. Equal inputs give equal bytes and an equal SHA-256.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from wickstreet.analytics.domain.fields import FIELDS
from wickstreet.analytics.domain.metrics import Missing, Value


@dataclass(frozen=True, slots=True)
class FundRow:
    """One fund in a snapshot: its fields in registry order, and its trailing anchors."""

    plan_option_id: int
    amfi_code: str
    name: str
    values: tuple[Value, ...]
    anchors: dict[str, str]


@dataclass(frozen=True)
class Snapshot:
    """A stored snapshot, indexed for reads."""

    id: int
    revision: int
    method_version: int
    as_of: date
    sources: tuple[str, ...]
    rows: tuple[FundRow, ...]
    by_code: dict[str, FundRow] = field(init=False)
    # Field id -> reason -> how many rows miss that field for that reason.
    missing: dict[str, Counter[str]] = field(init=False)

    def __post_init__(self) -> None:
        """Index the rows once; a snapshot never changes (MF-11)."""
        object.__setattr__(self, "by_code", {row.amfi_code: row for row in self.rows})
        missing: dict[str, Counter[str]] = {f.id: Counter() for f in FIELDS}
        for row in self.rows:
            for f, value in zip(FIELDS, row.values, strict=True):
                if isinstance(value, Missing):
                    missing[f.id][value.reason] += 1
        object.__setattr__(self, "missing", missing)


@dataclass(frozen=True, slots=True)
class Encoded:
    """A snapshot body ready to store."""

    payload: bytes
    sha256: str
    funds: int


def _value(value: Value) -> Any:
    return [value.state, value.reason] if isinstance(value, Missing) else value


def _decoded(value: Any) -> Value:
    return Missing(value[0], value[1]) if isinstance(value, list) else value


def encode(
    method_version: int, revision: int, as_of: date, sources: Sequence[str], rows: Sequence[FundRow]
) -> Encoded:
    """Serialise rows in plan-option order; refuses NaN and infinity."""
    body = json.dumps(
        {
            "method_version": method_version,
            "revision": revision,
            "as_of": as_of.isoformat(),
            "sources": sorted(sources),
            "fields": [f.id for f in FIELDS],
            "funds": [
                [r.plan_option_id, r.amfi_code, r.name, [_value(v) for v in r.values], r.anchors]
                for r in sorted(rows, key=lambda r: r.plan_option_id)
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return Encoded(gzip.compress(body, mtime=0), hashlib.sha256(body).hexdigest(), len(rows))


def decode(snapshot_id: int, payload: bytes) -> Snapshot:
    """Rebuild a snapshot; fails if its fields are not this registry's."""
    body = json.loads(gzip.decompress(payload))
    if body["fields"] != [f.id for f in FIELDS]:
        raise ValueError(f"Snapshot {snapshot_id} was written with another field registry.")
    return Snapshot(
        id=snapshot_id,
        revision=body["revision"],
        method_version=body["method_version"],
        as_of=date.fromisoformat(body["as_of"]),
        sources=tuple(body["sources"]),
        rows=tuple(
            FundRow(pid, code, name, tuple(_decoded(v) for v in values), anchors)
            for pid, code, name, values, anchors in body["funds"]
        ),
    )


def payload_sha256(payload: bytes) -> str:
    """SHA-256 of a stored payload's JSON body."""
    return hashlib.sha256(gzip.decompress(payload)).hexdigest()


class SnapshotStore(Protocol):
    """Port: stored snapshots, one per (revision, method version)."""

    async def exists(self, revision: int, method_version: int) -> bool:
        """Return whether the snapshot is stored."""
        ...

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
        ...

    async def find(self, revision: int | None, method_version: int) -> Snapshot | None:
        """Return the snapshot at ``revision``, or the latest when it is ``None``."""
        ...
