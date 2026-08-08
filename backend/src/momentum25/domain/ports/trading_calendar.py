"""Trading-calendar port — abstracts exchange session data out of the pure core."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class TradingCalendar(Protocol):
    """Answers which calendar dates are NSE/BSE trading sessions."""

    def is_session(self, day: date) -> bool:
        """Return ``True`` if *day* is a trading session."""
        ...

    def sessions_between(self, start: date, end: date) -> list[date]:
        """Return trading sessions in ``[start, end]`` inclusive, ascending."""
        ...

    def next_session(self, after: date) -> date:
        """Return the first trading session strictly after *after*."""
        ...
