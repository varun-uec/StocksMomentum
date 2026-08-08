"""Watchlist use-case tests (Phase 6.9) — add/remove/list against a fake repo."""

from __future__ import annotations

import pytest

from momentum25.application.use_cases.watchlist import (
    AddToWatchlist,
    GetWatchlist,
    RemoveFromWatchlist,
)
from momentum25.domain.entities.security import Security
from momentum25.domain.errors import NotFoundError
from momentum25.domain.value_objects.types import Symbol

_SECURITIES = {"TATATECH": 11, "INFY": 22}


class FakeSecurityRepository:
    """Only the one method the watchlist use cases depend on."""

    async def get_by_symbol(self, symbol: str) -> Security | None:
        security_id = _SECURITIES.get(symbol.upper())
        if security_id is None:
            return None
        return Security(
            id=security_id, symbol=Symbol(symbol.upper()), name=symbol.upper(), isin=None
        )


class FakeWatchlistRepository:
    """In-memory, insertion-ordered, set-semantics watchlist."""

    def __init__(self) -> None:
        self.ids: list[int] = []

    async def add(self, security_id: int) -> None:
        if security_id not in self.ids:
            self.ids.append(security_id)

    async def remove(self, security_id: int) -> None:
        if security_id in self.ids:
            self.ids.remove(security_id)

    async def list_symbols(self) -> list[str]:
        by_id = {v: k for k, v in _SECURITIES.items()}
        return [by_id[i] for i in self.ids]


@pytest.mark.asyncio
async def test_add_remove_list_round_trip() -> None:
    """Add/list/remove round-trips and preserves insertion order."""
    watchlist = FakeWatchlistRepository()
    securities = FakeSecurityRepository()
    add = AddToWatchlist(securities=securities, watchlist=watchlist)
    remove = RemoveFromWatchlist(securities=securities, watchlist=watchlist)
    read = GetWatchlist(watchlist=watchlist)

    assert await read.execute() == []

    await add.execute("TATATECH")
    await add.execute("INFY")
    assert await read.execute() == ["TATATECH", "INFY"]

    await remove.execute("TATATECH")
    assert await read.execute() == ["INFY"]


@pytest.mark.asyncio
async def test_add_is_idempotent() -> None:
    """Starring an already-starred symbol must not duplicate it."""
    watchlist = FakeWatchlistRepository()
    add = AddToWatchlist(securities=FakeSecurityRepository(), watchlist=watchlist)

    await add.execute("INFY")
    await add.execute("infy")  # case-insensitive resolution, same security
    assert watchlist.ids == [22]


@pytest.mark.asyncio
async def test_remove_absent_symbol_is_a_no_op() -> None:
    """Un-starring something never starred is not an error."""
    watchlist = FakeWatchlistRepository()
    remove = RemoveFromWatchlist(securities=FakeSecurityRepository(), watchlist=watchlist)
    await remove.execute("INFY")
    assert watchlist.ids == []


@pytest.mark.asyncio
async def test_unknown_symbol_raises_not_found() -> None:
    """An unknown symbol must not silently create a dangling watchlist row."""
    watchlist = FakeWatchlistRepository()
    add = AddToWatchlist(securities=FakeSecurityRepository(), watchlist=watchlist)
    with pytest.raises(NotFoundError):
        await add.execute("NOSUCHSYMBOL")
    assert watchlist.ids == []
