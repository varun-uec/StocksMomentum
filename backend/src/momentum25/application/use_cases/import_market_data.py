"""Import locally supplied, authorized CSV market data into the application store."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from momentum25.domain.entities.market_data import (
    OHLCVBar,
    compute_adjustment_factors,
)
from momentum25.domain.entities.security import Security
from momentum25.domain.ports.market_data import RawCorporateAction, RawIndexBar
from momentum25.domain.value_objects.types import Symbol


def _rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    """Read a CSV after validating its header and non-empty body."""
    try:
        with path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            fields = {field.strip().lower() for field in (reader.fieldnames or [])}
            missing = required - fields
            if missing:
                raise ValueError(f"{path}: missing required columns: {', '.join(sorted(missing))}")
            parsed = [
                {
                    str(key).strip().lower(): (value or "").strip()
                    for key, value in row.items()
                    if key
                }
                for row in reader
            ]
    except OSError as exc:
        raise ValueError(f"Cannot read CSV {path}: {exc}") from exc
    if not parsed:
        raise ValueError(f"{path}: CSV contains no data rows")
    return parsed


def _decimal(value: str, *, label: str, positive: bool = False) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{label}: expected a decimal number, got {value!r}") from exc
    if not result.is_finite() or (positive and result <= 0):
        requirement = "a finite positive number" if positive else "a finite number"
        raise ValueError(f"{label}: expected {requirement}, got {value!r}")
    return result


def _date(value: str, *, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label}: expected YYYY-MM-DD, got {value!r}") from exc


def parse_eod_csv(path: Path) -> tuple[list[Security], dict[str, list[OHLCVBar]]]:
    """Parse a normalized daily-bars CSV and reject ambiguous or invalid rows."""
    required = {"symbol", "date", "open", "high", "low", "close", "volume"}
    rows = _rows(path, required)
    security_meta: dict[str, Security] = {}
    bars_by_symbol: dict[str, list[OHLCVBar]] = defaultdict(list)
    seen: set[tuple[str, date]] = set()

    for line, row in enumerate(rows, start=2):
        label = f"{path}:{line}"
        try:
            symbol = Symbol(row["symbol"])
            bar_date = _date(row["date"], label=f"{label} date")
            prices = {
                key: _decimal(row[key], label=f"{label} {key}", positive=True)
                for key in ("open", "high", "low", "close")
            }
            if prices["high"] < max(prices["open"], prices["close"]) or prices["low"] > min(
                prices["open"], prices["close"]
            ) or prices["low"] > prices["high"]:
                raise ValueError(f"{label}: OHLC values violate high/low bounds")
            volume = int(row["volume"])
            if volume < 0 or str(volume) != row["volume"]:
                raise ValueError(f"{label} volume: expected a non-negative integer")
            key = (str(symbol), bar_date)
            if key in seen:
                raise ValueError(f"{label}: duplicate symbol/date row for {symbol} on {bar_date}")
            seen.add(key)

            exchange = (row.get("exchange") or "NSE").upper()
            if exchange not in {"NSE", "BSE", "BOTH"}:
                raise ValueError(f"{label} exchange: expected NSE, BSE or BOTH")
            listing_date = (
                _date(row["listing_date"], label=f"{label} listing_date")
                if row.get("listing_date")
                else None
            )
            candidate = Security(
                symbol=symbol,
                name=row.get("name") or str(symbol),
                isin=row.get("isin") or None,
                exchange=exchange,
                listing_date=listing_date,
            )
            existing = security_meta.get(str(symbol))
            if existing and (
                existing.name != candidate.name or existing.exchange != candidate.exchange
            ):
                raise ValueError(f"{label}: inconsistent name or exchange for {symbol}")
            security_meta[str(symbol)] = candidate

            prev_close = (
                _decimal(row["prev_close"], label=f"{label} prev_close", positive=True)
                if row.get("prev_close")
                else None
            )
            turnover = (
                _decimal(row["turnover_value"], label=f"{label} turnover_value")
                if row.get("turnover_value")
                else None
            )
            if turnover is not None and turnover < 0:
                raise ValueError(f"{label} turnover_value: expected a non-negative number")
            bars_by_symbol[str(symbol)].append(
                OHLCVBar(
                    date=bar_date,
                    open=prices["open"],
                    high=prices["high"],
                    low=prices["low"],
                    close=prices["close"],
                    volume=volume,
                    prev_close=prev_close,
                    turnover_value=turnover,
                )
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(str(exc)) from exc

    return list(security_meta.values()), dict(bars_by_symbol)


def parse_actions_csv(path: Path) -> dict[str, list[RawCorporateAction]]:
    """Parse an optional action CSV; an empty ratio deliberately means unadjusted."""
    rows = _rows(path, {"symbol", "ex_date", "type", "ratio"})
    actions: dict[str, list[RawCorporateAction]] = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        label = f"{path}:{line}"
        try:
            symbol = str(Symbol(row["symbol"]))
            ex_date = _date(row["ex_date"], label=f"{label} ex_date")
            action_type = row["type"].strip()
            if not action_type:
                raise ValueError(f"{label}: action type is required")
            ratio = (
                _decimal(row["ratio"], label=f"{label} ratio", positive=True)
                if row["ratio"]
                else None
            )
            actions[symbol].append(
                RawCorporateAction(
                    symbol=symbol,
                    ex_date=ex_date,
                    action_type=action_type,
                    ratio=ratio,
                    raw_subject=row.get("raw_subject", ""),
                )
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(str(exc)) from exc
    return dict(actions)


def parse_benchmark_csv(path: Path) -> tuple[str, list[RawIndexBar]]:
    """Parse one benchmark series from an index_code/date/close CSV."""
    rows = _rows(path, {"index_code", "date", "close"})
    codes = {row["index_code"].upper() for row in rows}
    if len(codes) != 1 or not next(iter(codes)):
        raise ValueError(f"{path}: a benchmark CSV must contain exactly one index_code")
    code = next(iter(codes))
    result: list[RawIndexBar] = []
    seen: set[date] = set()
    for line, row in enumerate(rows, start=2):
        bar_date = _date(row["date"], label=f"{path}:{line} date")
        if bar_date in seen:
            raise ValueError(f"{path}:{line}: duplicate benchmark date {bar_date}")
        seen.add(bar_date)
        result.append(
            RawIndexBar(
                index_code=code,
                date=bar_date,
                close=_decimal(row["close"], label=f"{path}:{line} close", positive=True),
            )
        )
    return code, result


class ImportEodCsv:
    """Persist normalized EOD exports and optional action history atomically."""

    def __init__(
        self,
        security_repo: Any,
        ohlcv_repo: Any,
        corporate_action_repo: Any,
    ) -> None:
        """Bind the security, daily-bar and action repositories."""
        self._security_repo = security_repo
        self._ohlcv_repo = ohlcv_repo
        self._actions_repo = corporate_action_repo

    async def execute(self, bars_path: Path, actions_path: Path | None = None) -> dict[str, int]:
        """Validate and import files as one database transaction."""
        securities, bars_by_symbol = parse_eod_csv(bars_path)
        actions = parse_actions_csv(actions_path) if actions_path is not None else {}
        unknown_actions = set(actions) - set(bars_by_symbol)
        if unknown_actions:
            raise ValueError(
                "Corporate-action symbols must also appear in the EOD file: "
                + ", ".join(sorted(unknown_actions))
            )

        session = getattr(self._ohlcv_repo, "_session", None)
        try:
            existing = {
                str(security.symbol): security
                for security in await self._security_repo.list_all()
            }
            securities = [
                Security(
                    symbol=security.symbol,
                    name=(
                        existing[str(security.symbol)].name
                        if (
                            str(security.symbol) in existing
                            and security.name == str(security.symbol)
                        )
                        else security.name
                    ),
                    isin=security.isin,
                    sector=(
                        existing[str(security.symbol)].sector
                        if str(security.symbol) in existing
                        else None
                    ),
                    industry=(
                        existing[str(security.symbol)].industry
                        if str(security.symbol) in existing
                        else None
                    ),
                    exchange=security.exchange,
                    listing_date=security.listing_date,
                )
                for security in securities
            ]
            await self._security_repo.upsert_many(securities)
            await self._security_repo.set_exchanges(
                {str(security.symbol): security.exchange for security in securities}
            )
            active = {str(s.symbol): s for s in await self._security_repo.list_active()}
            bars_written = 0
            actions_written = 0
            factors_written = 0
            for symbol, bars in bars_by_symbol.items():
                security = active.get(symbol)
                if security is None or security.id is None:
                    raise ValueError(f"Security {symbol} was not persisted")
                bars_written += await self._ohlcv_repo.upsert_bars(security.id, bars)
                if symbol in actions:
                    actions_written += await self._actions_repo.save_many(
                        security.id, actions[symbol]
                    )
                    complete = await self._ohlcv_repo.get_series(
                        security.id, lookback_days=1_000_000, as_of=date.max
                    )
                    factors = compute_adjustment_factors(
                        [bar.date for bar in complete.bars],
                        await self._actions_repo.list_for_security(security.id),
                    )
                    factors_written += await self._ohlcv_repo.update_adjustment_factors(
                        security.id, factors
                    )
            if session is not None:
                await session.commit()
        except Exception:
            if session is not None:
                await session.rollback()
            raise
        return {
            "symbols": len(securities),
            "bars": bars_written,
            "actions": actions_written,
            "adjusted_bars": factors_written,
        }


class ImportBenchmarkCsv:
    """Persist one authorized benchmark close series from a CSV export."""

    def __init__(self, benchmark_repo: Any) -> None:
        """Bind the benchmark repository."""
        self._benchmark_repo = benchmark_repo

    async def execute(self, path: Path) -> dict[str, int | str]:
        """Validate and upsert the benchmark series."""
        code, bars = parse_benchmark_csv(path)
        count = await self._benchmark_repo.upsert_bars(code, bars)
        session = getattr(self._benchmark_repo, "_session", None)
        if session is not None:
            await session.commit()
        return {"index_code": code, "bars": count}
