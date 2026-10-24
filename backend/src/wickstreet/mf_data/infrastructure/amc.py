"""AMC portfolio adapters: each AMC's own monthly portfolio files (doc 21 E4).

An AMC lists its files on one page. The adapter reads the page, picks the month-end
file by the month and year in its link, and fetches it. Pages observed on 2026-10-24:

- PPFAS: ``amc.ppfas.com/downloads/portfolio-disclosure/``, one workbook a month with a
  sheet per scheme (``PPFAS_Monthly_Portfolio_Report_September_30_2026.xls``, an XLSX;
  before March 2026 a binary XLS), beside one file per scheme.
- DSP: ``dspim.com/mandatory-disclosures/portfolio-disclosures``, one zip a
  month of workbooks (``monthend-portfolios_30_june_2026.zip``).
- Nippon India: ``mf.nipponindiaim.com/investor-service/downloads/`` then
  ``factsheet-portfolio-and-other-disclosures``, one workbook a month with a sheet
  per scheme, mostly named with a two-digit year since 2024
  (``NIMF-MONTHLY-PORTFOLIO-30-Sep-26.xls``, an XLSX), beside fortnightly files.
- SBI: the portfolios page builds its list in the browser from one JSON ``POST`` to
  ``sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets``, which answers HTML rows of
  links to one workbook a month since 2023
  (``all-schemes-monthly-portfolio---as-on-30th-september-2026.xlsx``).
- ICICI Prudential: the downloads page lists its files from one JSON ``POST`` to
  ``apimf.icicipruamc.com/nms/v1/downloads/files`` (header ``env: api``), which
  answers JSON with each file's path. The page opens a path under
  ``www.icicipruamc.com/blob``: one zip a month of a workbook per scheme
  (``Monthly-Portfolio-Disclosure-September-2026.zip``).
- PGIM India: the disclosures page lists its monthly portfolios from one JSON
  ``POST`` to ``pgimindia.com/api/v1/brochure/published/disclosure`` (section
  "Monthly Portfolio"), each with its ``pdfPath``: one workbook per scheme a month
  (``PGIM INDIA SMALL CAP FUND Sep 2026.xlsx``).
- Samco: ``samcomf.com/StatutoryDisclosure`` links one workbook per scheme a month
  (``IN_MF_MONTHLY_PORTFOLIO_September_2026_Samco_Flexicap_Fund_1791526364.xlsx``),
  each on two hosts; the month is every file that names it.
- Tata: ``tatamutualfund.com/schemes-related/portfolio``, one workbook a month with a
  sheet per scheme (``Monthly Portfolio as on 30th September 2026.xlsx``). The links
  name ``betacms.tatamutualfund.com``, which redirects to ``www``.
- Groww: ``growwmf.in/statutory-disclosure/portfolio`` holds every file's
  ``publicUrl`` in its page script: one workbook a month
  (``Monthly Portfolio - September 30, 2026.xlsx``), beside fortnightly files.
- Motilal Oswal: the downloads page lists every file from one JSON ``GET`` to
  ``search-documents.json`` (category "month end portfolio"), each with its ``path``:
  one workbook a month, named by month ("Scheme Portfolio Details September 2026") or
  by date ("Monthly Portfolio 31-07-2026-Final"), beside fortnightly files.
- Trust, Mirae Asset, Sundaram, Quantum, Invesco: see :class:`TitledPortfolioAdapter`
  and its subclasses.
- WhiteOak: see :class:`WhiteOakPortfolioAdapter`.
- LIC: see :class:`LicPortfolioAdapter`.
- quant: see :class:`QuantPortfolioAdapter`.
- Baroda BNP Paribas: see :class:`BarodaPortfolioAdapter`.
- UTI: see :class:`UtiPortfolioAdapter`.

The AMCs in :data:`MANUAL` are never fetched: see :class:`ManualPortfolioSource`.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urljoin, urlsplit

from wickstreet.mf_data.domain.model import Portfolios, RawFile
from wickstreet.mf_data.domain.ports import SourceError
from wickstreet.mf_data.infrastructure.client import COMPATIBLE_USER_AGENT, PacedClient
from wickstreet.mf_data.infrastructure.portfolios import parse_portfolios, sheet_codes

# A link in a page (href) or a JSON value in a listing or a page script ("url",
# "path", "publicUrl"); Tata's page script holds its JSON escaped.
_LINK = re.compile(r"""(?:href=|"\w+"\s*:\s*)["']([^"']+\.(?:xlsx?|zip))(?:\?[^"']*)?["']""", re.I)
_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)  # fmt: skip


