"""Synthetic files in AMFI's layouts (ADR-022 §2.11: tests never use real AMFI data)."""

from __future__ import annotations

from datetime import date

from wickstreet.mf_data.infrastructure.amfi import NAV_HEADER, amfi_date

MASTER_HEADER_LINE = (
    "AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,Scheme Minimum Amount,"
    "Launch Date, Closure Date,ISIN Div Payout/ ISIN GrowthISIN Div Reinvestment"
)


def nav_file(day: date, navs: dict[str, str], *, names: dict[str, str] | None = None) -> bytes:
    """A NAV history file for ``day``: one fund house, one section, one row per code."""
    names = names or {}
    lines = [NAV_HEADER, "", "Open Ended Schemes ( Equity Scheme - Large Cap Fund )", "", ""]
    lines += ["Example Mutual Fund"]
    for code, value in navs.items():
        name = names.get(code, f"Example Fund {code} - Direct Plan - Growth")
        lines.append(
            f"{code};{name};Direct Plan;Growth;INF000X{code:0>5};-;{value};{amfi_date(day)}"
        )
    return ("\r\n".join(lines) + "\r\n").encode()


def master_file(codes: list[str]) -> bytes:
    """A scheme master listing ``codes``, one closed and one with two ISINs."""
    rows = [MASTER_HEADER_LINE]
    for code in codes:
        rows.append(
            f"Example AMC Limited,{code},Example Fund,Open Ended,Equity Scheme - Large Cap Fund,"
            f"Example Fund {code} - Direct Plan - Growth,5000,01-Jan-2013,,"
            f"INF000X{code:0>5}INF000Y{code:0>5}"
        )
    return ("\r\n".join(rows) + "\r\n").encode()
