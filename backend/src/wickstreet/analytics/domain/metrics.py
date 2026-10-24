"""The MF metric method: NAV-only metrics of one plan-option (ADR-017 MF-8, MF-11).

``docs/current/mf-metrics.md`` is the method spec. Any change that alters a
computed value, a category or a classification bumps ``METHOD_VERSION``, so a
snapshot never mixes two methods.

Dates are ordinals (``date.toordinal``). A NAV is valid when it is a finite number
above zero; other rows are excluded and counted. Flagged jumps are kept and counted.
Cross-fund metrics (category ranks, consistency, scores) are in :mod:`peers`.
"""

from __future__ import annotations

import math
from array import array
from bisect import bisect_right
from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from typing import Literal

# v1: the methodology approved on 2026-10-23. v2: v1 with the option rule fixed after
# the real-data spot check (unclaimed-dividend plans, "IDCW Yield", "RetireInvest").
# v3: Slice 3 adds status, annual returns, drawdown episodes, worst periods, downside
# risk, category ranks, consistency, scores and sibling categories (doc 20 §3).
# v4: doc 21 — SEBI 2026 categories, point-in-time peer groups and rank history,
# persistence, deterioration, direct vs regular, rolling percentiles, current drawdown,
# near-duplicates.
# v5: E2 — the RBI 91-day T-bill yield: risk-free returns, Sharpe 1Y/3Y, Sortino against
# the risk-free rate instead of 0%.
# v6: E1 and E3 — AMFI scheme facts (TER, AUM, riskometer, benchmark, SSD), TER category
# ranks, AMFI benchmark-relative returns, statistics against a labelled index-fund proxy,
# and E4 holdings fields from monthly portfolio disclosures.
METHOD_VERSION = 6
# The longest gap between two valid NAVs an anchor or a window may span.
MAX_GAP_DAYS = 7
# A fund is active when its last valid NAV is this close to the as-of date.
ACTIVE_DAYS = 7
YEAR_DAYS = 365.25
ANNUALISE_VOL = math.sqrt(252)
MIN_SINCE_DAYS = 365
VAR_LEVEL = 0.95
JUMP = "nav_jump"

NO_NAV = "no_nav"
NO_RECENT_NAV = "no_recent_nav"
HISTORY_TOO_SHORT = "history_too_short"
GAP_AT_START = "gap_at_start"
GAP_IN_WINDOW = "gap_in_window"
NOT_RECOVERED = "not_recovered"
NO_DRAWDOWN = "no_drawdown"
ZERO_DENOMINATOR = "zero_denominator"
NO_PEER_GROUP = "no_peer_group"
TOO_FEW_PEERS = "too_few_peers"
NO_PAIR = "no_pair"
NO_RISK_FREE = "no_risk_free"
# Scheme facts (v6): no AMFI scheme joins the plan-option; the scheme did not file the
# value; AMFI's returns are for the growth option; no benchmark, or no index fund for it;
# no value a year back.
NO_SCHEME = "no_scheme_join"
NOT_FILED = "not_filed"
GROWTH_ONLY = "growth_option_only"
NO_BENCHMARK = "no_benchmark"
NO_PROXY = "no_benchmark_proxy"
NO_YEAR_AGO = "no_year_ago_value"
# Holdings (v6): the portfolio holds no equity, so an equity share is not meaningful.
NO_EQUITY = "no_equity"
# A window may end at most this long after the last auction it uses.
RISK_FREE_STALE_DAYS = 35
REASONS = frozenset(
    {
        NO_NAV,
        NO_RECENT_NAV,
        HISTORY_TOO_SHORT,
        GAP_AT_START,
        GAP_IN_WINDOW,
        NOT_RECOVERED,
        NO_DRAWDOWN,
        ZERO_DENOMINATOR,
        NO_PEER_GROUP,
        TOO_FEW_PEERS,
        NO_PAIR,
        NO_RISK_FREE,
        NO_SCHEME,
        NOT_FILED,
        GROWTH_ONLY,
        NO_BENCHMARK,
        NO_PROXY,
        NO_YEAR_AGO,
        NO_EQUITY,
    }
)

ACTIVE, HISTORICAL = "active", "historical"
STATUSES = (ACTIVE, HISTORICAL, NO_NAV)