class AmcPortfolioAdapter:
    """One AMC's monthly portfolio files, found on its disclosure page."""

    adapter_version = "amc-portfolios-2026-10-24.8"
    layout_verified = True

    def __init__(
        self,
        name: str,
        page: str,
        *,
        require: tuple[str, ...],
        exclude: tuple[str, ...] = (),
        prefer: tuple[str, ...] = (),
        listing: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        files: str | None = None,
        each: bool = False,
        stable_codes: bool = True,
        min_interval_seconds: float,
        timeout_seconds: float,
        max_attempts: int,
    ) -> None:
        """Read ``page``; a link must hold every ``require`` word and no ``exclude`` word.

        With ``listing``, the page is an endpoint that lists the files when it is sent
        that JSON body, with ``headers``. With ``files``, a listed path is read under
        that prefix rather than against the page. With ``each``, the AMC files one
        workbook per scheme, and a month is every file that names it. Without
        ``stable_codes``, the AMC reuses sheet codes across schemes, so none is learnt.
        """
        self.name = name
        self._page = page
        self._require = require
        self._exclude = exclude
        self._prefer = prefer
        self._listing = listing
        self._headers = headers
        self._files = files
        self._each = each
        self._stable_codes = stable_codes
        self._links: list[str] | None = None
        self._http = PacedClient(
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            user_agent=COMPATIBLE_USER_AGENT,
        )

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()

    async def _listed(self) -> list[str]:
        if self._links is None:
            if self._listing is None:
                response = await self._http.get(self._page)
            else:
                response = await self._http.post(self._page, self._listing, self._headers)
            if response.status_code != 200:
                raise SourceError(f"{self._page} answered HTTP {response.status_code}.")
            found = (m.group(1) for m in _LINK.finditer(response.text.replace('\\"', '"')))
            links = {
                urljoin(self._page, link) if self._files is None else self._files + link
                for link in found
            }
            self._links = sorted(links)
        return self._links

    def pick(self, links: list[str], month_end: date) -> str | None:
        """The link for ``month_end``: its month (full or short), year and words.

        The year is four digits anywhere, or two digits right after the month
        ("30-Sep-26"), so a day such as the 26 in "26-Sep-2025" is never a year. A
        numeric month-end date ("31-07-2026", "31.03.2026", "30092026") names both. A
        link whose file name starts with a ``prefer`` prefix wins, such as an AMC's
        all-scheme workbook over its per-scheme files.
        """
        tails = {link: link.rsplit("/", 1)[-1].lower() for link in links}
        ordered = sorted(links, key=lambda k: (not tails[k].startswith(self._prefer or ("\0",)), k))
        return next((link for link in ordered if self._names(link, month_end)), None)

    def picks(self, links: list[str], month_end: date) -> list[str]:
        """Every link for ``month_end``, one per file name, for an AMC that files per scheme."""
        found: dict[str, str] = {}
        for link in sorted(links):
            if self._names(link, month_end):
                found.setdefault(_tail(link), link)
        return [found[tail] for tail in sorted(found)]

    def _names(self, link: str, month_end: date) -> bool:
        month = _MONTHS[month_end.month - 1]
        short = rf"(?<![a-z])(?:{month}|{month[:3]})(?![a-z])"
        two_digit = rf"{short}[^a-z0-9]{{0,2}}{month_end.year % 100:02d}(?!\d)"
        numeric = (
            rf"(?<!\d)(?:{month_end.day}[-. _]0?{month_end.month}[-. _]{month_end.year}"
            rf"|{month_end:%d%m%Y})(?!\d)"
        )
        tail = _tail(link)
        named = month in tail or re.search(short, tail) or re.search(numeric, tail)
        dated = str(month_end.year) in tail or re.search(two_digit, tail)
        return bool(
            named
            and dated
            and all(w in tail for w in self._require)
            and not any(w in tail for w in self._exclude)
        )

    async def portfolio(self, month_end: date) -> RawFile | None:
        """The month's file, or ``None`` when the page lists none for it.

        An AMC that files one workbook per scheme gets its month's files fetched in
        turn and kept as one zip, named in order and stamped 1980-01-01, so the same
        files give the same bytes.
        """
        listed = await self._listed()
        if not self._each:
            link = self.pick(listed, month_end)
            return None if link is None else await self._fetch(link)
        links = self.picks(listed, month_end)
        return await self._bundle(links) if links else None

    async def _bundle(self, links: list[str]) -> RawFile:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
            for link in links:
                fetched = await self._fetch(link)
                bundle.writestr(
                    zipfile.ZipInfo(_tail(link), (1980, 1, 1, 0, 0, 0)), fetched.content
                )
        return RawFile(self._page, datetime.now(UTC), buffer.getvalue())

    async def _fetch(self, link: str) -> RawFile:
        response = await self._http.get(link)
        if response.is_redirect and _same_site(link, response.headers["location"]):
            link = urljoin(link, response.headers["location"])
            response = await self._http.get(link)
        if response.status_code != 200:
            raise SourceError(f"{link} answered HTTP {response.status_code}.")
        return RawFile(link, datetime.now(UTC), response.content)

    def parse_portfolios(
        self,
        raw: RawFile,
        names: Mapping[str, int],
        fallback: date | None,
        codes: Mapping[str, int] | None = None,
    ) -> Portfolios:
        """Every scheme portfolio in the file."""
        return parse_portfolios(raw.content, names, fallback, codes)

    def sheet_codes(self, raw: RawFile, names: Mapping[str, int]) -> dict[str, int]:
        """The sheet codes that name one scheme each in the file."""
        return sheet_codes(raw.content, names) if self._stable_codes else {}


