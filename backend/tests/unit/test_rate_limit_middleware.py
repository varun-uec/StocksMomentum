"""Tests for :class:`RateLimitMiddleware` (Phase 1.3 defect fixes).

Covers the two real defects found while auditing it: an idle client IP was
never evicted (unbounded memory growth under scan traffic), and the window
was measured with ``time.perf_counter()``, a process-relative clock with no
fixed meaning across dispatch calls.
"""

from __future__ import annotations

from momentum25.interface.api.middleware import RateLimitMiddleware


def _middleware() -> RateLimitMiddleware:
    return RateLimitMiddleware(app=object(), max_requests=5, window_seconds=10)


def test_idle_clients_are_evicted_after_a_window() -> None:
    mw = _middleware()
    base = 1_000_000.0
    mw._requests["1.2.3.4"] = [base]
    mw._last_sweep = base

    # Still within the window: not swept yet.
    mw._sweep_idle_clients(base + 5)
    assert "1.2.3.4" in mw._requests

    # Past the window with no new activity from that IP: evicted.
    mw._sweep_idle_clients(base + 11)
    assert "1.2.3.4" not in mw._requests


def test_active_clients_survive_a_sweep() -> None:
    mw = _middleware()
    base = 1_000_000.0
    mw._requests["5.6.7.8"] = [base + 9]  # request just before the sweep fires
    mw._last_sweep = base

    mw._sweep_idle_clients(base + 11)
    assert "5.6.7.8" in mw._requests


def test_cleanup_uses_wall_clock_not_perf_counter() -> None:
    mw = _middleware()
    now = 2_000_000.0
    mw._requests["9.9.9.9"] = [now - 3]  # inside the 10s window
    mw._cleanup("9.9.9.9", now)
    assert mw._requests["9.9.9.9"] == [now - 3]

    mw._cleanup("9.9.9.9", now + 11)  # now outside the window
    assert mw._requests["9.9.9.9"] == []
