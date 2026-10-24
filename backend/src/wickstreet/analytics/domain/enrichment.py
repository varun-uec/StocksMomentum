"""Fund facts, costs and benchmark analytics from AMFI scheme facts (doc 21 C12, C14, C15).

Method v6. ``docs/current/mf-metrics.md`` §Fund facts is the spec. Two kinds of value:

- **As filed.** TER, AUM, riskometer, benchmark, scheme and benchmark returns and the
  information ratio are AMFI's own figures. A plan-option joins its AMFI scheme
  through the ISINs the scheme's SSD lists. TER and AMFI's returns are per plan
  (regular or direct); AMFI's returns are for the growth option.
- **Against a labelled proxy.** AMFI publishes no benchmark TRI series that Wickstreet
  may store. Beta, alpha, tracking error, information ratio and capture ratios are
  computed against the NAV of an index fund that tracks the same benchmark: the one
  with the lowest AMFI-filed tracking error. Its NAV carries its TER and tracking
  error, so a proxy figure is not an index figure, and the field labels say so.
"""

from __future__ import annotations

import math
import re
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from wickstreet.analytics.domain.classify import DIRECT, ETF, GROWTH, REGULAR
from wickstreet.analytics.domain.fieldspec import Field
from wickstreet.analytics.domain.metrics import (
    ANNUALISE_VOL,
    GROWTH_ONLY,
    HISTORY_TOO_SHORT,
    MAX_GAP_DAYS,
    NO_PROXY,
    NO_RISK_FREE,
    NO_SCHEME,
    NO_YEAR_AGO,
    NOT_FILED,
    NOT_IDCW,
    TOO_FEW_PEERS,
    YEAR_DAYS,
    Missing,
    RiskFree,
    Value,
)
from wickstreet.analytics.domain.peers import rank_all
from wickstreet.analytics.domain.relations import DailyNavs
from wickstreet.mf_data.domain.reads import FactPoint, FactView

# Common daily returns a proxy statistic needs over the 3Y window; months for capture.
MIN_COMMON_DAYS = 500
MIN_SIDE_MONTHS = 6
# A year-ago value must be this close to the date one year back.
YEAR_AGO_TOLERANCE_DAYS = 45
PEERS_MIN = 5
RISKOMETER = ("Low", "Low to Moderate", "Moderate", "Moderately High", "High", "Very High")
_LEVEL = {name.lower(): i + 1 for i, name in enumerate(RISKOMETER)}
HORIZONS = ("1y", "3y", "5y", "10y")
IR_HORIZONS = ("1y", "3y", "5y")
PROXY_FIELDS = (
    "beta_3y",
    "alpha_3y",
    "te_3y",
    "ir_3y_proxy",
    "up_capture_3y",
    "down_capture_3y",
    "r2_3y",
)

_PERCENT = 100.0
_MONTH_NAMES = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_MONTHS = {m: i + 1 for i, m in enumerate(_MONTH_NAMES)}
_DATE = re.compile(
    r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?[\s/.\-]+(\d{1,2}|[A-Za-z]{3,9})\.?[\s/.\-,]+(\d{4})(?!\d)"
    r"|\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})(?!\d)"
    r"|(?<!\d)(\d{1,2})[\s/\-]+([A-Za-z]{3,9})[\s/\-,]+(\d{2})(?!\d)"
)
_MANAGER = re.compile(r"([A-Z][A-Za-z.'’ ]*?[A-Za-z])\s*(?:\(|[-–:,]|since|w\.e\.f\.?)+\s*")
_AMOUNT = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SIP = re.compile(r"SIP[^0-9]{0,40}?(\d[\d,]*)", re.I)
_BENCH_NOISE = re.compile(r"totalreturns?index|totalreturns?|tri|index|^sandp|^sp(?=bse)")