# A date in a title: "30th September 2026", "September2026", "Sep 30, 2026", "30.09.2026".
_TITLE_DATE = re.compile(
    r"(?<![a-z])(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[^a-z0-9]{0,3}"
    r"(?:\d{1,2}(?:st|nd|rd|th)?,?[^a-z0-9]{0,3})?((?:19|20)\d\d)"
    r"|(?<!\d)\d{1,2}[-./](\d{1,2})[-./]((?:19|20)\d\d)",
    re.I,
)


def _first_month(title: str) -> tuple[int, int] | None:
    """The year and month of a title's first date, if it has one."""
    found = _TITLE_DATE.search(title)
    if found is None:
        return None
    if found.group(1):
        return int(found.group(2)), [m[:3] for m in _MONTHS].index(found.group(1).lower()) + 1
    return int(found.group(4)), int(found.group(3))


def _tail(link: str) -> str:
    """A link's file name, lower case, with ``%20`` read as a space and no query."""
    return link.split("?", 1)[0].rsplit("/", 1)[-1].lower().replace("%20", " ")


def _same_site(link: str, target: str) -> bool:
    """A redirect stays on the link's site: under the link's host less its first label.

    ``betacms.tatamutualfund.com`` may send to ``www.tatamutualfund.com``; a link on a
    bare domain may only send to the same host.
    """
    host = urlsplit(link).hostname or ""
    to = urlsplit(urljoin(link, target)).hostname or ""
    parent = host.split(".", 1)[1] if host.count(".") >= 2 else host
    return to == parent or to.endswith("." + parent)


class TitledPortfolioAdapter(AmcPortfolioAdapter):
    """An AMC whose listing names each file's month in a title, not in its file name.

    A subclass reads the listing as (title, URL) pairs. The month's files are those
    whose title's first date is that month ("as on 30th September 2023 for ... Apr 2026
    ... Index Fund" is September 2023), kept as one zip with ``each``, else the first.
    """

    async def _titled(self, month_end: date) -> list[tuple[str, str]]:
        """Each listed file's title and URL."""
        raise NotImplementedError

    async def portfolio(self, month_end: date) -> RawFile | None:
        """The month's file or files, or ``None`` when none is listed."""
        found: dict[str, str] = {}
        for title, url in sorted(await self._titled(month_end)):
            words = title.lower()
            if (
                _first_month(title) == (month_end.year, month_end.month)
                and all(w in words for w in self._require)
                and not any(w in words for w in self._exclude)
            ):
                found.setdefault(_tail(url), url)
        links = [found[tail] for tail in sorted(found)]
        if not links:
            return None
        return await self._bundle(links) if self._each else await self._fetch(links[0])

    async def _json(self, response: Any) -> Any:
        if response.status_code != 200:
            raise SourceError(f"{self._page} answered HTTP {response.status_code}.")
        return json.loads(response.text)


