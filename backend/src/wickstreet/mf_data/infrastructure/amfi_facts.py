"""AMFI scheme facts: TER, fund performance, scheme summaries, tracking error (doc 21 E1, E3).

AMFI's research pages read these endpoints, as observed on 2026-10-24:

- Schemes of one fund house: ``/api/populate-scheme?MF_ID=N`` (JSON ``scheme_id``,
  ``scheme_name``). Fund-house ids ran from 1 to 91 on 2026-10-24; an unused id gives ``[]``.
- Scheme summary document (SEBI's SSD): ``portal.amfiindia.com/spages/SSD_<id>.xml``.
  One element per item as the AMC filed it: benchmark, riskometer, managers and their
  start dates, exit load, minimums, ISINs, SEBI code.
- TER for one month, every scheme and day: ``/api/populate-te-rdata-revised?...&excel=true``
  (XLSX; regular and direct base expense ratio and total TER, % a year).
- Fund performance for one date and sub-category: ``POST /gateway/pollingsebi/api/amfi/
  fundperformance``. Scheme and Tier 1 benchmark returns (% a year, as AMFI computes
  them from TRI), information ratio, riskometers and daily AUM (₹ crore).
- Index-fund and ETF tracking error for one date: ``/api/tracking-error-data``.
- The half-yearly average market-cap list (SEBI's large, mid and small cap classes),
  linked from ``/otherdata/categorisation-of-stocks``.

The adapter stores what AMFI filed. It joins rows to AMFI scheme ids by SEBI scheme
code or by scheme name; a row it cannot join is counted, never guessed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from wickstreet.mf_data.domain.facts import compact, join_by_navs
from wickstreet.mf_data.domain.model import (
    AMFI,
    DIRECT,
    REGULAR,
    SCHEME,
    CapClass,
    Fact,
    RawFile,
    SchemeFacts,
    SchemeRef,
)
from wickstreet.mf_data.domain.ports import SourceError, SourceLayoutError
from wickstreet.mf_data.infrastructure.amfi import amfi_date
from wickstreet.mf_data.infrastructure.client import COMPATIBLE_USER_AGENT, PacedClient
from wickstreet.mf_data.infrastructure.portfolios import parse_market_caps
from wickstreet.mf_data.infrastructure.xlsx import first_sheet

SITE = "https://www.amfiindia.com"
SCHEMES_URL = SITE + "/api/populate-scheme"
TER_URL = SITE + "/api/populate-te-rdata-revised"
TRACKING_ERROR_URL = SITE + "/api/tracking-error-data"
GATEWAY = SITE + "/gateway/pollingsebi/api/amfi/"
SSD_URL = "https://portal.amfiindia.com/spages/SSD_{sd_id}.xml"
# Half-yearly average market cap per company and its SEBI class (large, mid, small).
CATEGORISATION_PAGE = SITE + "/otherdata/categorisation-of-stocks"
FUND_HOUSE_IDS = range(1, 121)
OPEN_ENDED = 1

_EXCEL_EPOCH = date(1899, 12, 30)
_ISIN = re.compile(r"INF[A-Z0-9]{9}")
_RETURN = re.compile(
    r"^return(7Days|15Days|1Month|3Month|6Month|1Year|3Year|5Year|10Year|SinceLaunch)"
    r"(Regular|Direct|Benchmark|BenchmarkRegular|BenchmarkDirect)$"
)
_IR = re.compile(r"^ir(1|3|5|10)Yr(Regular|Direct)$")
_HORIZON = {
    "7Days": "7d",
    "15Days": "15d",
    "1Month": "1m",
    "3Month": "3m",
    "6Month": "6m",
    "1Year": "1y",
    "3Year": "3y",
    "5Year": "5y",
    "10Year": "10y",
    "SinceLaunch": "si",
}
_PLAN = {"Regular": REGULAR, "Direct": DIRECT, "BenchmarkRegular": REGULAR}
_PLAN |= {"BenchmarkDirect": DIRECT, "Benchmark": SCHEME}
# TER workbook columns: (fact, plan, column) as filed on 2026-10-24.
_TER_COLUMNS = (
    ("ter_base", REGULAR, "F"),
    ("ter", REGULAR, "J"),
    ("ter_base", DIRECT, "K"),
    ("ter", DIRECT, "O"),
)
_NOT_FILED = frozenset({"", "not applicable", "na", "n.a.", "nil", "-"})


def _number(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _json(raw: RawFile) -> object:
    try:
        return json.loads(raw.content)
    except ValueError as exc:
        raise SourceLayoutError(f"{raw.url} is not JSON: {exc}") from exc


def parse_scheme_list(raw: RawFile) -> list[SchemeRef]:
    """Every scheme of every fund house, from the combined ``populate-scheme`` file."""
    found = _json(raw)
    if not isinstance(found, dict):
        raise SourceLayoutError("The scheme list is not keyed by fund-house id.")
    schemes = [
        SchemeRef(int(item["scheme_id"]), int(mf_id), str(item["scheme_name"]).strip())
        for mf_id, items in found.items()
        for item in items
    ]
    if not schemes:
        raise SourceLayoutError("The scheme list is empty.")
    return schemes


def parse_ssd(raw: RawFile, sd_id: int, as_of: date) -> SchemeFacts:
    """Each filed SSD element as an ``ssd:<element>`` text fact, and the ISINs listed."""
    try:
        root = ElementTree.fromstring(raw.content.decode("utf-8-sig"))
    except (ElementTree.ParseError, UnicodeDecodeError) as exc:
        raise SourceLayoutError(f"SSD {sd_id} is not XML: {exc}") from exc
    summary = root.find("SchemeSummary")
    if summary is None:
        raise SourceLayoutError(f"SSD {sd_id} has no SchemeSummary.")
    filed: dict[str, list[str]] = {}
    for element in summary:
        text = " ".join((element.text or "").split())
        if text.lower().rstrip(".") not in _NOT_FILED:
            filed.setdefault(element.tag, []).append(text)
    # An element filed twice keeps both texts, in order.
    facts = [
        Fact(sd_id, f"ssd:{tag}", SCHEME, as_of, txt=" | ".join(texts))
        for tag, texts in filed.items()
    ]
    isins = dict.fromkeys(_ISIN.findall(" ".join(filed.get("ISINs", []))), sd_id)
    return SchemeFacts(facts, isins)


def parse_ter(raw: RawFile, codes: Mapping[str, int], names: Mapping[str, int]) -> SchemeFacts:
    """A month of daily TER as change points: each value from the first day it holds.

    A row joins by its SEBI scheme code, else by its scheme name.
    """
    rows = first_sheet(raw.content)
    if not rows or rows[0].get("A") != "NSDL Scheme Code" or rows[0].get("O", "").find("TER") < 0:
        raise SourceLayoutError("Not AMFI's TER workbook (header changed).")
    daily: dict[tuple[int, str, str], dict[date, Decimal]] = {}
    unmatched: set[str] = set()
    for row in rows[1:]:
        code, name, serial = row.get("A", ""), row.get("B", ""), row.get("E", "")
        sd_id = codes.get(compact(code)) or names.get(compact(name))
        if sd_id is None:
            unmatched.add(code or name)
            continue
        try:
            day = _EXCEL_EPOCH + timedelta(days=int(float(serial)))
        except ValueError:
            raise SourceLayoutError(f"TER date {serial!r} for {name} is not a date.") from None
        for fact, plan, column in _TER_COLUMNS:
            value = _number(row.get(column))
            if value is not None:
                daily.setdefault((sd_id, fact, plan), {})[day] = value
    facts = []
    for (sd_id, fact, plan), values in daily.items():
        previous = None
        for day in sorted(values):
            if values[day] != previous:
                facts.append(Fact(sd_id, fact, plan, day, num=values[day]))
                previous = values[day]
    return SchemeFacts(facts, unmatched=len(unmatched))


def _performance_facts(row: Mapping[str, object], sd_id: int, day: date) -> list[Fact]:
    facts = []
    for key, value in row.items():
        number = _number(value)
        if (matched := _RETURN.match(key)) and number is not None:
            horizon, who = matched.groups()
            prefix = "bench_ret_" if who.startswith("Benchmark") else "ret_"
            facts.append(Fact(sd_id, prefix + _HORIZON[horizon], _PLAN[who], day, num=number))
        elif (matched := _IR.match(key)) and number is not None:
            years, who = matched.groups()
            facts.append(Fact(sd_id, f"ir_{years}y", _PLAN[who], day, num=number))
    for name, key in (
        ("benchmark", "benchmark"),
        ("riskometer", "riskometerScheme"),
        ("riskometer_benchmark", "riskometerBenchmark"),
    ):
        text = " ".join(str(row.get(key) or "").split())
        if text.lower() not in _NOT_FILED:
            facts.append(Fact(sd_id, name, SCHEME, day, txt=text))
    aum = _number(row.get("dailyAUM"))
    if aum is not None:
        facts.append(Fact(sd_id, "aum_cr", SCHEME, day, num=aum))
    return facts


def _unique(facts: list[Fact]) -> list[Fact]:
    """One fact per key; a scheme listed in two sub-categories keeps its first listing."""
    seen: dict[tuple[int, str, str, date], Fact] = {}
    for fact in facts:
        seen.setdefault((fact.sd_id, fact.name, fact.plan, fact.as_of), fact)
    return list(seen.values())


def parse_performance(
    raw: RawFile,
    day: date,
    names: Mapping[str, int],
    navs: Mapping[Decimal, set[int]] | None = None,
) -> SchemeFacts:
    """Fund performance rows for ``day``, joined by scheme name, else by their NAV pair."""
    found = _json(raw)
    if not isinstance(found, dict) or not isinstance(found.get("queries"), list):
        raise SourceLayoutError("Not a combined fund-performance file.")
    facts: list[Fact] = []
    unmatched: set[str] = set()
    for query in found["queries"]:
        for row in query.get("data") or []:
            name = str(row.get("schemeName") or "")
            sd_id = names.get(compact(name))
            if sd_id is None and navs:
                filed = [_number(row.get("navRegular")), _number(row.get("navDirect"))]
                sd_id = join_by_navs(navs, filed)
            if sd_id is None:
                unmatched.add(name)
                continue
            facts.extend(_performance_facts(row, sd_id, day))
    return SchemeFacts(_unique(facts), unmatched=len(unmatched))


def parse_tracking_error(raw: RawFile, day: date, names: Mapping[str, int]) -> SchemeFacts:
    """Annualised tracking error (%) of index funds and ETFs on ``day``, as filed."""
    found = _json(raw)
    if not isinstance(found, dict) or not isinstance(found.get("data"), list):
        raise SourceLayoutError("Not a tracking-error file.")
    facts: list[Fact] = []
    unmatched: set[str] = set()
    for row in found["data"]:
        name = str(row.get("Scheme_Name") or "")
        sd_id = names.get(compact(name))
        if sd_id is None:
            unmatched.add(name)
            continue
        for plan, key in ((REGULAR, "RegularPercent"), (DIRECT, "DirectPercent")):
            value = _number(row.get(key))
            if value is not None:
                facts.append(Fact(sd_id, "tracking_error", plan, day, num=value))
        benchmark = " ".join(str(row.get("Benchmark") or "").split())
        if benchmark:
            facts.append(Fact(sd_id, "tracking_benchmark", SCHEME, day, txt=benchmark))
    return SchemeFacts(_unique(facts), unmatched=len(unmatched))


def _squeeze(url: str) -> str:
    """A file URL without spaces, underscores or dots: ``30_Jun2024`` reads ``30Jun2024``."""
    return re.sub(r"[\s_.]", "", url.replace("%20", ""))


def _now() -> datetime:
    return datetime.now(UTC)


class AmfiFactsAdapter:
    """Fetches AMFI's scheme-fact pages; parsing is in the module's pure functions."""

    name = AMFI
    adapter_version = "amfi-facts-2026-10-24.1"

    def __init__(
        self, *, min_interval_seconds: float, timeout_seconds: float, max_attempts: int
    ) -> None:
        """Create the adapter with its own paced client (TER workbooks take about 50 s)."""
        self._http = PacedClient(
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=max(timeout_seconds, 180.0),
            max_attempts=max_attempts,
            user_agent=COMPATIBLE_USER_AGENT,
        )

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()

    parse_scheme_list = staticmethod(parse_scheme_list)
    parse_ssd = staticmethod(parse_ssd)
    parse_ter = staticmethod(parse_ter)
    parse_performance = staticmethod(parse_performance)
    parse_tracking_error = staticmethod(parse_tracking_error)

    async def _json_get(self, url: str, params: dict[str, str]) -> object:
        response = await self._http.get(url, params)
        if response.status_code != 200:
            raise SourceError(f"{url} answered HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceLayoutError(f"{url} did not answer JSON.") from exc

    async def scheme_list(self) -> RawFile:
        """Every fund house's scheme list, combined into one JSON file keyed by fund-house id."""
        combined = {}
        for mf_id in FUND_HOUSE_IDS:
            found = await self._json_get(SCHEMES_URL, {"MF_ID": str(mf_id)})
            if isinstance(found, list) and found:
                combined[str(mf_id)] = found
        content = json.dumps(combined, sort_keys=True).encode()
        return RawFile(
            f"{SCHEMES_URL}?MF_ID={FUND_HOUSE_IDS[0]}..{FUND_HOUSE_IDS[-1]}", _now(), content
        )

    async def ssd(self, sd_id: int) -> RawFile | None:
        """One scheme summary document; ``None`` when AMFI has none for the scheme."""
        url = SSD_URL.format(sd_id=sd_id)
        response = await self._http.get(url)
        if response.status_code != 200 or b"SchemeSummary" not in response.content:
            return None
        return RawFile(url, _now(), response.content)

    async def ter_month(self, month: date) -> RawFile:
        """The TER workbook of ``month`` (any day in it)."""
        params = {
            "MF_ID": "All",
            "Month": f"{month.month:02d}-{month.year}",
            "strCat": "-1",
            "strType": "-1",
            "excel": "true",
        }
        response = await self._http.get(TER_URL, params)
        if response.status_code != 200 or response.content[:2] != b"PK":
            raise SourceError(f"TER for {params['Month']} answered HTTP {response.status_code}.")
        return RawFile(str(response.request.url), _now(), response.content)

    async def performance(self, day: date, *, closed_ended: bool) -> RawFile:
        """Every sub-category's fund performance on ``day``, combined into one JSON file."""
        filters = await self._http.post(GATEWAY + "fundperformancefilters", {})
        lists = filters.json().get("data") or {}
        maturities = [m["id"] for m in lists.get("maturityTypeList", [])]
        if not closed_ended:
            maturities = [m for m in maturities if m == OPEN_ENDED]
        queries = []
        for kind in lists.get("investmentTypeList", []):
            found = await self._http.post(GATEWAY + "getsubcategory", {"category": kind["id"]})
            for sub in found.json().get("data") or []:
                for maturity in maturities:
                    body = {
                        "maturityType": maturity,
                        "category": kind["id"],
                        "subCategory": sub["id"],
                        "mfid": 0,
                        "reportDate": amfi_date(day),
                    }
                    answer = (await self._http.post(GATEWAY + "fundperformance", body)).json()
                    if answer.get("validationStatus") != "SUCCESS":
                        raise SourceError(f"Fund performance refused {body}: {answer}")
                    queries.append({"body": body, "data": answer.get("data") or []})
        content = json.dumps({"day": day.isoformat(), "queries": queries}).encode()
        return RawFile(GATEWAY + "fundperformance", _now(), content)

    async def market_caps(self, period_end: date) -> RawFile | None:
        """AMFI's market-cap list for the half-year ending ``period_end`` (30 Jun or 31 Dec)."""
        page = await self._http.get(CATEGORISATION_PAGE)
        if page.status_code != 200:
            raise SourceError(f"{CATEGORISATION_PAGE} answered HTTP {page.status_code}.")
        stamp = f"{period_end.day}{amfi_date(period_end)[3:6]}{period_end.year}"
        links = re.findall(r'excelUrl\\?":\\?"([^"\\]+)', page.text)
        link = next((u.strip() for u in links if stamp in _squeeze(u)), None)
        if link is None:
            return None
        response = await self._http.get(link)
        if response.status_code != 200 or response.content[:2] != b"PK":
            raise SourceError(f"{link} answered HTTP {response.status_code}.")
        return RawFile(link, _now(), response.content)

    @staticmethod
    def parse_market_caps(raw: RawFile) -> list[CapClass]:
        """The companies in AMFI's list, with their class."""
        return parse_market_caps(raw.content)

    async def tracking_error(self, day: date) -> RawFile:
        """Tracking error of every index fund and ETF on ``day``."""
        params = {"MF_ID": "all", "strdt": amfi_date(day).lower()}
        response = await self._http.get(TRACKING_ERROR_URL, params)
        if response.status_code != 200:
            raise SourceError(f"Tracking error answered HTTP {response.status_code}.")
        return RawFile(str(response.request.url), _now(), response.content)