FACT_FIELDS = (
    Field("ter", "TER", "Costs", "number", "fraction", "Total expense ratio as filed with AMFI."),
    Field("ter_base", "Base TER", "Costs", "number", "fraction", "Base expense ratio as filed."),
    Field("ter_as_of", "TER date", "Costs", "date", None, "Day the TER was filed for."),
    Field(
        "ter_change_1y",
        "TER change 1Y",
        "Costs",
        "number",
        "fraction",
        "TER now less the TER filed a year before.",
    ),
    Field(
        "ter_cat_pct",
        "TER category percentile",
        "Costs",
        "number",
        "percentile",
        "100 = cheapest among active peers with a TER.",
    ),
    Field(
        "ter_cat_median",
        "TER category median",
        "Costs",
        "number",
        "fraction",
        "Median TER of the active peers.",
    ),
    Field("aum_cr", "AUM", "Profile", "number", "INR crore", "Scheme AUM as AMFI reports it."),
    Field("aum_as_of", "AUM date", "Profile", "date", None, "Day AMFI reported the AUM for."),
    Field(
        "aum_change_1y",
        "AUM change 1Y",
        "Profile",
        "number",
        "fraction",
        "AUM growth from the AMFI report a year before.",
    ),
    Field("riskometer", "Riskometer", "Profile", "enum", None, "SEBI riskometer as AMFI shows it."),
    Field(
        "riskometer_level", "Riskometer level", "Profile", "number", None, "1 = Low, 6 = Very High."
    ),
    Field("benchmark", "Benchmark", "Profile", "enum", None, "Tier 1 benchmark as AMFI shows it."),
    Field("manager_count", "Fund managers", "Profile", "number", "count", "Managers in the SSD."),
    Field(
        "manager_tenure_y",
        "Longest manager tenure",
        "Profile",
        "number",
        "years",
        "Years since the earliest manager start date filed in the SSD ('since inception' "
        "is the allotment date).",
    ),
    Field("inception", "Allotment date", "Profile", "date", None, "Allotment date in the SSD."),
    Field("min_lumpsum", "Minimum lump sum", "Profile", "number", "INR", "As filed in the SSD."),
    Field("min_sip", "Minimum SIP", "Profile", "number", "INR", "Monthly SIP minimum in the SSD."),
    *(
        Field(
            f"bench_ret_{h}",
            f"Benchmark return {h.upper()}",
            "Benchmark",
            "number",
            "fraction",
            f"AMFI's {h.upper()} return of the Tier 1 benchmark TRI, a year where over 1Y.",
        )
        for h in HORIZONS
    ),
    *(
        Field(
            f"excess_{h}",
            f"Return over benchmark {h.upper()}",
            "Benchmark",
            "number",
            "fraction",
            f"AMFI's {h.upper()} scheme return for the plan less the benchmark's.",
        )
        for h in HORIZONS
    ),
    *(
        Field(
            f"ir_{h}",
            f"Information ratio {h.upper()}",
            "Benchmark",
            "number",
            "ratio",
            f"AMFI's {h.upper()} information ratio for the plan.",
        )
        for h in IR_HORIZONS
    ),
    Field("perf_as_of", "Benchmark data date", "Benchmark", "date", None, "AMFI report date."),
    Field(
        "tracking_error",
        "Tracking error (filed)",
        "Benchmark",
        "number",
        "fraction",
        "Index funds and ETFs: tracking error as filed with AMFI.",
    ),
    Field("beta_3y", "Beta 3Y (proxy)", "Benchmark", "number", "ratio", "Against the proxy NAV."),
    Field(
        "alpha_3y",
        "Alpha 3Y (proxy)",
        "Benchmark",
        "number",
        "fraction",
        "CAGR less risk-free less beta times the proxy's excess CAGR, a year.",
    ),
    Field(
        "te_3y",
        "Tracking error 3Y (proxy)",
        "Benchmark",
        "number",
        "fraction",
        "Annualised standard deviation of daily returns less the proxy's.",
    ),
    Field(
        "ir_3y_proxy",
        "Information ratio 3Y (proxy)",
        "Benchmark",
        "number",
        "ratio",
        "CAGR less the proxy's CAGR, over the proxy tracking error.",
    ),
    Field(
        "up_capture_3y",
        "Upside capture 3Y (proxy)",
        "Benchmark",
        "number",
        "ratio",
        "Geometric mean return in the proxy's up months over the proxy's.",
    ),
    Field(
        "down_capture_3y",
        "Downside capture 3Y (proxy)",
        "Benchmark",
        "number",
        "ratio",
        "Geometric mean return in the proxy's down months over the proxy's.",
    ),
    Field("r2_3y", "R² 3Y (proxy)", "Benchmark", "number", "ratio", "Squared daily correlation."),
    Field(
        "bench_proxy_gap_3y",
        "Proxy gap to benchmark 3Y",
        "Benchmark",
        "number",
        "fraction",
        "The proxy fund's 3Y return less its benchmark's, both from one AMFI report.",
    ),
)
IDCW_FIELDS = (
    Field("idcw_last", "Last IDCW record date", "IDCW", "date", None, "As AMFI lists it."),
    Field("idcw_count_1y", "IDCW payouts 1Y", "IDCW", "number", "count", "Record dates in a year."),
    Field(
        "idcw_1y",
        "IDCW paid 1Y",
        "IDCW",
        "number",
        "INR",
        "₹ per unit with a record date in a year.",
    ),
    Field(
        "idcw_yield_1y",
        "IDCW yield 1Y",
        "IDCW",
        "number",
        "fraction",
        "IDCW paid in a year over the latest NAV.",
    ),
    Field(
        "ret_1y_with_idcw",
        "Return 1Y with IDCW",
        "IDCW",
        "number",
        "fraction",
        "NAV return with each listed payout reinvested at the NAV of its record date.",
    ),
    Field(
        "cagr_3y_with_idcw",
        "CAGR 3Y with IDCW",
        "IDCW",
        "number",
        "fraction",
        "As Return 1Y with IDCW, a year over 3 years.",
    ),
)
FACT_FIELD_IDS = tuple(f.id for f in (*FACT_FIELDS, *IDCW_FIELDS))