class WhiteOakPortfolioAdapter(TitledPortfolioAdapter):
    """WhiteOak: a CMS lists one workbook per scheme a month, each with a document name.

    ``cms.whiteoakamc.com/api/scheme-portfolios`` answers 100 rows a page, filtered to
    the monthly period. A row's ``doc_name`` names the month ("... Monthly Portfolio
    Disclosure - 30th September2026"); its ``doc_file`` holds the file's URL, whose own
    name says "Sept_2026".
    """

    _documents: dict[str, str] | None = None

    async def _titled(self, month_end: date) -> list[tuple[str, str]]:
        if self._documents is None:
            self._documents = {}
            page, pages = 1, 1
            while page <= pages:
                found = await self._json(
                    await self._http.get(
                        self._page,
                        {
                            "pagination[page]": str(page),
                            "pagination[pageSize]": "100",
                            "filters[period][$eq]": "Monthly",
                            "populate": "doc_file",
                        },
                    )
                )
                pages = int(found["meta"]["pagination"]["pageCount"])
                for row in found["data"]:
                    file = ((row["attributes"].get("doc_file") or {}).get("data") or {}).get(
                        "attributes"
                    ) or {}
                    if file.get("url"):
                        self._documents[row["attributes"]["doc_name"]] = file["url"]
                page += 1
        return list(self._documents.items())


class TrustPortfolioAdapter(TitledPortfolioAdapter):
    """Trust: one JSON ``POST`` lists the monthly reports, each with a title and a URL.

    ``trustmf.com/api/api/Trust/GetData`` answers rows with a ``title`` ("TRUSTMF
    Monthly Portfolio Report as on 30.09.2026") and a ``fileurl`` whose name holds only
    an upload stamp.
    """

    async def _titled(self, month_end: date) -> list[tuple[str, str]]:
        found = await self._json(
            await self._http.post(self._page, self._listing or {}, self._headers)
        )
        return [
            (str(row.get("title", "")), row["fileurl"])
            for row in found.get("resultSetArray") or []
            if row.get("fileurl")
        ]


class MiraePortfolioAdapter(TitledPortfolioAdapter):
    """Mirae Asset: a paged JSON ``POST`` lists one workbook per scheme a month.

    ``miraeassetmf.co.in/AjaxService/GetDownloadsData`` (module ``portfolio_tab1``)
    answers rows with a ``Title`` ("Portfolio Details as on 30th September 2026 for
    Mirae Asset Flexi Cap Fund") and a site path in ``URL`` (``mafcf_sept2026.xlsx``).
    """

    _rows: list[tuple[str, str]] | None = None

    async def _titled(self, month_end: date) -> list[tuple[str, str]]:
        if self._rows is None:
            self._rows = []
            page, total = 1, 1
            while len(self._rows) < total:
                found = await self._json(
                    await self._http.post(
                        self._page,
                        {"request": {"modulename": "portfolio_tab1", "pgno": page, "pgsize": 500}},
                    )
                )
                total = int(found.get("DataCount") or 0)
                rows = found.get("Data") or []
                if not rows:
                    break
                self._rows += [
                    (str(r.get("Title", "")), urljoin(self._page, r["URL"]))
                    for r in rows
                    if r.get("URL")
                ]
                page += 1
        return self._rows


class SundaramPortfolioAdapter(TitledPortfolioAdapter):
    """Sundaram: one form ``POST`` answers every monthly file as HTML links with titles.

    The portfolios page calls its ``GetCategory`` method (``Catid=Monthly``), which
    answers each year's links (``/uploaddir/MonthlyPortfolio/monthlyportfolio_<stamp>
    .xlsx``) titled "Monthly Portfolio Disclosure Equity & Fund of Funds - Sep 2026" and
    "... Fixed Income - Sep 2026".
    """

    _rows: list[tuple[str, str]] | None = None

    async def _titled(self, month_end: date) -> list[tuple[str, str]]:
        if self._rows is None:
            response = await self._http.post_form(self._page, {"Catid": "Monthly"})
            if response.status_code != 200:
                raise SourceError(f"{self._page} answered HTTP {response.status_code}.")
            found = response.text.replace("\\'", "'")
            self._rows = [
                (re.sub(r"<[^>]+>", "", title).strip(), urljoin(self._page, href))
                for href, title in re.findall(
                    r"<a[^>]*href='([^']+\.xlsx?)'[^>]*>(.*?)</a>", found, re.S
                )
            ]
        return self._rows


