"""Synthetic files in TigZig's and MFAPI's layouts (tests never use real source data)."""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

import httpx

from wickstreet.mf_data.infrastructure.mfapi import MfapiAdapter
from wickstreet.mf_data.infrastructure.tigzig import ARCHIVE_URL, SNAPSHOT_URL, TigzigAdapter

SNAPSHOT_HEADER = "scheme_code,isin,isin2,scheme_name,amc,scheme_type,category,nav_date,nav,source"


def archive_file(rows: list[tuple[str, date, str]]) -> bytes:
    """An archive sorted by code, then date, with one SIF row that must be skipped."""
    lines = ['scheme_code,date,nav,"scheme_name",isin,source']
    for code, day, nav in sorted(rows):
        lines.append(f'{code},{day.isoformat()},{nav},"Example Fund {code}",INF000X{code:0>5},MF')
    lines.append(f'120,{rows[0][1].isoformat()},10.0000,"Example SIF",,SIF')
    return gzip.compress(("\n".join(lines) + "\n").encode())


def snapshot_file(codes: list[str]) -> bytes:
    """A scheme-master snapshot listing ``codes`` and one SIF."""
    lines = [SNAPSHOT_HEADER]
    for code in codes:
        lines.append(
            f'{code},INF000X{code:0>5},-,"Example Fund {code} - Growth",Example AMC,'
            "Open Ended Schemes,Equity Scheme - Large Cap Fund,2026-10-01,10.0000,MF"
        )
    lines.append('120,,,"Example SIF",Example AMC,Open Ended Schemes,SIF,2026-10-01,10,SIF')
    return gzip.compress(("\n".join(lines) + "\n").encode())


def mfapi_file(navs: dict[date, str], status: str = "SUCCESS") -> bytes:
    """One MFAPI history, newest date first as MFAPI writes it."""
    data = [
        {"date": f"{day.day:02d}-{day.month:02d}-{day.year}", "nav": nav}
        for day, nav in sorted(navs.items(), reverse=True)
    ]
    return json.dumps({"meta": {"scheme_code": 0}, "data": data, "status": status}).encode()


def tigzig_adapter(work_dir: Path, archive: bytes, snapshot: bytes) -> TigzigAdapter:
    """The real adapter over a fake network serving ``archive`` and ``snapshot``."""
    files = {ARCHIVE_URL: archive, SNAPSHOT_URL: snapshot}

    def serve(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=files[str(request.url)])

    return TigzigAdapter(
        work_dir=work_dir,
        min_interval_seconds=0,
        timeout_seconds=5,
        max_attempts=1,
        transport=httpx.MockTransport(serve),
    )


def mfapi_adapter(histories: dict[str, bytes]) -> MfapiAdapter:
    """The real adapter over a fake network serving one history per code."""

    def serve(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=histories[request.url.path.rsplit("/", 1)[-1]])

    return MfapiAdapter(
        min_interval_seconds=0,
        timeout_seconds=5,
        max_attempts=1,
        transport=httpx.MockTransport(serve),
    )