def benchmark_key(name: str) -> str:
    """A join key for benchmark names as filed: ``NIFTY500(TRI)`` and ``Nifty 500 TRI`` agree."""
    compact = re.sub(r"[^a-z0-9]", "", name.lower().replace("&", "and"))
    return _BENCH_NOISE.sub("", compact)


def _as_day(found: re.Match[str]) -> date | None:
    if found.group(1):
        day, month, year = found.group(1, 2, 3)
    elif found.group(4):
        day, month, year = found.group(5), found.group(4), found.group(6)
    else:
        # A two-digit year follows a month name: 20-Mar-26 is 2026.
        day, month, year = found.group(7), found.group(8), "20" + found.group(9)
    number = int(month) if month.isdigit() else _MONTHS.get(month[:3].lower())
    try:
        return date(int(year), number or 0, int(day))
    except ValueError:
        return None


def all_days(text: str) -> list[date]:
    """Every date in ``text``, in the forms SSDs use.

    24/05/2013, 24-May-2013, 05 Jul 2023, 9th November, 2011, May 24, 2013 and 20-Mar-26.
    """
    return [d for m in _DATE.finditer(text) if (d := _as_day(m)) is not None]


def parse_day(text: str) -> date | None:
    """The first date in ``text``, in any form :func:`all_days` reads."""
    found = all_days(text)
    return found[0] if found else None


def manager_starts(text: str) -> list[tuple[str, date]]:
    """Each manager and start date in an SSD ``Fund_Manager_From_Date`` element."""
    found = []
    for part in re.split(r"[;,]\s*(?=[A-Z])|\s{2,}|\n", text):
        day = parse_day(part)
        name = _MANAGER.match(part.strip())
        if day is not None and name is not None:
            found.append((name.group(1).strip(), day))
    return found


def first_amount(text: str) -> float | None:
    """The first rupee amount in an SSD text such as ``Rs. 5,000 and in multiples of Re. 1``."""
    found = _AMOUNT.search(text)
    return float(found.group().replace(",", "")) if found else None


@dataclass(frozen=True, slots=True)
class FundFacts:
    """The facts of one plan-option, resolved for its plan."""

    sd_id: int
    latest: Mapping[tuple[str, str], FactPoint]
    series: Mapping[tuple[str, str], Sequence[FactPoint]]
    plan: str
    single_plan: bool

    def get(self, name: str, scheme_level: bool = False) -> FactPoint | None:
        """The latest fact for the fund's plan; an ETF falls back to its one filed plan."""
        if scheme_level:
            return self.latest.get((name, ""))
        found = self.latest.get((name, self.plan))
        if found is None and self.single_plan:
            other = REGULAR if self.plan == DIRECT else DIRECT
            found = self.latest.get((name, other))
        return found

    def points(self, name: str, scheme_level: bool = False) -> Sequence[FactPoint]:
        """The fact's series for the fund's plan."""
        if scheme_level:
            return self.series.get((name, ""), ())
        found = self.series.get((name, self.plan), ())
        if not found and self.single_plan:
            found = self.series.get((name, REGULAR if self.plan == DIRECT else DIRECT), ())
        return found