class QuantumPortfolioAdapter(TitledPortfolioAdapter):
    """Quantum: one combined-portfolio page a year lists one all-funds workbook a month.

    ``quantumamc.com/portfolio/combined/-1/1/<year>/0`` (all schemes, monthly) lists the
    year's months; each link's click handler carries its title ("September 2026 - All
    Funds") beside the file's URL, whose name is a GUID.
    """

    _years: dict[int, list[tuple[str, str]]] | None = None

    async def _titled(self, month_end: date) -> list[tuple[str, str]]:
        self._years = self._years or {}
        if month_end.year not in self._years:
            url = self._page.format(year=month_end.year)
            response = await self._http.get(url)
            if response.status_code != 200:
                raise SourceError(f"{url} answered HTTP {response.status_code}.")
            self._years[month_end.year] = [
                (title, link)
                for link, title in re.findall(
                    r"GTMcodeforxml\('([^']+\.xlsx?)', '[^']*', '([^']*)'", response.text
                )
            ]
        return self._years[month_end.year]


class InvescoPortfolioAdapter(TitledPortfolioAdapter):
    """Invesco: one JSON ``GET`` per year and class lists each scheme's twelve months.

    ``invescomutualfund.com/api/CompleteMonthlyHoldings?year=&classification=`` answers
    a row per scheme with ``Name`` and ``JanUrl`` to ``DecUrl``, for the classes
    ``equity``, ``hybrid``, ``fixed-income``, ``fund-of-funds`` and ``index-funds``.
    A file's title is the month, the year and the scheme's name.
    """

    CLASSES = ("equity", "hybrid", "fixed-income", "fund-of-funds", "index-funds")
    _years: dict[int, list[tuple[str, str]]] | None = None

    async def _titled(self, month_end: date) -> list[tuple[str, str]]:
        self._years = self._years or {}
        if month_end.year not in self._years:
            rows: list[tuple[str, str]] = []
            for kind in self.CLASSES:
                found = await self._json(
                    await self._http.get(
                        self._page, {"year": str(month_end.year), "classification": kind}
                    )
                )
                for row in found:
                    for month in _MONTHS:
                        url = row.get(f"{month[:3].capitalize()}Url")
                        if url:
                            rows.append((f"{month} {month_end.year} {row['Name']}", url))
            self._years[month_end.year] = rows
        return self._years[month_end.year]


class LicPortfolioAdapter(AmcPortfolioAdapter):
    """LIC: one form ``POST`` per month lists that month's consolidated workbooks.

    The portfolios page's "Consolidated Portfolio" tab posts ``id=639`` (monthly), the
    month's number and the year to ``licmf.com/downloads/consolidated-portfolio-files``,
    which answers links to an equity and a debt workbook
    (``LIC MF Monthly Equity Portfolio_Sep_26.xlsx``).
    """

    async def portfolio(self, month_end: date) -> RawFile | None:
        """The month's workbooks as one zip, or ``None`` when none is listed."""
        form = {"id": "639", "month": str(month_end.month), "year": str(month_end.year)}
        listed = await self._http.post_form(self._page, form)
        if listed.status_code != 200:
            raise SourceError(f"{self._page} answered HTTP {listed.status_code}.")
        found = [urljoin(self._page, m.group(1)) for m in _LINK.finditer(listed.text)]
        links = self.picks(found, month_end)
        return await self._bundle(links) if links else None


class QuantPortfolioAdapter(AmcPortfolioAdapter):
    """quant: one JSON ``POST`` per year lists that year's monthly workbooks.

    The statutory-disclosures page posts ``{"id": "<year>", "cat": "MONTHLY PORTFOLIO"}``
    to ``quantmutual.com/statutorydisclosures.aspx/displaydisclouser``, which answers
    ``{"d": "<html>"}`` with links under ``/Admin/disclouser/``
    (``Monthly_portfolio_sept_30092026.xlsx``, ``Monthly_Portfolio_July26.xlsx``). A
    December file may be listed with the next year, so both years are read.
    """

    async def portfolio(self, month_end: date) -> RawFile | None:
        """The month's workbook, or ``None`` when neither year lists one."""
        links: list[str] = []
        for year in (month_end.year, month_end.year + 1):
            body: dict[str, object] = {"id": str(year), "cat": "MONTHLY PORTFOLIO"}
            listed = await self._http.post(self._page, body)
            if listed.status_code != 200:
                raise SourceError(f"{self._page} answered HTTP {listed.status_code}.")
            page = str(json.loads(listed.text).get("d") or "").replace("\\'", "'")
            links += [urljoin(self._page, m.group(1)) for m in _LINK.finditer(page)]
        link = self.pick(links, month_end)
        return None if link is None else await self._fetch(link)


