"""AMC portfolio adapters: each AMC's own monthly portfolio files (doc 21 E4).

An AMC lists its files on one page. The adapter reads the page, picks the month-end
file by the month and year in its link, and fetches it. Pages observed on 2026-10-24:

- PPFAS: ``amc.ppfas.com/downloads/portfolio-disclosure/``, one workbook a month with a
  sheet per scheme (``PPFAS_Monthly_Portfolio_Report_September_30_2026.xls``, an XLSX;
  before March 2026 a binary XLS), beside one file per scheme.
- DSP: ``dspim.com/mandatory-disclosures/portfolio-disclosures``, one zip a
  month of workbooks (``monthend-portfolios_30_june_2026.zip``).

Other AMCs build their pages in the browser, so their files come in through
``wickstreet mf import-portfolios``, which reads the same layouts.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from urllib.parse import urljoin

from wickstreet.mf_data.domain.model import Portfolios, RawFile
from wickstreet.mf_data.domain.ports import SourceError
from wickstreet.mf_data.infrastructure.client import COMPATIBLE_USER_AGENT, PacedClient
from wickstreet.mf_data.infrastructure.portfolios import parse_portfolios

_LINK = re.compile(r"""href=["']([^"']+\.(?:xlsx?|zip))(?:\?[^"']*)?["']""", re.I)
_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)  # fmt: skip


class AmcPortfolioAdapter:
    """One AMC's monthly portfolio files, found on its disclosure page."""

    adapter_version = "amc-portfolios-2026-10-24.1"

    def __init__(
        self,
        name: str,
        page: str,
        *,
        require: tuple[str, ...],
        exclude: tuple[str, ...] = (),
        prefer: tuple[str, ...] = (),
        min_interval_seconds: float,
        timeout_seconds: float,
        max_attempts: int,
    ) -> None:
        """Read ``page``; a link must hold every ``require`` word and no ``exclude`` word."""
        self.name = name
        self._page = page
        self._require = require
        self._exclude = exclude
        self._prefer = prefer
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
            response = await self._http.get(self._page)
            if response.status_code != 200:
                raise SourceError(f"{self._page} answered HTTP {response.status_code}.")
            links = {urljoin(self._page, m.group(1)) for m in _LINK.finditer(response.text)}
            self._links = sorted(links)
        return self._links

    def pick(self, links: list[str], month_end: date) -> str | None:
        """The link for ``month_end``: its month (full or short), year and words.

        A link whose file name starts with a ``prefer`` prefix wins, such as an AMC's
        all-scheme workbook over its per-scheme files.
        """
        month = _MONTHS[month_end.month - 1]
        tails = {link: link.rsplit("/", 1)[-1].lower() for link in links}
        ordered = sorted(links, key=lambda k: (not tails[k].startswith(self._prefer or ("\0",)), k))
        for link in ordered:
            tail = link.rsplit("/", 1)[-1].lower().replace("%20", " ")
            named = month in tail or re.search(rf"(?<![a-z]){month[:3]}(?![a-z])", tail)
            if (
                named
                and str(month_end.year) in tail
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


def amc_adapters(
    *, min_interval_seconds: float, timeout_seconds: float, max_attempts: int
) -> dict[str, AmcPortfolioAdapter]:
    """The AMCs whose disclosure pages list their files in plain HTML."""

    def http(name: str, page: str, **words: tuple[str, ...]) -> AmcPortfolioAdapter:
        return AmcPortfolioAdapter(
            name,
            page,
            require=words["require"],
            exclude=words.get("exclude", ()),
            prefer=words.get("prefer", ()),
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
    }
