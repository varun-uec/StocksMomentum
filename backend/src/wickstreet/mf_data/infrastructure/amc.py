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
- Trust: see :class:`TrustPortfolioAdapter`.
- WhiteOak: see :class:`WhiteOakPortfolioAdapter`.
- Baroda BNP Paribas: see :class:`BarodaPortfolioAdapter`.
- UTI: see :class:`UtiPortfolioAdapter`.

Other AMCs build their pages in the browser from sources not yet read, so their
files come in through ``wickstreet mf import-portfolios``, which reads the same
layouts.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, date, datetime, timedelta
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

    adapter_version = "amc-portfolios-2026-10-24.5"

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


def _tail(link: str) -> str:
    """A link's file name, lower case, with ``%20`` read as a space."""
    return link.rsplit("/", 1)[-1].lower().replace("%20", " ")


def _same_site(link: str, target: str) -> bool:
    """A redirect stays on the link's site: under the link's host less its first label.

    ``betacms.tatamutualfund.com`` may send to ``www.tatamutualfund.com``; a link on a
    bare domain may only send to the same host.
    """
    host = urlsplit(link).hostname or ""
    to = urlsplit(urljoin(link, target)).hostname or ""
    parent = host.split(".", 1)[1] if host.count(".") >= 2 else host
    return to == parent or to.endswith("." + parent)


class WhiteOakPortfolioAdapter(AmcPortfolioAdapter):
    """WhiteOak: a CMS lists one workbook per scheme a month, each with a document name.

    ``cms.whiteoakamc.com/api/scheme-portfolios`` answers 100 rows a page, filtered to
    the monthly period. A row's ``doc_name`` names the month ("... Monthly Portfolio
    Disclosure - 30th September2026"); its ``doc_file`` holds the file's URL, whose own
    name says "Sept_2026", so the month is read from the document name.
    """

    _documents: dict[str, str] | None = None

    async def portfolio(self, month_end: date) -> RawFile | None:
        """Every scheme's workbook for the month, as one zip; ``None`` when none is listed."""
        if self._documents is None:
            self._documents = {}
            page, pages = 1, 1
            while page <= pages:
                listed = await self._http.get(
                    self._page,
                    {
                        "pagination[page]": str(page),
                        "pagination[pageSize]": "100",
                        "filters[period][$eq]": "Monthly",
                        "populate": "doc_file",
                    },
                )
                if listed.status_code != 200:
                    raise SourceError(f"{self._page} answered HTTP {listed.status_code}.")
                found = json.loads(listed.text)
                pages = int(found["meta"]["pagination"]["pageCount"])
                for row in found["data"]:
                    file = ((row["attributes"].get("doc_file") or {}).get("data") or {}).get(
                        "attributes"
                    ) or {}
                    if file.get("url"):
                        self._documents[row["attributes"]["doc_name"]] = file["url"]
                page += 1
        links = [
            url for name, url in sorted(self._documents.items()) if self._names(name, month_end)
        ]
        return await self._bundle(links) if links else None


class TrustPortfolioAdapter(AmcPortfolioAdapter):
    """Trust: one JSON ``POST`` lists the monthly reports, each with a title and a URL.

    ``trustmf.com/api/api/Trust/GetData`` answers rows with a ``title`` ("TRUSTMF
    Monthly Portfolio Report as on 30.09.2026") and a ``fileurl`` whose name holds only
    an upload stamp, so the month is read from the title.
    """

    async def portfolio(self, month_end: date) -> RawFile | None:
        """The month's report, or ``None`` when none is listed."""
        listed = await self._http.post(self._page, self._listing or {}, self._headers)
        if listed.status_code != 200:
            raise SourceError(f"{self._page} answered HTTP {listed.status_code}.")
        rows = json.loads(listed.text).get("resultSetArray") or []
        found = sorted(
            row["fileurl"]
            for row in rows
            if row.get("fileurl") and self._names(str(row.get("title", "")), month_end)
        )
        return await self._fetch(found[0]) if found else None


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