class BarodaPortfolioAdapter(AmcPortfolioAdapter):
    """Baroda BNP Paribas: a form ``POST`` lists the files uploaded in one month.

    The portfolios page (``barodabnpparibasmf.in/downloads/monthly-portfolio-scheme``)
    issues a CSRF token and a session cookie and sends both with its listing request
    to ``ajax-load-more-documents-new``; the adapter does the same. A month end's files
    are uploaded in the next month or the one after. The listing answers JSON with HTML
    entries; the all-funds workbook is the one titled "Monthly Portfolio - all funds as
    on 30th September 2026". File names carry only numeric dates, so the title picks it.
    """

    _LISTING = "https://www.barodabnpparibasmf.in/ajax-load-more-documents-new"
    _TOKEN = re.compile(r'name="csrf_test_name" value="([^"]+)"')
    _ENTRY = re.compile(r'file-name">([^<]+)<.*?href="([^"]+)"', re.S)
    # ponytail: the listing honours its month filter only some of the time (observed
    # 2026-10-24), so pages are read until the title shows; cap the walk.
    _MAX_PAGES = 120

    async def _entries(self, token: str, upload: date) -> AsyncIterator[tuple[str, str]]:
        """Every listed (title, link) for an upload month, page by page as "Load more" reads."""
        page, total, remaining = "0", "48", "0"
        for _ in range(self._MAX_PAGES):
            listed = await self._http.post_form(
                self._LISTING,
                {
                    "csrf_test_name": token,
                    "cnt": total,
                    "pagination": page,
                    "send_category": "17",
                    "send_year": str(upload.year),
                    "send_month": str(upload.month),
                    "remaining_cnt": remaining,
                },
                {"X-Requested-With": "XMLHttpRequest", "Referer": self._page},
            )
            if listed.status_code != 200:
                raise SourceError(f"{self._LISTING} answered HTTP {listed.status_code}.")
            body = json.loads(listed.text)
            for entry in self._ENTRY.findall(body.get("data", "")):
                yield entry
            if body.get("status") != "Y":
                return
            page, total = str(body["pagination"]), str(body["total_row"])
            remaining = str(body["remaining_cnt"])

    async def portfolio(self, month_end: date) -> RawFile | None:
        """The month's all-funds workbook, or ``None`` when no upload lists it."""
        page = await self._http.get(self._page)
        token = self._TOKEN.search(page.text)
        if page.status_code != 200 or token is None:
            raise SourceError(f"{self._page} gave no listing token (HTTP {page.status_code}).")
        title = f"{_MONTHS[month_end.month - 1]} {month_end.year}"
        upload = month_end + timedelta(days=1)
        for _ in range(2):
            async for name, link in self._entries(token.group(1), upload):
                if "all funds" in name.lower() and title in name.lower():
                    response = await self._http.get(link)
                    if response.status_code != 200:
                        raise SourceError(f"{link} answered HTTP {response.status_code}.")
                    return RawFile(link, datetime.now(UTC), response.content)
            upload = (upload.replace(day=28) + timedelta(days=4)).replace(day=1)
        return None


class UtiPortfolioAdapter(AmcPortfolioAdapter):
    """UTI: one ``GET`` per month lists the consolidated portfolio zip.

    The downloads page asks ``utimf.com/api/get-consolidate-portfolio-disclosure``
    with the year and the month's name; the answer is JSON rows with each file's
    ``url``. The zip holds one sheet that stacks every scheme's portfolio.
    """

    async def portfolio(self, month_end: date) -> RawFile | None:
        """The month's consolidated zip, or ``None`` when the month lists none."""
        month = _MONTHS[month_end.month - 1].capitalize()
        listed = await self._http.get(self._page, {"year": str(month_end.year), "month": month})
        if listed.status_code != 200:
            raise SourceError(f"{self._page} answered HTTP {listed.status_code}.")
        for row in json.loads(listed.text).get("rows", []):
            if "consolidated" in str(row.get("name", "")).lower() and row.get("url"):
                response = await self._http.get(row["url"])
                if response.status_code != 200:
                    raise SourceError(f"{row['url']} answered HTTP {response.status_code}.")
                return RawFile(row["url"], datetime.now(UTC), response.content)
        return None


