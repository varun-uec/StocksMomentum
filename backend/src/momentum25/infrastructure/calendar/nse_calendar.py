""":class:`TradingCalendar` implementation backed by ``exchange_calendars``.

``exchange_calendars`` ships no ``XNSE`` calendar; NSE and BSE observe the same
set of trading holidays in India, so the ``XBOM`` (BSE) calendar is used as the
NSE trading calendar. This is a documented proxy, not an approximation of NSE's
own calendar from first principles.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import exchange_calendars as xcals

from momentum25.domain.ports.trading_calendar import TradingCalendar

_CALENDAR_CODE = "XBOM"


class NSETradingCalendar:
    """Trading calendar for NSE, backed by the XBOM (BSE) calendar."""

    def __init__(self) -> None:
        """Load the underlying exchange calendar."""
        self._calendar = xcals.get_calendar(_CALENDAR_CODE)

    def is_session(self, day: date) -> bool:
        """Return ``True`` if *day* is a trading session."""
        return bool(self._calendar.is_session(day.isoformat()))

    def sessions_between(self, start: date, end: date) -> list[date]:
        """Return trading sessions in ``[start, end]`` inclusive, ascending."""
        sessions = self._calendar.sessions_in_range(start.isoformat(), end.isoformat())
        return [ts.date() for ts in sessions]

    def next_session(self, after: date) -> date:
        """Return the first trading session strictly after *after*.

        Uses ``date_to_session(..., direction="next")`` rather than
        ``next_session``, which requires its input to already be a session --
        ``after`` is often "today", an arbitrary calendar date that may
        itself be a weekend or holiday.
        """
        candidate = self._calendar.date_to_session(after.isoformat(), direction="next")
        result: date = candidate.date()
        if result == after:
            # after was itself a session; advance to the next one.
            result = self._calendar.next_session(after.isoformat()).date()
        return result


@lru_cache(maxsize=1)
def get_nse_trading_calendar() -> TradingCalendar:
    """Return the process-wide cached NSE trading calendar instance."""
    return NSETradingCalendar()