@dataclass(frozen=True, slots=True)
class Missing:
    """No value: not available (``NA``) or not meaningful (``NM``), and why."""

    state: Literal["NA", "NM"]
    reason: str


Value = float | int | bool | str | Missing

# (field, calendar months back from the as-of date, annualised)
TRAILING = (
    ("ret_1m", 1, False),
    ("ret_3m", 3, False),
    ("ret_6m", 6, False),
    ("ret_1y", 12, False),
    ("cagr_3y", 36, True),
    ("cagr_5y", 60, True),
    ("cagr_10y", 120, True),
)
ROLLING = (("rolling_1y", 12), ("rolling_3y", 36), ("rolling_5y", 60))
ROLLING_STATS = (
    "count",
    "mean",
    "median",
    "min",
    "max",
    "positive_share",
    "p10",
    "p25",
    "p75",
    "p90",
)
# (stat, quantile) by nearest rank, as for VaR.
PERCENTILES = (("p10", 0.10), ("p25", 0.25), ("p75", 0.75), ("p90", 0.90))
VOLATILITY = (("vol_1y", 12), ("vol_3y", 36))
DRAWDOWN = (("mdd_1y", 12), ("mdd_3y", 36))
SINCE = ("since_start", "ret_since", "cagr_since", "mdd_since")
LATEST = ("status", "active", "nav", "last_nav_date", "excluded_navs", "jump_flags")
ANNUAL = (
    "ret_ytd",
    "ret_cy_last",
    "ret_fy_last",
    "cy_best",
    "cy_worst",
    "cy_positive_share",
    "cy_count",
)
# (prefix, months back; None = the whole stored history)
EPISODES = (("dd_3y", 36), ("dd_since", None))
EPISODE_STATS = ("peak", "trough", "recovery", "fall_days", "recovery_days")
WORST = (("worst_1m", 1), ("worst_3m", 3), ("worst_1y", 12))
DOWNSIDE = ("downside_dev_3y", "sortino_3y", "var95_3y", "cvar95_3y", "ret_risk_3y")
UNDERWATER = ("dd_now", "dd_now_days", "underwater_max_days")
RISK_FREE = ("rf_1y", "rf_3y", "sharpe_1y", "sharpe_3y")
METRIC_FIELDS = (
    *LATEST,
    *(name for name, _, _ in TRAILING),
    *SINCE,
    *ANNUAL,
    *(name for name, _ in VOLATILITY),
    *(name for name, _ in DRAWDOWN),
    *(f"{name}_{stat}" for name, _ in EPISODES for stat in EPISODE_STATS),
    *(name for name, _ in WORST),
    *DOWNSIDE,
    *UNDERWATER,
    *RISK_FREE,
    *(f"{name}_{stat}" for name, _ in ROLLING for stat in ROLLING_STATS),
)


def _floats() -> array[float]:
    return array("d")


@dataclass(frozen=True, slots=True)
class MonthEnds:
    """A fund's values at each complete month-end it was alive (method v4).

    Parallel arrays: ``months`` (year × 12 + month - 1), the NAV, the trailing 1Y return
    and the trailing 3Y CAGR at the fund's last valid NAV of the month (``nan`` when the
    window has no start anchor). Arrays keep 40k funds small.
    """

    months: array[int] = field(default_factory=lambda: array("l"))
    navs: array[float] = field(default_factory=_floats)
    ret_1y: array[float] = field(default_factory=_floats)
    cagr_3y: array[float] = field(default_factory=_floats)


@dataclass(frozen=True, slots=True)
class FundMetrics:
    """Every metric of one fund, its trailing anchors and the inputs of cross-fund fields.

    ``then`` holds ``ret_1y``, ``vol_3y`` and ``mdd_3y`` one year before the as-of date,
    for funds alive then. ``days`` and ``levels`` are the valid NAVs of an active fund's 3Y
    window, from its start anchor, for near-duplicates.
    """

    values: dict[str, Value]
    anchors: dict[str, str]
    month_ends: MonthEnds = field(default_factory=MonthEnds)
    then: dict[str, float] = field(default_factory=dict)
    days: array[int] = field(default_factory=lambda: array("i"))
    levels: array[float] = field(default_factory=_floats)