# AMCs whose files a person downloads, with why Wickstreet does not fetch them
# (checked 2026-10-24; the owner authorised manual import and local storage).
MANUAL = {
    "kotak": "a Radware bot check guards the site",
    "hdfc": "the site answers HTTP 403 to clients other than a browser",
    "edelweiss": "the site answers HTTP 403 to clients other than a browser",
    "absl": "its terms bar robots and systematic retrieval",
    "wealthco": "a TSPD bot check guards the site",
    "hsbc": "its terms bar robots and automated access",
    "franklin": "its terms bar robots and automated access",
    "jio": "its terms bar robots and automated access",
    "axis": "the listing needs the page's session token; robots.txt disallows /cms/",
    "bandhan": "the listing API carries encrypted, signed payloads",
    "mahindra": "the listing API carries encrypted, signed payloads",
    "iti": "the listing API carries encrypted, signed payloads",
    "jm": "the listing API carries encrypted, signed payloads",
    "canara": "robots.txt disallows /wp-content/uploads/, where the files sit",
    "union": "the monthly listing does not load",
    "boi": "no machine-readable monthly listing was found",
    "bajaj": "no machine-readable monthly listing was found",
    "360one": "no machine-readable monthly listing was found",
    "shriram": "no machine-readable monthly listing was found",
    "navi": "no machine-readable monthly listing was found",
    "zerodha": "no machine-readable monthly listing was found",
}


class ManualPortfolioSource:
    """An AMC whose files a person downloads in a browser; Wickstreet fetches nothing.

    Its files come in through ``wickstreet mf import-portfolios`` and the parser the
    fetched AMCs use. Its layout is unverified until one of its genuine files has been
    imported and checked, so a portfolio that does not reconcile is held back.
    """

    adapter_version = AmcPortfolioAdapter.adapter_version
    layout_verified = False

    def __init__(self, name: str, why: str) -> None:
        """``why`` says why Wickstreet does not fetch the AMC's files."""
        self.name = name
        self._why = why

    async def portfolio(self, month_end: date) -> RawFile | None:
        """Refuse: this AMC is manual import only."""
        raise SourceError(
            f"{self.name} is manual import only: {self._why}. Download the month's file "
            "in a browser and run `wickstreet mf import-portfolios`."
        )

    def parse_portfolios(
        self,
        raw: RawFile,
        names: Mapping[str, int],
        fallback: date | None,
        codes: Mapping[str, int] | None = None,
    ) -> Portfolios:
        """Every scheme portfolio in the file."""
        return parse_portfolios(raw.content, names, fallback, codes)

    def sheet_codes(self, raw: RawFile, names: Mapping[str, int]) -> dict[str, int]:
        """The sheet codes that name one scheme each in the file."""
        return sheet_codes(raw.content, names)


def manual_sources() -> dict[str, ManualPortfolioSource]:
    """Every manual-import AMC, by name."""
    return {name: ManualPortfolioSource(name, why) for name, why in MANUAL.items()}