def facts_of(view: FactView, pid: int, plan: str, fund_type: str) -> FundFacts | None:
    """The fund's scheme facts, or ``None`` when its ISINs join no AMFI scheme."""
    sd_id = view.scheme_of.get(pid)
    if sd_id is None:
        return None
    single = fund_type == ETF
    return FundFacts(sd_id, view.latest.get(sd_id, {}), view.series.get(sd_id, {}), plan, single)


def _fraction(point: FactPoint | None) -> Value:
    if point is None or point.num is None:
        return Missing("NA", NOT_FILED)
    return point.num / _PERCENT


def _day(point: FactPoint | None) -> Value:
    return Missing("NA", NOT_FILED) if point is None else date.fromordinal(point.day).isoformat()


def _year_ago(points: Sequence[FactPoint], day: int) -> FactPoint | None:
    target = day - 365
    before = [p for p in points if p.day <= target and p.num is not None]
    if not before or target - before[-1].day > YEAR_AGO_TOLERANCE_DAYS:
        return None
    return before[-1]


def _change(points: Sequence[FactPoint], now: FactPoint | None, *, ratio: bool) -> Value:
    if now is None or now.num is None:
        return Missing("NA", NOT_FILED)
    then = _year_ago(points, now.day)
    if then is None or then.num is None:
        return Missing("NA", NO_YEAR_AGO)
    if ratio:
        return now.num / then.num - 1 if then.num > 0 else Missing("NM", "zero_denominator")
    return (now.num - then.num) / _PERCENT


def _ter_change(points: Sequence[FactPoint], now: FactPoint | None) -> Value:
    # TER is stored as change points: the value a year ago is the last one before then.
    if now is None or now.num is None:
        return Missing("NA", NOT_FILED)
    before = [p for p in points if p.day <= now.day - 365 and p.num is not None]
    if not before:
        return Missing("NA", NO_YEAR_AGO)
    return (now.num - (before[-1].num or 0.0)) / _PERCENT


def fact_fields(facts: FundFacts | None, option: str, as_of: int) -> dict[str, Value]:
    """The as-filed fields of one plan-option (every field in ``FACT_FIELDS`` but proxies)."""
    if facts is None:
        absent = Missing("NA", NO_SCHEME)
        return dict.fromkeys(FACT_FIELD_IDS, absent)
    ter, aum = facts.get("ter"), facts.get("aum_cr", scheme_level=True)
    risk = facts.get("riskometer", scheme_level=True)
    risk = risk or facts.get("ssd:Riskometer_as_on_Date", scheme_level=True)
    bench = facts.get("benchmark", scheme_level=True) or facts.get(
        "ssd:Benchmark_Tier_1", scheme_level=True
    )
    level = _LEVEL.get((risk.txt or "").lower()) if risk else None
    values: dict[str, Value] = {
        "ter": _fraction(ter),
        "ter_base": _fraction(facts.get("ter_base")),
        "ter_as_of": _day(ter),
        "ter_change_1y": _ter_change(facts.points("ter"), ter),
        "aum_cr": aum.num if aum and aum.num is not None else Missing("NA", NOT_FILED),
        "aum_as_of": _day(aum),
        "aum_change_1y": _change(facts.points("aum_cr", scheme_level=True), aum, ratio=True),
        "riskometer": risk.txt if risk and risk.txt else Missing("NA", NOT_FILED),
        "riskometer_level": level if level is not None else Missing("NA", NOT_FILED),
        "benchmark": bench.txt if bench and bench.txt else Missing("NA", NOT_FILED),
    }
    values |= _ssd_fields(facts, as_of)
    perf = facts.get("bench_ret_1y", scheme_level=True)
    values["perf_as_of"] = _day(perf)
    for h in HORIZONS:
        benchmark = _fraction(facts.get(f"bench_ret_{h}", scheme_level=True))
        values[f"bench_ret_{h}"] = benchmark
        own = _fraction(facts.get(f"ret_{h}"))
        if option != GROWTH:
            values[f"excess_{h}"] = Missing("NM", GROWTH_ONLY)
        elif isinstance(own, float) and isinstance(benchmark, float):
            values[f"excess_{h}"] = own - benchmark
        else:
            values[f"excess_{h}"] = Missing("NA", NOT_FILED)
    for h in IR_HORIZONS:
        found = facts.get(f"ir_{h}")
        if option != GROWTH:
            values[f"ir_{h}"] = Missing("NM", GROWTH_ONLY)
        else:
            values[f"ir_{h}"] = (
                found.num if found and found.num is not None else Missing("NA", NOT_FILED)
            )
    values["tracking_error"] = _fraction(facts.get("tracking_error"))
    return values