@cache
def months_back(ordinal: int, months: int) -> int:
    """The date ``months`` calendar months earlier, its day clamped to the month end."""
    day = date.fromordinal(ordinal)
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    return date(year, month, min(day.day, monthrange(year, month)[1])).toordinal()


@cache
def month_key(ordinal: int) -> int:
    """Year × 12 + month - 1: one key per calendar month."""
    day = date.fromordinal(ordinal)
    return day.year * 12 + day.month - 1


def _iso(ordinal: int) -> str:
    return date.fromordinal(ordinal).isoformat()


def _cagr(start: float, end: float, days: int) -> float:
    return math.pow(end / start, YEAR_DAYS / days) - 1


def valid_series(
    points: Sequence[tuple[int, float | None, str | None]],
) -> tuple[list[int], list[float], int, int]:
    """Dates and NAVs of the valid points, and the excluded and jump counts."""
    dates: list[int] = []
    navs: list[float] = []
    excluded = jumps = 0
    for day, nav, anomaly in points:
        if anomaly == JUMP:
            jumps += 1
        if nav is None or not math.isfinite(nav) or nav <= 0:
            excluded += 1
            continue
        dates.append(day)
        navs.append(nav)
    return dates, navs, excluded, jumps


def start_anchor(dates: Sequence[int], target: int) -> int | Missing:
    """The last valid NAV on or before ``target``, at most ``MAX_GAP_DAYS`` before it."""
    index = bisect_right(dates, target) - 1
    if index < 0:
        return Missing("NA", HISTORY_TOO_SHORT)
    if target - dates[index] > MAX_GAP_DAYS:
        return Missing("NA", GAP_AT_START)
    return index


def _has_gap(dates: Sequence[int], start: int, end: int) -> bool:
    return any(dates[k] - dates[k - 1] > MAX_GAP_DAYS for k in range(start + 1, end + 1))


def _returns(
    dates: Sequence[int], navs: Sequence[float], start: int, end: int
) -> list[float] | Missing:
    """Simple returns between consecutive NAVs in [start, end]; needs 2 and no gap."""
    if end - start < 2:
        return Missing("NA", HISTORY_TOO_SHORT)
    if _has_gap(dates, start, end):
        return Missing("NM", GAP_IN_WINDOW)
    return [navs[k] / navs[k - 1] - 1 for k in range(start + 1, end + 1)]


def volatility(dates: Sequence[int], navs: Sequence[float], start: int, end: int) -> Value:
    """Sample standard deviation of returns between consecutive NAVs, times √252."""
    returns = _returns(dates, navs, start, end)
    if isinstance(returns, Missing):
        return returns
    mean = math.fsum(returns) / len(returns)
    variance = math.fsum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * ANNUALISE_VOL


@dataclass(frozen=True, slots=True)
class RiskFree:
    """The 91-day T-bill yield as a deposit that accrues yield ÷ 365 each calendar day.

    Each auction's yield is in force from its date to the next auction. ``growth[k]``
    is the log growth from the first auction to auction k (method v5).
    """

    days: Sequence[int]
    daily: Sequence[float]
    growth: Sequence[float]

    @classmethod
    def of(cls, points: Sequence[tuple[int, float]]) -> RiskFree:
        """From (date ordinal, % a year) in date order."""
        days = [d for d, _ in points]
        daily = [math.log1p(y / 100 / 365) for _, y in points]
        growth = [0.0]
        for k in range(1, len(days)):
            growth.append(growth[-1] + (days[k] - days[k - 1]) * daily[k - 1])
        return cls(days, daily, growth)

    def _log(self, day: int) -> float:
        k = bisect_right(self.days, day) - 1
        return self.growth[k] + (day - self.days[k]) * self.daily[k]

    def covers(self, start: int, end: int) -> bool:
        """Whether an auction precedes ``start`` and a recent one precedes ``end``."""
        if not self.days or start < self.days[0]:
            return False
        last = self.days[bisect_right(self.days, end) - 1]
        return end - last <= RISK_FREE_STALE_DAYS

    def growth_between(self, start: int, end: int) -> float:
        """The deposit's return from ``start`` to ``end``; check :meth:`covers` first."""
        return math.expm1(self._log(end) - self._log(start))

    def annualised(self, start: int, end: int) -> Value:
        """The deposit's annualised return over [start, end], on 365.25-day years."""
        if not self.covers(start, end) or end <= start:
            return Missing("NA", NO_RISK_FREE)
        return math.expm1((self._log(end) - self._log(start)) * YEAR_DAYS / (end - start))