def amc_adapters(
    *, min_interval_seconds: float, timeout_seconds: float, max_attempts: int
) -> dict[str, AmcPortfolioAdapter]:
    """The AMCs whose disclosure pages or listing endpoints give their files' links."""

    def http(
        name: str,
        page: str,
        listing: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        files: str | None = None,
        each: bool = False,
        stable_codes: bool = True,
        **words: tuple[str, ...],
    ) -> AmcPortfolioAdapter:
        return AmcPortfolioAdapter(
            name,
            page,
            require=words["require"],
            exclude=words.get("exclude", ()),
            prefer=words.get("prefer", ()),
            listing=listing,
            headers=headers,
            files=files,
            each=each,
            stable_codes=stable_codes,
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        )

    return {
        "ppfas": http(
            "ppfas",
            "https://amc.ppfas.com/downloads/portfolio-disclosure/",
            require=("portfolio",),
            exclude=("fortnight", "half"),
            prefer=("ppfas_monthly_portfolio", "monthly-portfolio", "monthly_portfolio"),
        ),
        "dsp": http(
            "dsp",
            "https://www.dspim.com/mandatory-disclosures/portfolio-disclosures",
            require=("month", ".zip"),
            exclude=("fortnight", "half"),
        ),
        "nippon": http(
            "nippon",
            "https://mf.nipponindiaim.com/investor-service/downloads/"
            "factsheet-portfolio-and-other-disclosures",
            require=("monthly", "portfolio"),
            exclude=("fortnight", "half"),
        ),
        "sbi": http(
            "sbi",
            "https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets",
            {"FundId": "", "PSYear": "", "PSMonth": "", "PSFrequency": "Monthly"},
            require=("all-scheme", "monthly", "portfolio"),
            exclude=("fortnight", "half"),
        ),
        "icici": http(
            "icici",
            "https://apimf.icicipruamc.com/nms/v1/downloads/files",
            {
                "categoryId": "26a073d7-08d2-4a95-95fa-f83a4ee51e40",
                "schemeCategory": "",
                "userType": "Investor",
                "fileType": "All",
                "page": "1",
                "size": "200",
                "filter": [],
                "categoryName": "OTHERS",
            },
            {"env": "api"},
            "https://www.icicipruamc.com/blob",
            require=("monthly-portfolio-disclosure",),
            exclude=("fortnight", "half"),
        ),
        "pgim": http(
            "pgim",
            "https://www.pgimindia.com/api/v1/brochure/published/disclosure",
            {"headerId": 2, "sectionId": "SECTION_747960037", "source": "W", "branchCode": None},
            each=True,
            require=(),
            exclude=("fortnight",),
        ),
        "samco": http(
            "samco",
            "https://www.samcomf.com/StatutoryDisclosure",
            each=True,
            require=("monthly_portfolio",),
            exclude=("fortnight",),
        ),
        "tata": http(
            "tata",
            "https://www.tatamutualfund.com/schemes-related/portfolio",
            require=("portfolio",),
            exclude=("fortnight", "half"),
        ),
        "groww": http(
            "groww",
            "https://www.growwmf.in/statutory-disclosure/portfolio",
            require=("monthly", "portfolio"),
            exclude=("fortn", "half"),
        ),
        "motilal": http(
            "motilal",
            "https://www.motilaloswalmf.com/content/aem-cloud-dept-backend-motilal-oswal/api/"
            "search-documents.json?year=&category=month%20end%20portfolio&month=&type=mf",
            # A code such as "YO27" named another fund of funds in 2024 (seen 2026-10-24).
            stable_codes=False,
            require=("portfolio",),
            exclude=("fortnight", "forthnight", "half", "performance"),
        ),
        "whiteoak": WhiteOakPortfolioAdapter(
            "whiteoak",
            "https://cms.whiteoakamc.com/api/scheme-portfolios",
            each=True,
            require=("monthly",),
            exclude=("fortnight",),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "trust": TrustPortfolioAdapter(
            "trust",
            "https://www.trustmf.com/api/api/Trust/GetData",
            require=("monthly", "portfolio"),
            listing={
                "systemQueryFileName": "disclosuresweb.xml",
                "tagName": "GetDisclosureByType",
                "searchField": "",
                "searchValue": "",
                "sortField": "uploaddate",
                "sortDirection": "DESC",
                "replaceField": "_slug_",
                "replaceValue": "portfolio-monthly-disclosure",
            },
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "mirae": MiraePortfolioAdapter(
            "mirae",
            "https://www.miraeassetmf.co.in/AjaxService/GetDownloadsData",
            each=True,
            require=("portfolio",),
            exclude=("fortnight", "half"),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "sundaram": SundaramPortfolioAdapter(
            "sundaram",
            "https://www.sundarammutual.com/ajax/"
            "Modules_Disclosure_Monthly_Fortnightly_Adhoc_Portfolios,App_Web_0k2jxmrp.ashx"
            "?_method=GetCategory&_session=no",
            each=True,
            require=("monthly", "portfolio"),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "lic": LicPortfolioAdapter(
            "lic",
            "https://www.licmf.com/downloads/consolidated-portfolio-files",
            require=("monthly", "portfolio"),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "quant": QuantPortfolioAdapter(
            "quant",
            "https://quantmutual.com/statutorydisclosures.aspx/displaydisclouser",
            require=("monthly", "portfolio"),
            exclude=("fortnight",),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "quantum": QuantumPortfolioAdapter(
            "quantum",
            "https://www.quantumamc.com/portfolio/combined/-1/1/{year}/0",
            require=("all funds",),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "invesco": InvescoPortfolioAdapter(
            "invesco",
            "https://www.invescomutualfund.com/api/CompleteMonthlyHoldings",
            each=True,
            require=(),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "uti": UtiPortfolioAdapter(
            "uti",
            "https://www.utimf.com/api/get-consolidate-portfolio-disclosure",
            require=(),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
        "barodabnp": BarodaPortfolioAdapter(
            "barodabnp",
            "https://www.barodabnpparibasmf.in/downloads/monthly-portfolio-scheme",
            require=(),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
    }
