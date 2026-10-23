"""A metric snapshot: every fund's fields at one (revision, method version) (MF-11).

The encoding is deterministic: sorted keys, floats as ``repr``, gzip without a
timestamp. Equal inputs give equal bytes and an equal SHA-256.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from wickstreet.analytics.domain.fields import FIELDS
from wickstreet.analytics.domain.metrics import REASONS, Missing, Value


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
    # Field id -> reason -> how many rows miss that field for that reason; counted from
    # the rows when not given.
    missing: dict[str, Counter[str]] = field(default_factory=dict)
    # Cross-fund tables of method v4: ``pairs``, ``near_duplicates``, ``regimes``, ``proxy``.
    tables: dict[str, Any] = field(default_factory=dict)
    by_code: dict[str, FundRow] = field(init=False)

    def __post_init__(self) -> None:
        """Index the rows once; a snapshot never changes (MF-11)."""
        object.__setattr__(self, "by_code", {row.amfi_code: row for row in self.rows})
        if not self.missing:
            object.__setattr__(self, "missing", count_missing(self.rows))


def count_missing(rows: Sequence[FundRow]) -> dict[str, Counter[str]]:
    """Field id -> reason -> rows missing that field for that reason."""
    missing: dict[str, Counter[str]] = {f.id: Counter() for f in FIELDS}
    for row in rows:
        for f, value in zip(FIELDS, row.values, strict=True):
            if isinstance(value, Missing):
                missing[f.id][value.reason] += 1
    return missing


@dataclass(frozen=True, slots=True)
class Encoded:
    """A snapshot body ready to store."""

    payload: bytes
    sha256: str
    funds: int


# Every (state, reason) a snapshot may hold, in a fixed order; a row stores a missing
# value as null and its position in this table, so decoding allocates little.
STATES: tuple[tuple[str, str], ...] = tuple(
    sorted((state, reason) for state in ("NA", "NM") for reason in REASONS)
)
_CODES = {pair: code for code, pair in enumerate(STATES)}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def row_json(row: FundRow) -> str:
    """One fund: id, code, name, values (null when missing), missing codes, anchors."""
    values: list[Any] = []
    codes: list[int] = []
    for value in row.values:
        if isinstance(value, Missing):
            values.append(None)
            codes.append(_CODES[(value.state, value.reason)])
        else:
            values.append(value)
    return _json([row.plan_option_id, row.amfi_code, row.name, values, codes, row.anchors])


class Encoder:
    """Streams a snapshot body through gzip and SHA-256, one fund at a time.

    The body equals one ``json.dumps`` of the whole snapshot with sorted keys, but the
    encoder never holds it whole. Rows must arrive in plan-option order.
    """

    def __init__(
        self, method_version: int, revision: int, as_of: date, sources: Sequence[str]
    ) -> None:
        """Write the keys that sort before ``funds``."""
        self._buffer = io.BytesIO()
        self._gzip = gzip.GzipFile(fileobj=self._buffer, mode="wb", mtime=0)
        self._sha = hashlib.sha256()
        self._method_version = method_version
        self._tail = (
            f',"revision":{_json(revision)},"sources":{_json(sorted(sources))},'
            f'"states":{_json([list(pair) for pair in STATES])}'
        )
        self._missing: dict[str, Counter[str]] = {f.id: Counter() for f in FIELDS}
        self._last: int | None = None
        self.funds = 0
        self._write(
            f'{{"as_of":{_json(as_of.isoformat())},'
            f'"fields":{_json([f.id for f in FIELDS])},"funds":['
        )

    def _write(self, text: str) -> None:
        data = text.encode()
        self._sha.update(data)
        self._gzip.write(data)

    def add(self, row: FundRow) -> None:
        """Append one fund."""
        if self._last is not None and row.plan_option_id <= self._last:
            raise ValueError("Snapshot rows must arrive in plan-option order.")
        for f, value in zip(FIELDS, row.values, strict=True):
            if isinstance(value, Missing):
                self._missing[f.id][value.reason] += 1
        self._write(("," if self._last is not None else "") + row_json(row))
        self._last = row.plan_option_id
        self.funds += 1

    def finish(self, tables: dict[str, Any] | None = None) -> Encoded:
        """Close the body with the cross-fund tables; return the gzipped payload and its hash."""
        self._write(
            f'],"method_version":{_json(self._method_version)},"missing":{_json(self._missing)}'
            + self._tail
            + f',"tables":{_json(tables or {})}}}'
        )
        self._gzip.close()
        return Encoded(self._buffer.getvalue(), self._sha.hexdigest(), self.funds)


def encode(
    method_version: int, revision: int, as_of: date, sources: Sequence[str], rows: Sequence[FundRow]
) -> Encoded:
    """Serialise rows in plan-option order."""
    encoder = Encoder(method_version, revision, as_of, sources)
    for row in sorted(rows, key=lambda r: r.plan_option_id):
        encoder.add(row)
    return encoder.finish()


def _values(values: list[Any], codes: list[int], states: list[Missing]) -> tuple[Value, ...]:
    missing = iter(codes)
    return tuple(states[next(missing)] if v is None else v for v in values)


def decode(snapshot_id: int, payload: bytes) -> Snapshot:
    """Rebuild a snapshot; fails if its fields are not this registry's."""
    body = json.loads(gzip.decompress(payload))
    if body["fields"] != [f.id for f in FIELDS]:
        raise ValueError(f"Snapshot {snapshot_id} was written with another field registry.")
    states = [Missing(state, reason) for state, reason in body["states"]]
    return Snapshot(
        id=snapshot_id,
        revision=body["revision"],
        method_version=body["method_version"],
        as_of=date.fromisoformat(body["as_of"]),
        sources=tuple(body["sources"]),
        rows=tuple(
            FundRow(pid, code, name, _values(values, codes, states), anchors)
            for pid, code, name, values, codes, anchors in body["funds"]
        ),
        missing={f: Counter(reasons) for f, reasons in body.get("missing", {}).items()},
        tables=body.get("tables", {}),
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
