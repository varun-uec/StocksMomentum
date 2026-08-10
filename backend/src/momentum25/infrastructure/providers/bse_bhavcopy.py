"""BSE market-data provider (Phase 5.1) — official bhavcopy archive, both schemas.

Implements the :class:`MarketDataProvider` port against BSE's public daily
bhavcopy archive, routing by date between the two formats BSE actually
publishes (RP-014 measured, not assumed):

* **UDiFF** (``2024-01-02`` onward, the current scheme)::

      https://www.bseindia.com/download/BhavCopy/Equity/
          BhavCopy_BSE_CM_0_0_0_20260806_F_0000.CSV

* **Legacy EQ_CSV** (``2006-03-01`` → ``2023-12-29``, BSE's earlier daily
  archive; the first downloadable file is 2006-03-01, every earlier date
  returns an HTML error page)::

      https://www.bseindia.com/download/BhavCopy/Equity/
          EQ010306_CSV.ZIP

  Column schema (read off live files from 2006, 2008, 2011, 2015, 2020 and
  2023 — identical across all six eras; equity rows are ``SC_TYPE == 'Q'``)::

      SC_CODE,SC_NAME,SC_GROUP,SC_TYPE,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,
      NO_TRADES,NO_OF_SHRS,NET_TURNOV,TDCLOINDI

The UDiFF column schema below was read off a live 2026-08-06 download (4,962
rows), not assumed::

    TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,...,
    FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,...,
    TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,...

The legacy EQ_CSV files carry no ISIN and no trade-date column — scrip identity
during 2006–2023 is BSE's stable numeric ``SC_CODE`` (carried as
``native_code`` on :class:`RawBar`) plus the padded ``SC_NAME``. The RP-014
backfill learns each ``SC_CODE``'s ISIN from modern UDiFF sessions and resolves
through the canonical securities table; a scrip that never reappears in the
UDiFF era (delisted before 2024) therefore cannot be identity-joined and is
disclosed, never guessed.

Two port methods are deliberately **not** implemented (``fetch_benchmark``,
``fetch_corporate_actions``): BSE publishes SENSEX history and corporate actions
only behind endpoints this codebase has not verified, and returning an empty
list from ``fetch_corporate_actions`` would be indistinguishable from "this
security has no splits or bonuses" — silently corrupting adjusted history. They
raise ``NotImplementedError`` instead. The NSE provider remains the source for
both.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from momentum25.domain.ports.market_data import (
    RawBar,
    RawCorporateAction,
    RawIndexBar,
    RawInstrument,
)
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("bse_bhavcopy")

_BSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bseindia.com/",
}

# Only the columns actually consumed; parsing is by header name so additional
# or reordered columns in a future BSE revision do not shift values silently.
_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "TradDt", "FinInstrmTp", "ISIN", "TckrSymb", "SctySrs", "FinInstrmNm",
        "OpnPric", "HghPric", "LwPric", "ClsPric", "PrvsClsgPric",
        "TtlTradgVol", "TtlTrfVal",
    }
)

# The equity cash segment marks every scrip ``STK`` (UDiFF) / ``Q`` (legacy);
# derivatives and other segments are published in separate files but the
# guards are kept explicit.
_EQUITY_INSTRUMENT_TYPE = "STK"
_EQUITY_LEGACY_SCRIP_TYPE = "Q"

# RP-014 measured archive boundaries (see module docstring): no public BSE
# bhavcopy exists before 2006-03-01; the legacy EQ_CSV format ends 2023-12-29;
# the UDiFF format begins 2024-01-02 (first trading day of 2024).
BSE_LEGACY_START: date = date(2006, 3, 1)
UDIFF_START: date = date(2024, 1, 2)

# Legacy EQ_CSV required columns. Parsing by header name tolerates column
# reordering; a 2006-era file must carry exactly these.
_LEGACY_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "SC_CODE", "SC_NAME", "SC_GROUP", "SC_TYPE", "OPEN", "HIGH", "LOW",
        "CLOSE", "PREVCLOSE", "NO_OF_SHRS", "NET_TURNOV",
    }
)


def bse_bhavcopy_url(for_date: date) -> str:
    """Return the BSE equity bhavcopy URL for ``for_date`` (pure)."""
    return (
        "https://www.bseindia.com/download/BhavCopy/Equity/"
        f"BhavCopy_BSE_CM_0_0_0_{for_date:%Y%m%d}_F_0000.CSV"
    )


def bse_legacy_bhavcopy_url(for_date: date) -> str:
    """Return the legacy BSE equity bhavcopy URL for ``for_date`` (pure)."""
    return (
        "https://www.bseindia.com/download/BhavCopy/Equity/"
        f"EQ{for_date:%d%m%y}_CSV.ZIP"
    )


def bse_archive_url(for_date: date) -> str | None:
    """Return the BSE archive URL for ``for_date``, or ``None`` before inception (pure).

    ``None`` means BSE publishes no public bhavcopy for the date — every date
    before 2006-03-01 returns an HTML error page for both URL schemes, so a
    caller must treat it as an empty session, not attempt a download.
    """
    if for_date < BSE_LEGACY_START:
        return None
    if for_date < UDIFF_START:
        return bse_legacy_bhavcopy_url(for_date)
    return bse_bhavcopy_url(for_date)


def _decimal_or_none(value: str | None) -> Decimal | None:
    """Parse a Decimal from a BSE CSV cell, or ``None`` if blank/invalid."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def parse_bse_bhavcopy(content: bytes, for_date: date) -> list[RawBar]:
    """Parse a BSE bhavcopy payload into ``RawBar`` rows (pure).

    Rows whose ``TradDt`` is not ``for_date`` are dropped rather than trusted,
    mirroring the NSE holiday handling: a stale file must never be misdated.
    ``PrvsClsgPric``/``TtlTrfVal`` are preserved verbatim (including a genuine
    reported zero); only blank or unparseable cells become ``None``.
    """
    text = content.decode("latin1")
    reader = csv.DictReader(io.StringIO(text))
    header = {(h or "").strip() for h in (reader.fieldnames or [])}
    if not _REQUIRED_COLUMNS.issubset(header):
        _logger.warning(
            "bse_bhavcopy_unexpected_columns",
            date=for_date.isoformat(),
            columns=sorted(header),
        )
        return []

    iso_date = for_date.isoformat()
    bars: list[RawBar] = []
    for row in reader:
        cell = {(k or "").strip(): (v or "") for k, v in row.items()}
        if cell.get("FinInstrmTp", "").strip() != _EQUITY_INSTRUMENT_TYPE:
            continue
        if cell.get("TradDt", "").strip() != iso_date:
            continue
        symbol = cell.get("TckrSymb", "").strip().upper()
        if not symbol:
            continue
        close = _decimal_or_none(cell.get("ClsPric"))
        if close is None:
            continue
        bars.append(
            RawBar(
                symbol=symbol,
                date=for_date,
                open=_decimal_or_none(cell.get("OpnPric")) or Decimal("0"),
                high=_decimal_or_none(cell.get("HghPric")) or Decimal("0"),
                low=_decimal_or_none(cell.get("LwPric")) or Decimal("0"),
                close=close,
                volume=int(_decimal_or_none(cell.get("TtlTradgVol")) or Decimal("0")),
                prev_close=_decimal_or_none(cell.get("PrvsClsgPric")),
                turnover_value=_decimal_or_none(cell.get("TtlTrfVal")),
                isin=cell.get("ISIN", "").strip().upper() or None,
            )
        )
    return bars