def _ssd_fields(facts: FundFacts, as_of: int) -> dict[str, Value]:
    absent = Missing("NA", NOT_FILED)
    starts_text = facts.get("ssd:Fund_Manager_From_Date", scheme_level=True)
    allotted = facts.get("ssd:Allotment_Date", scheme_level=True)
    allotment = parse_day(allotted.txt or "") if allotted else None
    names_text = facts.get("ssd:Fund_Manager_Name", scheme_level=True)
    starts_days = all_days(starts_text.txt or "") if starts_text else []
    count = (
        len([n for n in re.split(r",|\band\b|&|;", names_text.txt or "") if n.strip()])
        if names_text
        else 0
    )
    lumpsum = facts.get("ssd:Minimum_Application_Amount", scheme_level=True)
    sip_text = facts.get("ssd:SIP_SWP__STP_Details_Minimum_amount", scheme_level=True)
    sip = _SIP.search(sip_text.txt or "") if sip_text else None
    if not starts_days and starts_text and "inception" in (starts_text.txt or "").lower():
        starts_days = [allotment] if allotment else []
    earliest = min(starts_days) if starts_days else None
    tenure = (as_of - earliest.toordinal()) / YEAR_DAYS if earliest else None
    lump = first_amount(lumpsum.txt or "") if lumpsum else None
    return {
        "manager_count": count or absent,
        "manager_tenure_y": tenure if tenure is not None and tenure >= 0 else absent,
        "inception": allotment.isoformat() if allotment else absent,
        "min_lumpsum": lump if lump is not None else absent,
        "min_sip": float(sip.group(1).replace(",", "")) if sip else absent,
    }


def cost_ranks(
    groups: Mapping[tuple[str, str, str], Sequence[int]], values: Mapping[int, dict[str, Value]]
) -> None:
    """Set ``ter_cat_pct`` and ``ter_cat_median`` over each peer group's active funds."""
    for members in groups.values():
        priced: list[tuple[int, float]] = []
        for pid in members:
            ter = values[pid]["ter"] if pid in values else None
            if isinstance(ter, float):
                priced.append((pid, ter))
        if len(priced) < PEERS_MIN:
            for pid in members:
                if pid in values:
                    values[pid].setdefault("ter_cat_pct", Missing("NA", TOO_FEW_PEERS))
                    values[pid].setdefault("ter_cat_median", Missing("NA", TOO_FEW_PEERS))
            continue
        ordered = sorted(t for _, t in priced)
        n = len(ordered)
        median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
        for (pid, _), rank in zip(priced, rank_all([t for _, t in priced], False), strict=True):
            values[pid]["ter_cat_pct"] = rank.pct
            values[pid]["ter_cat_median"] = median
        for pid in members:
            if pid in values:
                values[pid].setdefault("ter_cat_pct", Missing("NA", NOT_FILED))
                values[pid].setdefault("ter_cat_median", median)


@dataclass(frozen=True, slots=True)
class Proxy:
    """The index fund whose NAV stands in for one benchmark."""

    key: str
    benchmark: str
    pid: int
    code: str
    name: str
    tracking_error: float | None
    gap_3y: Value


def choose_proxies(
    candidates: Sequence[tuple[int, str, str, str, float | None, Value]],
) -> dict[str, Proxy]:
    """Per benchmark key, the candidate with the lowest filed tracking error.

    A candidate is (pid, AMFI code, name, benchmark as filed, tracking error %, proxy
    gap): an active direct growth index fund (or an ETF) with a 3Y daily window.
    Ties go to the lower plan-option id, so the choice is deterministic.
    """
    chosen: dict[str, Proxy] = {}
    for pid, code, name, bench, te, gap in sorted(
        candidates, key=lambda c: (math.inf if c[4] is None else c[4], c[0])
    ):
        key = benchmark_key(bench)
        if key and key not in chosen:
            chosen[key] = Proxy(key, bench, pid, code, name, te, gap)
    return chosen