def downside(
    dates: Sequence[int],
    navs: Sequence[float],
    start: int,
    end: int,
    risk_free: RiskFree | None = None,
) -> tuple[Value, Value, Value, Value]:
    """Downside deviations (× √252), and 1-day historical VaR and CVaR at 95%.

    The first deviation has a 0% threshold. The second's threshold is the risk-free
    return over each interval (``NA no_risk_free`` without a covering series). VaR is
    the return at the 5th percentile (nearest rank); CVaR is the mean of the returns at
    or below it. Both are returns, so a loss is negative.
    """
    returns = _returns(dates, navs, start, end)
    if isinstance(returns, Missing):
        return returns, returns, returns, returns
    deviation = math.sqrt(math.fsum(min(r, 0.0) ** 2 for r in returns) / len(returns))
    excess: Value = Missing("NA", NO_RISK_FREE)
    if risk_free is not None and risk_free.covers(dates[start], dates[end]):
        below = [
            min(r - risk_free.growth_between(dates[k], dates[k + 1]), 0.0) ** 2
            for k, r in zip(range(start, end), returns, strict=True)
        ]
        excess = math.sqrt(math.fsum(below) / len(below)) * ANNUALISE_VOL
    ordered = sorted(returns)
    k = math.ceil((1 - VAR_LEVEL) * len(ordered))
    return deviation * ANNUALISE_VOL, excess, ordered[k - 1], math.fsum(ordered[:k]) / k


@dataclass(frozen=True, slots=True)
class Episode:
    """The deepest fall in a window: its depth and the indices of peak, trough and recovery."""

    depth: float
    peak: int
    trough: int
    recovery: int | None


def deepest(dates: Sequence[int], navs: Sequence[float], start: int, end: int) -> Episode | Missing:
    """The largest fall from a running peak; recovery is the first NAV back at the peak."""
    if _has_gap(dates, start, end):
        return Missing("NM", GAP_IN_WINDOW)
    peak = worst_peak = worst_trough = start
    worst = 0.0
    for k in range(start + 1, end + 1):
        nav = navs[k]
        if nav > navs[peak]:
            peak = k
        elif nav / navs[peak] - 1 < worst:
            worst, worst_peak, worst_trough = nav / navs[peak] - 1, peak, k
    recovery = next(
        (k for k in range(worst_trough + 1, end + 1) if navs[k] >= navs[worst_peak]), None
    )
    return Episode(worst, worst_peak, worst_trough, recovery)


def drawdown(dates: Sequence[int], navs: Sequence[float], start: int, end: int) -> Value:
    """The largest fall from a running peak, as a fraction (always <= 0)."""
    episode = deepest(dates, navs, start, end)
    return episode if isinstance(episode, Missing) else episode.depth


def _episode_values(
    name: str, episode: Episode | Missing, dates: Sequence[int]
) -> dict[str, Value]:
    if isinstance(episode, Missing):
        return {f"{name}_{stat}": episode for stat in EPISODE_STATS}
    if episode.depth == 0:
        none = Missing("NA", NO_DRAWDOWN)
        return {f"{name}_{stat}": none for stat in EPISODE_STATS}
    values: dict[str, Value] = {
        f"{name}_peak": _iso(dates[episode.peak]),
        f"{name}_trough": _iso(dates[episode.trough]),
        f"{name}_fall_days": dates[episode.trough] - dates[episode.peak],
    }
    if episode.recovery is None:
        values[f"{name}_recovery"] = values[f"{name}_recovery_days"] = Missing("NA", NOT_RECOVERED)
    else:
        values[f"{name}_recovery"] = _iso(dates[episode.recovery])
        values[f"{name}_recovery_days"] = dates[episode.recovery] - dates[episode.trough]
    return values