def parse_bse_legacy_bhavcopy(content: bytes, for_date: date) -> list[RawBar]:
    """Parse a legacy BSE bhavcopy ZIP payload into ``RawBar`` rows (pure).

    Legacy files (2006-03-01 → 2023-12-29) carry no trade-date column, so the
    session identity is the filename date that selected the file — the trust
    anchor the UDiFF route's ``TradDt`` check replaced. Only ``SC_TYPE == 'Q'``
    (equity) rows are kept; bonds/preference/other rows are the UDiFF
    ``FinInstrmTp != STK`` exclusion's legacy counterpart. The printed identity
    is ``SC_NAME`` (stripped of BSE's fixed-width padding); the exchange-stable
    numeric ``SC_CODE`` is carried on ``native_code`` for ISIN learning.
    ``PREVCLOSE``/``NET_TURNOV`` are preserved verbatim; only blank or
    unparseable cells become ``None``.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        _logger.warning("bse_legacy_bhavcopy_bad_zip", date=for_date.isoformat())
        return []

    names = archive.namelist()
    if not names:
        return []
    text = archive.read(names[0]).decode("latin1")
    reader = csv.DictReader(io.StringIO(text))
    header = {(h or "").strip().upper() for h in (reader.fieldnames or [])}
    if not _LEGACY_REQUIRED_COLUMNS.issubset(header):
        _logger.warning(
            "bse_legacy_bhavcopy_unexpected_columns",
            date=for_date.isoformat(),
            columns=sorted(header),
        )
        return []

    bars: list[RawBar] = []
    for row in reader:
        cell = {(k or "").strip().upper(): (v or "") for k, v in row.items()}
        if cell.get("SC_TYPE", "").strip().upper() != _EQUITY_LEGACY_SCRIP_TYPE:
            continue
        name = cell.get("SC_NAME", "").strip().upper()
        if not name:
            continue
        close = _decimal_or_none(cell.get("CLOSE"))
        if close is None:
            continue
        sc_code = cell.get("SC_CODE", "").strip() or None
        bars.append(
            RawBar(
                symbol=name,
                date=for_date,
                open=_decimal_or_none(cell.get("OPEN")) or Decimal("0"),
                high=_decimal_or_none(cell.get("HIGH")) or Decimal("0"),
                low=_decimal_or_none(cell.get("LOW")) or Decimal("0"),
                close=close,
                volume=int(_decimal_or_none(cell.get("NO_OF_SHRS")) or Decimal("0")),
                prev_close=_decimal_or_none(cell.get("PREVCLOSE")),
                turnover_value=_decimal_or_none(cell.get("NET_TURNOV")),
                native_code=sc_code,
            )
        )
    return bars


def parse_bse_instruments(content: bytes, for_date: date) -> list[RawInstrument]:
    """Parse a BSE bhavcopy payload into ``RawInstrument`` rows (pure).

    BSE's separate scrip-master endpoint is not used: the bhavcopy already
    carries ticker, ISIN, company name and group (``SctySrs``) for every scrip
    that traded that session, so the instrument master is derived from the same
    verified file rather than a second, unverified source. ``listing_date`` is
    left ``None`` — the bhavcopy does not carry it and inferring one would be
    fabrication.
    """
    text = content.decode("latin1")
    reader = csv.DictReader(io.StringIO(text))
    header = {(h or "").strip() for h in (reader.fieldnames or [])}
    if not _REQUIRED_COLUMNS.issubset(header):
        _logger.warning(
            "bse_instruments_unexpected_columns",
            date=for_date.isoformat(),
            columns=sorted(header),
        )
        return []

    instruments: dict[str, RawInstrument] = {}
    for row in reader:
        cell = {(k or "").strip(): (v or "") for k, v in row.items()}
        if cell.get("FinInstrmTp", "").strip() != _EQUITY_INSTRUMENT_TYPE:
            continue
        symbol = cell.get("TckrSymb", "").strip().upper()
        if not symbol:
            continue
        instruments.setdefault(
            symbol,
            RawInstrument(
                symbol=symbol,
                name=cell.get("FinInstrmNm", "").strip() or symbol,
                isin=cell.get("ISIN", "").strip().upper() or None,
                series=cell.get("SctySrs", "").strip() or None,
                native_code=cell.get("FinInstrmId", "").strip() or None,
            ),
        )
    return sorted(instruments.values(), key=lambda i: i.symbol)


class BSEBhavcopyProvider:
    """Implements :class:`MarketDataProvider` against the BSE equity bhavcopy.

    The HTTP boundary is a single method (:meth:`_download`); all schema
    handling lives in the two module-level pure parsers, which are covered by
    tests against a real, unmodified BSE payload.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Bind the provider to an optional shared HTTP client."""
        self._client = client

    async def fetch_eod(self, for_date: date) -> list[RawBar]:
        """Fetch and parse BSE EOD bars for ``for_date`` (empty on non-sessions).

        Routes by date (RP-014): 2006-03-01 → 2023-12-29 from the legacy
        EQ_CSV archive, 2024-01-02 onward from the UDiFF bhavcopy, and any
        earlier date as an empty session (BSE publishes nothing before
        2006-03-01). The two formats' parsers are selected by the same pure
        date function, so a given date deterministically maps to one schema.
        """
        url = bse_archive_url(for_date)
        if url is None:
            _logger.info(
                "bse_bhavcopy_pre_archive_date", date=for_date.isoformat()
            )
            return []
        content = await self._download(url, for_date)
        if content is None:
            return []
        if for_date < UDIFF_START:
            return parse_bse_legacy_bhavcopy(content, for_date)
        return parse_bse_bhavcopy(content, for_date)

    async def fetch_instrument_master(self, for_date: date | None = None) -> list[RawInstrument]:
        """Return the BSE equity instrument master derived from a session's bhavcopy.

        ``for_date`` defaults to today; a non-session date yields an empty list,
        so callers should pass the last trading session (as the cross-listing
        use case does) rather than relying on the default. The master is
        current-format only: dates before the UDiFF era (2024-01-02) fail the
        UDiFF header check and yield an empty list — the RP-014 legacy backfill
        builds its ``SC_CODE`` identity junction exclusively from UDiFF-era
        sessions, so no legacy-date master is needed.
        """
        session = for_date or date.today()
        if session < UDIFF_START:
            _logger.warning(
                "bse_instrument_master_pre_udiff", date=session.isoformat()
            )
            return []
        content = await self._download(bse_bhavcopy_url(session), session)
        return parse_bse_instruments(content, session) if content else []

    async def fetch_benchmark(self, index_code: str, for_date: date) -> RawIndexBar | None:
        """Not implemented — see module docstring."""
        raise NotImplementedError(
            "BSE index history is not a verified source in this platform; "
            "use the NSE provider for benchmark data."
        )

    async def fetch_corporate_actions(self, symbol: str, since: date) -> list[RawCorporateAction]:
        """Not implemented — see module docstring."""
        raise NotImplementedError(
            "BSE corporate actions are not a verified source in this platform; "
            "an empty result would be indistinguishable from 'no actions' and "
            "would silently corrupt adjusted price history."
        )

    async def _download(self, url: str, for_date: date) -> bytes | None:
        """Fetch the raw bhavcopy payload; ``None`` on a non-session or error."""
        try:
            if self._client is not None:
                resp = await self._client.get(url, headers=_BSE_HEADERS, follow_redirects=True)
            else:
                async with httpx.AsyncClient(
                    headers=_BSE_HEADERS, timeout=30, follow_redirects=True
                ) as client:
                    resp = await client.get(url)
        except Exception as exc:  # network failure is a data gap, not a crash
            _logger.warning("bse_bhavcopy_fetch_failed", date=for_date.isoformat(), error=str(exc))
            return None

        if resp.status_code == 404:
            _logger.info("bse_bhavcopy_missing_nontrading_day", date=for_date.isoformat())
            return None
        if resp.status_code != 200:
            _logger.warning(
                "bse_bhavcopy_http_error", date=for_date.isoformat(), status=resp.status_code
            )
            return None
        return resp.content
