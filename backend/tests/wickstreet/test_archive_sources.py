"""TigZig and MFAPI adapters and the series comparison, on synthetic files (ADR-023 U11)."""

from __future__ import annotations

import gzip
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tests.wickstreet.archive_files import archive_file, mfapi_file, snapshot_file, tigzig_adapter
from wickstreet.mf_data.domain.ports import SourceLayoutError
from wickstreet.mf_data.domain.validation import compare_series
from wickstreet.mf_data.infrastructure.mfapi import parse_history
from wickstreet.mf_data.infrastructure.tigzig import parse_snapshot, split_archive

SEP_30, OCT_1, OCT_2 = date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)


async def test_the_archive_is_read_one_date_at_a_time_in_date_order(tmp_path: Path) -> None:
    content = archive_file(
        [("10002", SEP_30, "20"), ("10001", OCT_2, "11"), ("10001", OCT_1, "10")]
        + [("10001", date(2026, 10, 3), "12")]
    )
    adapter = tigzig_adapter(tmp_path / "work", content, b"")
    raw = await adapter.archive()
    days = list(adapter.parse_archive(raw, SEP_30, OCT_2))
    assert [(day, [(r.amfi_code, r.nav) for r in rows]) for day, rows in days] == [
        (SEP_30, [("10002", Decimal("20"))]),
        (OCT_1, [("10001", Decimal("10"))]),
        (OCT_2, [("10001", Decimal("11"))]),
    ]
    assert all(r.amc is None and r.nav_name is None for _, rows in days for r in rows)
    assert list((tmp_path / "work").iterdir()) == []


@pytest.mark.parametrize(
    "content",
    [
        gzip.compress(b"code,date,nav\n10001,2026-10-01,10\n"),
        gzip.compress(b'scheme_code,date,nav,"scheme_name",isin,source\nX1,2026-10-01,1,a,,MF\n'),
        gzip.compress(b'scheme_code,date,nav,"scheme_name",isin,source\n1,01-10-2026,1,a,,MF\n'),
        b"not gzip",
    ],
)
def test_an_unknown_archive_layout_publishes_nothing(content: bytes, tmp_path: Path) -> None:
    with pytest.raises(SourceLayoutError):
        split_archive(content, SEP_30, OCT_2, tmp_path / "work")


def test_the_snapshot_maps_to_the_scheme_contract_without_sifs() -> None:
    (record,) = parse_snapshot(snapshot_file(["10001"]))
    assert (record.amfi_code, record.amc, record.isin_growth, record.isin_reinvest) == (
        "10001",
        "Example AMC",
        "INF000X10001",
        None,
    )
    assert record.nav_name == record.scheme_name and record.launch_date is None


def test_an_mfapi_history_parses_by_date() -> None:
    navs = parse_history(mfapi_file({OCT_1: "10.12345", OCT_2: "N.A."}))
    assert navs == {OCT_1: Decimal("10.12345"), OCT_2: None}
    with pytest.raises(SourceLayoutError):
        parse_history(mfapi_file({}, status="FAILED"))
    with pytest.raises(SourceLayoutError):
        parse_history(b"{}")


def test_series_match_within_the_archive_rounding() -> None:
    stored = {SEP_30: Decimal("10.1234"), OCT_1: Decimal("10.5"), OCT_2: None}
    reference = {SEP_30: Decimal("10.12344"), OCT_1: Decimal("10.6"), date(2026, 10, 5): None}
    result = compare_series("10001", stored, reference, Decimal("0.0001"))
    assert (result.matched, result.differing, result.reference_only, result.stored_only) == (
        1,
        1,
        1,
        1,
    )
    assert result.examples == ("2026-10-01: stored 10.5, reference 10.6",)