def window_points(
    dates: Sequence[int], navs: Sequence[float], months: int, annualised: bool
) -> list[tuple[int, float]]:
    """(end index, return) of every ``months`` window with a valid start anchor.

    Targets only move forward, so the anchor index does too: one pass per window.
    """
    points: list[tuple[int, float]] = []
    anchor = 0
    for j, day in enumerate(dates):
        target = months_back(day, months)
        if target < dates[0]:
            continue
        while dates[anchor + 1] <= target:
            anchor += 1
        if target - dates[anchor] > MAX_GAP_DAYS:
            continue
        if annualised:
            points.append((j, _cagr(navs[anchor], navs[j], day - dates[anchor])))
        else:
            points.append((j, navs[j] / navs[anchor] - 1))
    return points


def nearest_rank(ordered: Sequence[float], quantile: float) -> float:
    """The ⌈quantile × n⌉-th lowest of ``ordered`` (sorted, not empty)."""
    return ordered[max(math.ceil(quantile * len(ordered)), 1) - 1]


def rolling_summary(values: list[float]) -> dict[str, Value]:
    """count, mean, median, min, max, share > 0 and nearest-rank percentiles.

    The median of an even count is the mean of the middle two.
    """
    if not values:
        missing = Missing("NA", HISTORY_TOO_SHORT)
        empty: dict[str, Value] = {"count": 0}
        return empty | dict.fromkeys(ROLLING_STATS[1:], missing)
    values = sorted(values)
    n = len(values)
    middle = n // 2
    median = values[middle] if n % 2 else (values[middle - 1] + values[middle]) / 2
    return {
        "count": n,
        "mean": math.fsum(values) / n,
        "median": median,
        "min": values[0],
        "max": values[-1],
        "positive_share": sum(1 for p in values if p > 0) / n,
        **{stat: nearest_rank(values, q) for stat, q in PERCENTILES},
    }


def rolling(dates: Sequence[int], navs: Sequence[float], months: int) -> dict[str, Value]:
    """Summary of the annualised return over every ``months`` window in the history."""
    return rolling_summary([v for _, v in window_points(dates, navs, months, True)])


def year_returns(
    dates: Sequence[int], navs: Sequence[float], until: int, end_month: int
) -> list[tuple[int, float]]:
    """(end year, return) of each complete year ending on ``end_month``'s last day.

    ``end_month`` 12 gives calendar years; 3 gives April–March financial years. A year
    counts when both its ends have a start anchor and it ends on or before ``until``.
    """
    found: list[tuple[int, float]] = []
    previous: int | None = None
    for year in range(date.fromordinal(dates[0]).year, date.fromordinal(until).year + 1):
        end_day = date(year, end_month, monthrange(year, end_month)[1]).toordinal()
        if end_day > until:
            break
        index = start_anchor(dates, end_day)
        if isinstance(index, Missing):
            previous = None
            continue
        if previous is not None:
            found.append((year, navs[index] / navs[previous] - 1))
        previous = index
    return found


def last_complete_month(as_of: int) -> int:
    """The month key of the last month whose last day is on or before ``as_of``."""
    day = date.fromordinal(as_of)
    complete = day.day == monthrange(day.year, day.month)[1]
    return month_key(as_of) - (0 if complete else 1)


def _month_last_day(key: int) -> int:
    year, month = divmod(key, 12)
    return date(year, month + 1, monthrange(year, month + 1)[1]).toordinal()


def month_end_values(dates: Sequence[int], navs: Sequence[float], as_of: int) -> MonthEnds:
    """The fund's NAV, 1Y return and 3Y CAGR at each complete month-end it was alive.

    Alive means its last valid NAV of the month is within ``MAX_GAP_DAYS`` of the
    month's last day (method v4, M1).
    """
    found = MonthEnds()
    if not dates:
        return found
    one = dict(window_points(dates, navs, 12, False))
    three = dict(window_points(dates, navs, 36, True))
    last = last_complete_month(as_of)
    for j, day in enumerate(dates):
        key = month_key(day)
        if key > last:
            break
        if j + 1 < len(dates) and month_key(dates[j + 1]) == key:
            continue
        if _month_last_day(key) - day > MAX_GAP_DAYS:
            continue
        found.months.append(key)
        found.navs.append(navs[j])
        found.ret_1y.append(one.get(j, math.nan))
        found.cagr_3y.append(three.get(j, math.nan))
    return found


