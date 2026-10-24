"""The definition of one screenable field; the registry is in :mod:`fields`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FieldType = Literal["number", "boolean", "enum", "date"]


@dataclass(frozen=True, slots=True)
class Field:
    """One screenable value. ``values`` lists an enum's members; ``None`` means the snapshot's."""

    id: str
    label: str
    group: str
    type: FieldType
    unit: str | None
    description: str
    values: tuple[str, ...] | None = None