def _common(fund: DailyNavs, proxy: DailyNavs) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    at = dict(zip(proxy.days, proxy.levels, strict=True))
    days = [d for d in fund.days if d in at]
    mine = dict(zip(fund.days, fund.levels, strict=True))
    return (
        np.asarray(days),
        np.asarray([mine[d] for d in days]),
        np.asarray([at[d] for d in days]),
    )


def _month_returns(days: np.ndarray, levels: np.ndarray) -> np.ndarray:
    months = np.asarray(
        [date.fromordinal(int(d)).year * 12 + date.fromordinal(int(d)).month for d in days]
    )
    last = np.flatnonzero(np.diff(months, append=months[-1] + 1))
    ends: np.ndarray = levels[last]
    return np.asarray(ends[1:] / ends[:-1] - 1)


def _capture(fund: np.ndarray, proxy: np.ndarray, up: bool) -> Value:
    side = proxy > 0 if up else proxy < 0
    if side.sum() < MIN_SIDE_MONTHS:
        return Missing("NA", HISTORY_TOO_SHORT)
    mine = np.prod(1 + fund[side]) ** (1 / side.sum()) - 1
    theirs = np.prod(1 + proxy[side]) ** (1 / side.sum()) - 1
    return float(mine / theirs) if theirs != 0 else Missing("NM", "zero_denominator")


def finite(values: dict[str, Value]) -> dict[str, Value]:
    """Each value, with any NaN or infinity (a zero-variance series) as not meaningful."""
    return {
        k: Missing("NM", "zero_denominator") if isinstance(v, float) and not math.isfinite(v) else v
        for k, v in values.items()
    }


def proxy_fields(
    fund: DailyNavs | None, proxy: DailyNavs | None, risk_free: RiskFree
) -> dict[str, Value]:
    """Beta, alpha, tracking error, information ratio, capture and R² over common 3Y dates."""
    names = PROXY_FIELDS
    if proxy is None:
        return dict.fromkeys(names, Missing("NA", NO_PROXY))
    if fund is None:
        return dict.fromkeys(names, Missing("NA", HISTORY_TOO_SHORT))
    days, mine, theirs = _common(fund, proxy)
    if len(days) <= MIN_COMMON_DAYS:
        return dict.fromkeys(names, Missing("NA", HISTORY_TOO_SHORT))
    steps = np.diff(days) <= MAX_GAP_DAYS
    rf_, rp = (mine[1:] / mine[:-1] - 1)[steps], (theirs[1:] / theirs[:-1] - 1)[steps]
    if len(rf_) < MIN_COMMON_DAYS:
        return dict.fromkeys(names, Missing("NA", HISTORY_TOO_SHORT))
    variance = float(np.var(rp, ddof=1))
    beta = float(np.cov(rf_, rp, ddof=1)[0, 1] / variance) if variance > 0 else math.nan
    years = (int(days[-1]) - int(days[0])) / YEAR_DAYS
    cagr = (mine[-1] / mine[0]) ** (1 / years) - 1
    proxy_cagr = (theirs[-1] / theirs[0]) ** (1 / years) - 1
    te = float(np.std(rf_ - rp, ddof=1)) * ANNUALISE_VOL
    rf = risk_free.annualised(int(days[0]), int(days[-1]))
    alpha: Value = (
        float(cagr - rf - beta * (proxy_cagr - rf))
        if isinstance(rf, float) and math.isfinite(beta)
        else Missing("NA", NO_RISK_FREE)
    )
    monthly_f, monthly_p = _month_returns(days, mine), _month_returns(days, theirs)
    correlation = float(np.corrcoef(rf_, rp)[0, 1])
    return {
        "beta_3y": beta if math.isfinite(beta) else Missing("NM", "zero_denominator"),
        "alpha_3y": alpha,
        "te_3y": te,
        "ir_3y_proxy": float((cagr - proxy_cagr) / te)
        if te > 0
        else Missing("NM", "zero_denominator"),
        "up_capture_3y": _capture(monthly_f, monthly_p, up=True),
        "down_capture_3y": _capture(monthly_f, monthly_p, up=False),
        "r2_3y": correlation**2,
    }