def _then(dates: Sequence[int], navs: Sequence[float], as_of: int) -> dict[str, float]:
    """ret_1y, vol_3y and mdd_3y one year before ``as_of``, when the fund was alive then."""
    target = months_back(as_of, 12)
    end = start_anchor(dates, target)
    if isinstance(end, Missing):
        return {}
    found: dict[str, float] = {}
    one = start_anchor(dates, months_back(target, 12))
    if not isinstance(one, Missing):
        found["ret_1y"] = navs[end] / navs[one] - 1
    three = start_anchor(dates, months_back(target, 36))
    if not isinstance(three, Missing):
        for name, value in (
            ("vol_3y", volatility(dates, navs, three, end)),
            ("mdd_3y", drawdown(dates, navs, three, end)),
        ):
            if not isinstance(value, Missing):
                found[name] = float(value)
    return found


def _underwater(dates: Sequence[int], navs: Sequence[float], active: bool) -> dict[str, Value]:
    """Current fall from the running peak, days since that peak, longest time below a peak.

    A stretch below a peak ends at the first NAV back at the peak, or at the last NAV
    when it has not recovered.
    """
    peak = longest = 0
    for k in range(1, len(navs)):
        if navs[k] >= navs[peak]:
            longest = max(longest, dates[k] - dates[peak])
            peak = k
    longest = max(longest, dates[-1] - dates[peak])
    values: dict[str, Value] = {"underwater_max_days": longest}
    if active:
        values |= {"dd_now": navs[-1] / navs[peak] - 1, "dd_now_days": dates[-1] - dates[peak]}
    else:
        values |= dict.fromkeys(("dd_now", "dd_now_days"), Missing("NA", NO_RECENT_NAV))
    return values


def _ratio(numerator: Value, denominator: Value) -> Value:
    if isinstance(numerator, Missing):
        return numerator
    if isinstance(denominator, Missing):
        return denominator
    if denominator == 0:
        return Missing("NM", ZERO_DENOMINATOR)
    return float(numerator) / float(denominator)


def _annual(
    dates: Sequence[int], navs: Sequence[float], as_of: int, active: bool
) -> dict[str, Value]:
    today = date.fromordinal(as_of)
    calendar = dict(year_returns(dates, navs, as_of, 12))
    financial = dict(year_returns(dates, navs, as_of, 3))
    absent = Missing("NA", HISTORY_TOO_SHORT if active else NO_RECENT_NAV)
    fy_end = today.year if as_of >= date(today.year, 3, 31).toordinal() else today.year - 1
    values: dict[str, Value] = {
        "ret_cy_last": calendar.get(today.year - 1, absent),
        "ret_fy_last": financial.get(fy_end, absent),
        "cy_count": len(calendar),
    }
    year_end = start_anchor(dates, date(today.year - 1, 12, 31).toordinal())
    if not active:
        values["ret_ytd"] = Missing("NA", NO_RECENT_NAV)
    elif isinstance(year_end, Missing):
        values["ret_ytd"] = year_end
    else:
        values["ret_ytd"] = navs[-1] / navs[year_end] - 1
    if calendar:
        years = list(calendar.values())
        values |= {
            "cy_best": max(years),
            "cy_worst": min(years),
            "cy_positive_share": sum(1 for r in years if r > 0) / len(years),
        }
    else:
        none = Missing("NA", HISTORY_TOO_SHORT)
        values |= {"cy_best": none, "cy_worst": none, "cy_positive_share": none}
    return values


def _excess(ret: Value, rf: Value) -> Value:
    if isinstance(ret, Missing):
        return ret
    if isinstance(rf, Missing):
        return rf
    return float(ret) - float(rf)


