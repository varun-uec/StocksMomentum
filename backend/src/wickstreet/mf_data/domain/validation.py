"""Blocking checks and row anomalies for a NAV file (ADR-017 MF-8).

A blocking problem fails the run, and nothing from the file is published. A row
anomaly is stored as filed with a flag; how flagged rows enter metrics is owner
methodology, decided with the metric formulas.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from wickstreet.mf_data.domain.model import (
    DERIVATIVE,
    Anomaly,
    Holding,
    NavRecord,
    RatePoint,
    SchemeRecord,
)


class BlockingError(Exception):
    """The file must not be published."""


def check_nav_day(records: Iterable[NavRecord], day: date) -> list[NavRecord]:
    """Return the file's rows for ``day``, one per code, or raise :class:`BlockingError`.

    Blocking: no rows, a row dated other than ``day``, or one code filed twice with
    different values. Identical repeats are dropped.
    """
    unique: dict[str, NavRecord] = {}
    for record in records:
        if record.nav_date != day:
            raise BlockingError(
                f"Row for {record.amfi_code} is dated {record.nav_date}, not {day}."
            )
        seen = unique.get(record.amfi_code)
        if seen is not None and seen != record:
            raise BlockingError(
                f"Code {record.amfi_code} is filed twice for {day} with different values."
            )
        unique[record.amfi_code] = record
    if not unique:
        raise BlockingError(f"The file for {day} has no NAV rows.")
    return list(unique.values())


def check_scheme_master(records: Iterable[SchemeRecord]) -> list[SchemeRecord]:
    """Return the master's rows, or raise when it is empty or repeats a code."""
    unique: dict[str, SchemeRecord] = {}
    for record in records:
        if record.amfi_code in unique:
            raise BlockingError(f"Scheme master lists code {record.amfi_code} twice.")
        unique[record.amfi_code] = record
    if not unique:
        raise BlockingError("The scheme master has no rows.")
    return list(unique.values())


def flag_anomalies(
    records: Iterable[NavRecord], previous: Mapping[str, Decimal], jump_threshold: Decimal
) -> dict[str, Anomaly]:
    """Flag missing, zero and negative NAVs, and moves beyond ``jump_threshold``.

    ``previous`` holds each code's latest positive NAV before the file's date. A
    jump is ``|nav / previous - 1| > jump_threshold``: a suspected unadjusted split
    or a filing error.
    """
    flags: dict[str, Anomaly] = {}
    for record in records:
        nav = record.nav
        if nav is None:
            flags[record.amfi_code] = Anomaly.MISSING
        elif nav == 0:
            flags[record.amfi_code] = Anomaly.ZERO
        elif nav < 0:
            flags[record.amfi_code] = Anomaly.NEGATIVE
        else:
            before = previous.get(record.amfi_code)
            if before is not None and abs(nav / before - 1) > jump_threshold:
                flags[record.amfi_code] = Anomaly.JUMP
    return flags


@dataclass(frozen=True, slots=True)
class Comparison:
    """One code's stored NAVs against a reference source, date by date."""

    amfi_code: str
    matched: int
    differing: int
    reference_only: int
    stored_only: int
    examples: tuple[str, ...]


def compare_series(
    amfi_code: str,
    stored: Mapping[date, Decimal | None],
    reference: Mapping[date, Decimal | None],
    tolerance: Decimal,
    max_examples: int = 3,
) -> Comparison:
    """Compare two NAV series by date; two values within ``tolerance`` match.

    The archive keeps 4 decimals and AMFI files up to 8, so an exact comparison
    would report rounding as a difference. Two missing values match.
    """
    matched = differing = 0
    examples: list[str] = []
    for day in sorted(stored.keys() & reference.keys()):
        ours, theirs = stored[day], reference[day]
        same = ours == theirs or (
            ours is not None and theirs is not None and abs(ours - theirs) <= tolerance
        )
        if same:
            matched += 1
            continue
        differing += 1
        if len(examples) < max_examples:
            examples.append(f"{day}: stored {ours}, reference {theirs}")
    return Comparison(
        amfi_code=amfi_code,
        matched=matched,
        differing=differing,
        reference_only=len(reference.keys() - stored.keys()),
        stored_only=len(stored.keys() - reference.keys()),
        examples=tuple(examples),
    )


# A portfolio reconciles when its lines sum to 100% of net assets within this, with or
# without its derivative lines (a hedged sheet nets its futures; others list them apart).
RECONCILE_TOLERANCE = Decimal("0.02")


def unreconciled(holdings: Iterable[Holding]) -> list[tuple[int, date, Decimal]]:
    """Each portfolio that does not reconcile: its scheme, date and total of all lines."""
    every: defaultdict[tuple[int, date], Decimal] = defaultdict(Decimal)
    held: defaultdict[tuple[int, date], Decimal] = defaultdict(Decimal)
    for line in holdings:
        every[line.sd_id, line.as_of] += line.weight
        if line.asset != DERIVATIVE:
            held[line.sd_id, line.as_of] += line.weight
    return sorted(
        (sd_id, day, total)
        for (sd_id, day), total in every.items()
        if min(abs(total - 1), abs(held[sd_id, day] - 1)) > RECONCILE_TOLERANCE
    )


# A yield outside this range is a parse error, not a rate (% a year).
RATE_RANGE = (Decimal("0"), Decimal("25"))


def check_rates(records: Iterable[RatePoint]) -> list[RatePoint]:
    """Return the file's rates in date order, or raise :class:`BlockingError`.

    Blocking: no rows, a value outside ``RATE_RANGE``, or one series and date given two
    different values. Identical repeats are dropped.
    """
    unique: dict[tuple[str, date], RatePoint] = {}
    for record in records:
        low, high = RATE_RANGE
        if not low < record.value <= high:
            raise BlockingError(f"Rate {record.value} on {record.day} is outside {low}-{high}%.")
        key = (record.series, record.day)
        if key in unique and unique[key].value != record.value:
            raise BlockingError(f"{record.series} on {record.day} has two values.")
        unique[key] = record
    if not unique:
        raise BlockingError("The file has no rates.")
    return sorted(unique.values(), key=lambda r: (r.series, r.day))