# SEBI's April 2026 TER rules changed what the total TER includes, so values on either
# side of this date are not like for like (doc 17).
TER_DEFINITION_CHANGE = date(2026, 4, 1)
SSD_PROFILE = {
    "objective": "ssd:Description_Objective_of_the_scheme",
    "fund_type": "ssd:Fund_Type",
    "asset_allocation": "ssd:Stated_Asset_Allocation",
    "exit_load": "ssd:Exit_Load_if_applicable",
    "expense_stated_max": "ssd:Annual_Expense_Stated_maximum",
    "min_lumpsum": "ssd:Minimum_Application_Amount",
    "min_additional": "ssd:Minimum_Additional_Amount",
    "sip_minimum": "ssd:SIP_SWP__STP_Details_Minimum_amount",
    "plans": "ssd:Option_Names_Regular__Direct",
    "allotment_date": "ssd:Allotment_Date",
    "benchmark_tier_1": "ssd:Benchmark_Tier_1",
    "benchmark_tier_2": "ssd:Benchmark_Tier_2",
    "riskometer_at_launch": "ssd:Riskometer_At_the_time_of_Launch",
    "potential_risk_class": "ssd:Potential_Risk_Class_as_on_date",
    "managers": "ssd:Fund_Manager_Name",
    "manager_roles": "ssd:Fund_Manager_Type_PrimaryComanageDescription",
    "custodian": "ssd:Custodian",
    "registrar": "ssd:Registrar",
    "auditor": "ssd:Auditor",
    "sebi_code": "ssd:SEBI_Codes",
    "listing": "ssd:Listing_Details",
}


def change_points(points: Sequence[tuple[date, object]]) -> list[tuple[date, object]]:
    """The points where the value differs from the one before (TER rows repeat monthly)."""
    found: list[tuple[date, object]] = []
    for day, value in points:
        if not found or found[-1][1] != value:
            found.append((day, value))
    return found


def _reinvested(daily: DailyNavs, payouts: Sequence[tuple[int, float]], start: int) -> float:
    """Growth from a trailing-return anchor ``start`` to the last NAV, payouts reinvested."""
    days, levels = daily.days, daily.levels
    first = bisect_left(days, start)
    growth = levels[-1] / levels[first]
    for day, rate in payouts:
        if days[first] < day <= days[-1]:
            growth *= 1 + rate / levels[bisect_left(days, day)]
    return growth


def idcw_fields(
    option: str,
    payouts: Sequence[tuple[int, float]],
    daily: DailyNavs | None,
    as_of: int,
    anchors: Mapping[str, str],
) -> dict[str, Value]:
    """IDCW payouts in the last year and returns with them reinvested (M13: sourced only).

    The returns use the windows of ``ret_1y`` and ``cagr_3y``: their start anchors, the
    last NAV, and for 3Y the same annualisation.
    """
    ids = [f.id for f in IDCW_FIELDS]
    if option != "idcw":
        return dict.fromkeys(ids, Missing("NM", NOT_IDCW))
    if not payouts:
        return dict.fromkeys(ids, Missing("NA", NOT_FILED))
    year = [(d, r) for d, r in payouts if as_of - 365 < d <= as_of]
    paid = math.fsum(r for _, r in year)
    nav = daily.levels[-1] if daily is not None and daily.levels else None
    short = Missing("NA", HISTORY_TOO_SHORT)
    one = three = None
    if daily is not None and daily.days:
        if "ret_1y" in anchors:
            one = _reinvested(daily, payouts, date.fromisoformat(anchors["ret_1y"]).toordinal())
        if "cagr_3y" in anchors:
            start = date.fromisoformat(anchors["cagr_3y"]).toordinal()
            three = _reinvested(daily, payouts, start) ** (YEAR_DAYS / (daily.days[-1] - start))
    return {
        "idcw_last": date.fromordinal(payouts[-1][0]).isoformat(),
        "idcw_count_1y": len(year),
        "idcw_1y": paid,
        "idcw_yield_1y": paid / nav if nav else short,
        "ret_1y_with_idcw": one - 1 if one is not None else short,
        "cagr_3y_with_idcw": three - 1 if three is not None else short,
    }
