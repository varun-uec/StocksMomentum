"""Join keys from source rows to AMFI scheme ids (doc 21 E1, E3): code, name, NAV pair."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal

from wickstreet.mf_data.domain.model import SchemeRef


def compact(text: str) -> str:
    """A join key for names and codes: lower case, ``&`` as ``and``, letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", text.lower().replace("&", "and"))


# AMFI's scheme list adds these notes to a name; AMC files and reports leave them out:
# "(Existing number of Segregated Portfolios - 1)", "(the scheme has 2 segregated
# portfolios)", "(erstwhile Bluechip Fund)", "( Formerly Know as Sundaram Blue Chip
# Fund)".
_SEGREGATED_NOTE = re.compile(
    r"\s*\(\s*(?:existing\s+number\s+of\s+segregated\s+portfolios?|the\s+scheme\s+has"
    r"|erstwhile|formerly)[^()]*\)",
    re.I,
)

# AMC files shorten what AMFI spells out: "Gold ETF FOF" for "Gold ETF Fund of Fund",
# "APR-2029" and "Sept 2027" for "April 2029" and "September 2027", and an FMP's
# "Series 1" for "Series 1 (3668 Days)".
_FUND_OF_FUNDS = re.compile(r"\bfunds?\s+of\s+funds?\b", re.I)
_MONTH_NAME = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b(?=[\s.-]*\d)", re.I
)
_TENURE = re.compile(r"\s*\(\s*\d+\s*days\s*\)", re.I)


def loose(text: str) -> str:
    """A name's last-resort join key: "fund of funds" as "fof", a month as three letters.

    A source name joins by this key only when its own key joins no scheme. The ``~``
    keeps these keys apart from ``compact`` ones.
    """
    return "~" + compact(_MONTH_NAME.sub(r"\1", _FUND_OF_FUNDS.sub("fof", text)))


def scheme_keys(
    schemes: Sequence[SchemeRef], sebi_codes: Mapping[int, str]
) -> tuple[dict[str, int], dict[str, int]]:
    """SEBI code to scheme id, and name to scheme id.

    A name two schemes share joins the one that is ``live``, when only one is (AMFI
    lists "ICICI Prudential Liquid Fund", "... Fund -" and "... Fund-"; current plans
    join the second); else it joins neither, and a NAV pair may join the row. A name
    AMFI lists with a segregated-portfolio or former-name note also joins without it,
    unless another scheme has that shorter name. Last, a name joins by its ``loose`` key,
    which AMFI's name gives without its tenure: a filed name never drops its own, so
    "SBI Debt Fund Series C - 27 (1260 Days)" never joins "... (391 Days)".
    """
    codes = {compact(code): sd_id for sd_id, code in sebi_codes.items()}

    def keyed(key_of: Callable[[SchemeRef], str]) -> dict[str, int]:
        sharers: dict[str, set[SchemeRef]] = {}
        for scheme in schemes:
            sharers.setdefault(key_of(scheme), set()).add(scheme)
        found: dict[str, int] = {}
        for key, group in sharers.items():
            ids = {s.sd_id for s in group}
            live = {s.sd_id for s in group if s.live}
            if len(ids) == 1 or len(live) == 1:
                found[key] = min(ids) if len(ids) == 1 else live.pop()
        return found

    names = keyed(lambda s: compact(s.name))
    bare = keyed(lambda s: compact(_SEGREGATED_NOTE.sub("", s.name)))
    shortened = keyed(lambda s: loose(_TENURE.sub("", _SEGREGATED_NOTE.sub("", s.name))))
    return codes, shortened | bare | names


_TRAILING_NOTE = re.compile(r"\s*\([^()]*\)\s*$")


def join_by_name(names: Mapping[str, int], name: str) -> int | None:
    """The scheme a filed name names, also without a trailing note such as a ticker.

    "Motilal Oswal Nifty 500 Index Fund (MOFNIFTY500)" joins "... Index Fund".
    Last, the whole name joins by its ``loose`` key.
    """
    found = names.get(compact(name))
    if found is None and _TRAILING_NOTE.search(name):
        found = names.get(compact(_TRAILING_NOTE.sub("", name)))
    return found if found is not None else names.get(loose(name))


CENT = Decimal("0.01")


def _cents(nav: Decimal) -> Decimal:
    return nav.quantize(CENT, ROUND_HALF_UP)


def nav_index(navs: Mapping[int, Sequence[Decimal]]) -> dict[Decimal, set[int]]:
    """Each NAV, to the paisa, to the schemes with a plan-option at that NAV."""
    index: dict[Decimal, set[int]] = {}
    for sd_id, values in navs.items():
        for value in values:
            index.setdefault(_cents(value), set()).add(sd_id)
    return index


def join_by_navs(index: Mapping[Decimal, set[int]], filed: Sequence[Decimal | None]) -> int | None:
    """The one scheme whose plan-options carry every filed NAV, else ``None``.

    A row names the scheme's regular and direct NAVs; two different NAVs must point to
    the same single scheme, so a common NAV such as 10.00 never joins on its own.
    """
    given = {_cents(v) for v in filed if v is not None}
    if len(given) < 2:
        return None
    found = set.intersection(*(index.get(v, set()) for v in given))
    return next(iter(found)) if len(found) == 1 else None


def pick_by_navs(
    index: Mapping[Decimal, set[int]], sd_id: int, rows: Sequence[Sequence[Decimal | None]]
) -> int | None:
    """Of rows that share one scheme's name, the one whose filed NAVs are that scheme's.

    AMFI's performance file can list two schemes under one name: "Sundaram Banking and
    PSU Debt Fund" twice in 2020, one row an older scheme's. The row is the one, and the
    only one, that files a NAV the scheme has that day; else ``None``, and the caller
    keeps its first row as before.
    """
    own = [
        k
        for k, filed in enumerate(rows)
        if any(sd_id in index.get(_cents(v), set()) for v in filed if v is not None)
    ]
    return own[0] if len(own) == 1 else None
