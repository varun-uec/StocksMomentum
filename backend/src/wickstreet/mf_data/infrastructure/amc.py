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
- Baroda BNP Paribas: see :class:`BarodaPortfolioAdapter`.

Other AMCs build their pages in the browser from sources not yet read, so their
files come in through ``wickstreet mf import-portfolios``, which reads the same
layouts.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urljoin

from wickstreet.mf_data.domain.model import Portfolios, RawFile
from wickstreet.mf_data.domain.ports import SourceError
from wickstreet.mf_data.infrastructure.client import COMPATIBLE_USER_AGENT, PacedClient
from wickstreet.mf_data.infrastructure.portfolios import parse_portfolios

# A link in a page (href) or in a JSON listing ("url").
_LINK = re.compile(r"""(?:href=|"url"\s*:\s*)["']([^"']+\.(?:xlsx?|zip))(?:\?[^"']*)?["']""", re.I)
_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)  # fmt: skip


class AmcPortfolioAdapter:
    """One AMC's monthly portfolio files, found on its disclosure page."""

    adapter_version = "amc-portfolios-2026-10-24.3"

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
        min_interval_seconds: float,
        timeout_seconds: float,
        max_attempts: int,
    ) -> None:
        """Read ``page``; a link must hold every ``require`` word and no ``exclude`` word.

        With ``listing``, the page is an endpoint that lists the files when it is sent
        that JSON body, with ``headers``. With ``files``, a listed path is read under
        that prefix rather than against the page.
        """
        self.name = name
        self._page = page
        self._require = require
        self._exclude = exclude
        self._prefer = prefer
        self._listing = listing
        self._headers = headers
        self._files = files
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
            found = (m.group(1) for m in _LINK.finditer(response.text))
            links = {
                urljoin(self._page, link) if self._files is None else self._files + link
                for link in found
            }
            self._links = sorted(links)
        return self._links

    def pick(self, links: list[str], month_end: date) -> str | None:
        """The link for ``month_end``: its month (full or short), year and words.

        The year is four digits anywhere, or two digits right after the month
        ("30-Sep-26"), so a day such as the 26 in "26-Sep-2025" is never a year. A link
        whose file name starts with a ``prefer`` prefix wins, such as an AMC's
        all-scheme workbook over its per-scheme files.
        """
        month = _MONTHS[month_end.month - 1]
        short = rf"(?<![a-z])(?:{month}|{month[:3]})(?![a-z])"
        two_digit = rf"{short}[^a-z0-9]{{0,2}}{month_end.year % 100:02d}(?!\d)"
        tails = {link: link.rsplit("/", 1)[-1].lower() for link in links}
        ordered = sorted(links, key=lambda k: (not tails[k].startswith(self._prefer or ("\0",)), k))
        for link in ordered:
            tail = link.rsplit("/", 1)[-1].lower().replace("%20", " ")
            named = month in tail or re.search(short, tail)
            dated = str(month_end.year) in tail or re.search(two_digit, tail)
            if (
                named
                and dated
                and all(w in tail for w in self._require)
                and not any(w in tail for w in self._exclude)
            ):
                return link
        return None

    async def portfolio(self, month_end: date) -> RawFile | None:
        """The month's file, or ``None`` when the page lists none for it."""
        link = self.pick(await self._listed(), month_end)
        if link is None:
            return None
        response = await self._http.get(link)
        if response.status_code != 200:
            raise SourceError(f"{link} answered HTTP {response.status_code}.")
        return RawFile(link, datetime.now(UTC), response.content)

    def parse_portfolios(
        self, raw: RawFile, names: Mapping[str, int], fallback: date | None
    ) -> Portfolios:
        """Every scheme portfolio in the file."""
        return parse_portfolios(raw.content, names, fallback)


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
        "barodabnp": BarodaPortfolioAdapter(
            "barodabnp",
            "https://www.barodabnpparibasmf.in/downloads/monthly-portfolio-scheme",
            require=(),
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ),
    }