def compute(
    points: Sequence[tuple[int, float | None, str | None]],
    as_of: int,
    risk_free: RiskFree | None = None,
) -> FundMetrics:
    """Every per-fund metric at ``as_of``, the latest NAV date in the store."""
    dates, navs, excluded, jumps = valid_series(points)
    values: dict[str, Value] = {"excluded_navs": excluded, "jump_flags": jumps}
    anchors: dict[str, str] = {}
    if not dates:
        missing = Missing("NA", NO_NAV)
        values |= {name: missing for name in METRIC_FIELDS if name not in values}
        values |= {"active": False, "status": NO_NAV}
        return FundMetrics(values, anchors)

    end = len(dates) - 1
    active = as_of - dates[end] <= ACTIVE_DAYS
    span = dates[end] - dates[0]
    values |= {
        "status": ACTIVE if active else HISTORICAL,
        "active": active,
        "nav": navs[end],
        "last_nav_date": _iso(dates[end]),
        "since_start": _iso(dates[0]),
        "ret_since": navs[end] / navs[0] - 1,
        "cagr_since": (
            _cagr(navs[0], navs[end], span)
            if span >= MIN_SINCE_DAYS
            else Missing("NA", HISTORY_TOO_SHORT)
        ),
    }
    since = deepest(dates, navs, 0, end)
    values["mdd_since"] = since if isinstance(since, Missing) else since.depth
    values |= _episode_values("dd_since", since, dates)
    values |= _annual(dates, navs, as_of, active)

    starts: dict[int, int | Missing] = {}
    for months in {m for _, m, _ in TRAILING}:
        starts[months] = (
            start_anchor(dates, months_back(as_of, months))
            if active
            else Missing("NA", NO_RECENT_NAV)
        )
    for name, months, annualised in TRAILING:
        start = starts[months]
        if isinstance(start, Missing):
            values[name] = start
            continue
        anchors[name] = _iso(dates[start])
        values[name] = (
            _cagr(navs[start], navs[end], dates[end] - dates[start])
            if annualised
            else navs[end] / navs[start] - 1
        )
    for name, months in VOLATILITY:
        start = starts[months]
        values[name] = start if isinstance(start, Missing) else volatility(dates, navs, start, end)
    for name, months in DRAWDOWN:
        start = starts[months]
        values[name] = start if isinstance(start, Missing) else drawdown(dates, navs, start, end)
    three = starts[36]
    episode = three if isinstance(three, Missing) else deepest(dates, navs, three, end)
    values |= _episode_values("dd_3y", episode, dates)
    rf = risk_free or RiskFree.of([])
    for name, months in (("rf_1y", 12), ("rf_3y", 36)):
        start = starts[months]
        values[name] = (
            start if isinstance(start, Missing) else rf.annualised(dates[start], dates[end])
        )
    excess_dev: Value = three
    if isinstance(three, Missing):
        values |= {"downside_dev_3y": three, "var95_3y": three, "cvar95_3y": three}
    else:
        deviation, excess_dev, var, cvar = downside(dates, navs, three, end, rf)
        values |= {"downside_dev_3y": deviation, "var95_3y": var, "cvar95_3y": cvar}
    excess_3y = _excess(values["cagr_3y"], values["rf_3y"])
    values["sortino_3y"] = _ratio(excess_3y, excess_dev)
    values["sharpe_3y"] = _ratio(excess_3y, values["vol_3y"])
    values["sharpe_1y"] = _ratio(_excess(values["ret_1y"], values["rf_1y"]), values["vol_1y"])
    values["ret_risk_3y"] = _ratio(values["cagr_3y"], values["vol_3y"])
    values |= _underwater(dates, navs, active)
    days: array[int] = array("i")
    levels: array[float] = array("d")
    if active and not isinstance(three, Missing):
        days.extend(dates[three : end + 1])
        levels.extend(navs[three : end + 1])

    for name, months in WORST:
        worst = [v for _, v in window_points(dates, navs, months, False)]
        values[name] = min(worst) if worst else Missing("NA", HISTORY_TOO_SHORT)
    for name, months in ROLLING:
        points_ = window_points(dates, navs, months, True)
        for stat, value in rolling_summary([v for _, v in points_]).items():
            values[f"{name}_{stat}"] = value
    return FundMetrics(
        values,
        anchors,
        month_end_values(dates, navs, as_of),
        _then(dates, navs, as_of),
        days,
        levels,
    )


def rebase(
    points: Sequence[tuple[int, float | None, str | None]], start: int
) -> list[tuple[str, float]]:
    """Valid NAVs from ``start`` on, scaled to 100 at the first of them."""
    valid = [
        (d, n) for d, n, _ in points if d >= start and n is not None and math.isfinite(n) and n > 0
    ]
    if not valid:
        return []
    base = valid[0][1]
    return [(_iso(d), n / base * 100) for d, n in valid]
