"""Plain-language screen requests read into ordinary Wickstreet filter trees.

"Diversified equity funds with consistent five-year performance, relatively low
drawdowns and TER below 1%" becomes the same conditions a user could build by
hand. The reading is deterministic and rule-based: every condition names a
registry field, every threshold is the user's own number or a stated category
position, and nothing about a fund is asserted here. Words that match no rule
are returned as not understood rather than guessed. The result is validated
with the screener's own parser, so it can only describe a runnable screen.

A refinement ("also under 0.8% TER", "remove the drawdown limit") is read
against the current conditions: a new clause replaces conditions on the same
fields, a removal drops them, and everything else stays.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from wickstreet.analytics.domain.presets import DIVERSIFIED_EQUITY
from wickstreet.analytics.domain.screening import parse_filter, parse_sort
from wickstreet.mf_data.domain.amc_identity import AMCS

Node = dict[str, Any]

MAX_COLUMNS = 7
_DEFAULT_COLUMNS = ("score", "cagr_3y", "mdd_3y", "ter")


@dataclass(frozen=True, slots=True)
class Clause:
    """One understood part of the request and the conditions it adds."""

    phrase: str
    explanation: str
    conditions: tuple[Node, ...] = ()
    removes: frozenset[str] = frozenset()
    sort: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Interpretation:
    """A runnable screen and how each part of the request was read."""

    filter: dict[str, list[Node]]
    sort: list[dict[str, str]]
    columns: list[str]
    clauses: list[Clause]
    assumptions: list[str]
    not_understood: list[str]
    refined: bool = False
    notes: list[str] = field(default_factory=list)


# --- vocabulary -----------------------------------------------------------------

_EQ = "Equity Scheme - "
_CATEGORIES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    # (pattern, categories, label). Longer phrases first; "large cap" must not eat "large & mid".
    (
        r"diversified equity|diversified",
        tuple(DIVERSIFIED_EQUITY),
        "Diversified equity (no sector or theme funds)",
    ),
    (r"large\s*(?:&|and)\s*mid\s*-?\s*caps?", (_EQ + "Large & Mid Cap Fund",), "Large & Mid Cap"),
    (r"large\s*-?\s*caps?", (_EQ + "Large Cap Fund",), "Large Cap"),
    (r"mid\s*-?\s*caps?", (_EQ + "Mid Cap Fund",), "Mid Cap"),
    (r"small\s*-?\s*caps?", (_EQ + "Small Cap Fund",), "Small Cap"),
    (r"multi\s*-?\s*caps?", (_EQ + "Multi Cap Fund",), "Multi Cap"),
    (r"flexi\s*-?\s*caps?", (_EQ + "Flexi Cap Fund",), "Flexi Cap"),
    (r"focused", (_EQ + "Focused Fund",), "Focused"),
    (r"contra", (_EQ + "Contra Fund",), "Contra"),
    (r"value funds?", (_EQ + "Value Fund",), "Value"),
    (r"dividend yield", (_EQ + "Dividend Yield Fund",), "Dividend Yield"),
    (r"elss|tax[- ]sav(?:ing|er)s?", (_EQ + "ELSS",), "ELSS (tax saving)"),
    (r"sectoral|thematic|sector funds?", (_EQ + "Sectoral/ Thematic",), "Sectoral/Thematic"),
    (r"index funds?|index", ("Other Scheme - Index Funds",), "Index funds"),
    (r"gold etfs?|gold", ("Other Scheme - Gold ETF",), "Gold ETF"),
    (r"etfs?", ("Other Scheme - Other  ETFs",), "ETFs"),
    (
        r"international|overseas|global|foreign",
        ("Other Scheme - FoF Overseas",),
        "Overseas fund of funds",
    ),
    (r"overnight", ("Debt Scheme - Overnight Fund",), "Overnight"),
    (r"liquid", ("Debt Scheme - Liquid Fund",), "Liquid"),
    (
        r"ultra\s*short(?: duration)?",
        ("Debt Scheme - Ultra Short Duration Fund",),
        "Ultra Short Duration",
    ),
    (r"low duration", ("Debt Scheme - Low Duration Fund",), "Low Duration"),
    (r"money market", ("Debt Scheme - Money Market Fund",), "Money Market"),
    (r"short duration|short term debt", ("Debt Scheme - Short Duration Fund",), "Short Duration"),
    (r"corporate bonds?", ("Debt Scheme - Corporate Bond Fund",), "Corporate Bond"),
    (r"credit risk", ("Debt Scheme - Credit Risk Fund",), "Credit Risk"),
    (r"banking (?:and|&) psu|psu debt", ("Debt Scheme - Banking and PSU Fund",), "Banking and PSU"),
    (r"gilts?", ("Debt Scheme - Gilt Fund",), "Gilt"),
    (r"dynamic bonds?", ("Debt Scheme - Dynamic Bond",), "Dynamic Bond"),
    (r"arbitrage", ("Hybrid Scheme - Arbitrage Fund",), "Arbitrage"),
    (
        r"balanced advantage|baf|dynamic asset allocation",
        ("Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage",),
        "Balanced Advantage",
    ),
    (r"aggressive hybrid", ("Hybrid Scheme - Aggressive Hybrid Fund",), "Aggressive Hybrid"),
    (r"conservative hybrid", ("Hybrid Scheme - Conservative Hybrid Fund",), "Conservative Hybrid"),
    (r"multi\s*-?\s*asset", ("Hybrid Scheme - Multi Asset Allocation",), "Multi Asset"),
    (r"equity savings", ("Hybrid Scheme - Equity Savings",), "Equity Savings"),
    (r"retirement", ("Solution Oriented Scheme - Retirement Fund",), "Retirement"),
)
_ASSET_CLASSES = (("equity", "Equity"), ("debt", "Debt"), ("hybrid", "Hybrid"))

# Short names that are also ordinary words need "mutual fund", "mf" or "amc" after them.
_AMBIGUOUS_HOUSES = {"ask", "choice", "trust", "union", "navi", "quant", "unifi"}
# First words of house names that are also ordinary words.
_COMMON_WORDS = {"bank", "old", "the", "wealth"}
# Brand names investors use for a house whose AMFI label differs. Interpretation only.
_HOUSE_BRANDS = {"parag parikh": "in-amc-ppfas"}

_NUMBER_WORDS = {"one": 1, "three": 3, "five": 5, "ten": 10}
_HORIZON = r"(?P<h>1|3|5|10|one|three|five|ten)\s*-?\s*(?:y|yr|yrs|year|years)\b"
_HORIZON_PLAIN = r"(?:1|3|5|10|one|three|five|ten)\s*-?\s*(?:y|yr|yrs|year|years)\b"
_NUM = r"(?P<num>-?\d+(?:\.\d+)?)"
_BELOW = r"below|under|less than|lower than|at most|max(?:imum)?|up to|not more than|<=|<|≤"
_ABOVE = r"above|over|more than|greater than|higher than|at least|min(?:imum)?|>=|>|≥"
_THRESHOLD = re.compile(
    rf"(?P<cmp>{_BELOW}|{_ABOVE})\s*(?:of\s+)?(?:rs\.?\s*|₹\s*)?{_NUM}\s*(?P<unit>%|percent|k\s*crores?|k\s*cr|crores?|cr)?",
)

_FILLER = (
    "a an the and or with without of in on for to by is are be that which who have has "
    "having show me find list give get i want need looking look some any all funds fund "
    "mutual schemes scheme mf mfs plan plans please good great nice relatively fairly "
    "quite reasonably very really also only just but then than their its it them those "
    "these over last past period periods term long track record whose where can could "
    "would should let us sort sorted rank ranked order ordered first options option "
    "performing performers performer"
)
_STOP = frozenset(_FILLER.split())


def _horizon(text: str | None, default: int = 3) -> int:
    if not text:
        return default
    match = re.search(_HORIZON, text)
    if not match:
        return default
    h = match.group("h")
    return _NUMBER_WORDS.get(h, int(h) if h.isdigit() else default)


def _pct(value: float) -> str:
    return f"{value:g}%"


# --- reading ----------------------------------------------------------------------


class _Reader:
    """Consumes matched spans of the lower-cased request, so leftovers can be reported."""

    def __init__(self, text: str) -> None:
        self.text = " ".join(text.split())
        self.low = self.text.lower()
        self.used = [False] * len(self.low)
        self.clauses: list[tuple[int, Clause]] = []

    def free(self, start: int, end: int) -> bool:
        return not any(self.used[start:end])

    def take(self, start: int, end: int, clause: Clause) -> None:
        for i in range(start, end):
            self.used[i] = True
        self.clauses.append((start, clause))

    def find(self, pattern: str) -> Iterable[re.Match[str]]:
        for match in re.finditer(rf"(?<![\w-])(?:{pattern})(?![\w])", self.low):
            if self.free(*match.span()):
                yield match

    def window(self, start: int, end: int, before: int = 48, after: int = 40) -> tuple[str, str]:
        return self.low[max(0, start - before) : start], self.low[end : end + after]

    def leftovers(self) -> list[str]:
        """Runs of unconsumed words that are not filler."""
        found: list[str] = []
        run: list[str] = []
        for match in re.finditer(r"[^\s,;.]+", self.text):
            word = match.group().strip("\"'()").lower()
            consumed = any(self.used[match.start() : match.end()])
            if consumed or not word or word in _STOP or re.fullmatch(r"[\d.%-]+", word):
                if run:
                    found.append(" ".join(run))
                    run = []
                continue
            run.append(match.group().strip("\"'()"))
        if run:
            found.append(" ".join(run))
        return found


def _thresholds(r: _Reader) -> None:
    """A comparator and a number, read against the metric word nearest to it."""
    for match in list(_THRESHOLD.finditer(r.low)):
        if not r.free(*match.span()):
            continue
        before, after = r.window(*match.span())
        value = float(match.group("num"))
        unit = (match.group("unit") or "").replace(" ", "")
        below = re.fullmatch(_BELOW, match.group("cmp")) is not None
        op, word = ("<=", "at most") if below else (">=", "at least")
        if match.group("cmp") in ("below", "under", "less than", "lower than", "<"):
            op, word = "<", "below"
        elif match.group("cmp") in (
            "above",
            "over",
            "more than",
            "greater than",
            "higher than",
            ">",
        ):
            op, word = ">", "above"
        # The metric word closest to the number decides; words after it count when
        # nothing sits before it ("returns above 12% over 5 years").
        metric_end = match.end()
        near = re.findall(
            r"\b(?:ter|expense(?: ratio)?|cost|fees?|returns?|cagr|performance|gains?|"
            r"aum|assets|corpus|size|"
            r"sharpe|drawdowns?|falls?|volatility|risk)\b",
            before,
        )
        metric = near[-1] if near else None
        span_start = match.start()
        if metric is None:
            ahead = re.match(
                r"\s*(?:in\s+|of\s+)?"
                r"(ter|expense ratio|returns?|cagr|aum|sharpe|drawdown|volatility)",
                after,
            )
            metric = ahead.group(1) if ahead else None
            metric_end = match.end() + ahead.end() if ahead else match.end()
        else:
            span_start = match.start() - (len(before) - before.rfind(metric))
        if metric is None:
            continue
        leading = re.search(rf"{_HORIZON_PLAIN}\s*$", r.low[:span_start])
        if leading and r.free(leading.start(), span_start):
            span_start = leading.start()
        horizon_text = before[-30:] + " " + after[:30]
        end = metric_end
        trailing = re.match(
            rf"\s*(?:(?:over|in|for)\s+)?(?:the\s+)?(?:last\s+|past\s+)?{_HORIZON}",
            r.low[end : end + 40],
        )
        if trailing:
            end += trailing.end()
        phrase = r.text[span_start:end]
        clause = _threshold_clause(metric, op, word, value, unit, horizon_text, phrase)
        if clause is not None:
            r.take(span_start, end, clause)


def _threshold_clause(
    metric: str, op: str, word: str, value: float, unit: str, horizon_text: str, phrase: str
) -> Clause | None:
    if metric.startswith(("ter", "expense", "cost", "fee")):
        return Clause(
            phrase, f"TER {word} {_pct(value)}", ({"field": "ter", "op": op, "value": value / 100},)
        )
    if metric.startswith(("return", "cagr", "performance", "gain")):
        h = _horizon(horizon_text)
        field_id = {1: "ret_1y", 3: "cagr_3y", 5: "cagr_5y", 10: "cagr_10y"}[h]
        label = "1Y return" if h == 1 else f"{h}Y CAGR"
        return Clause(
            phrase,
            f"{label} {word} {_pct(value)}",
            ({"field": field_id, "op": op, "value": value / 100},),
        )
    if metric in ("aum", "assets", "corpus", "size"):
        crore = value * 1000 if unit.startswith("k") else value
        return Clause(
            phrase,
            f"AUM {word} ₹{crore:,.0f} crore",
            ({"field": "aum_cr", "op": op, "value": crore},),
        )
    if metric == "sharpe":
        return Clause(
            phrase,
            f"3Y Sharpe ratio {word} {value:g}",
            ({"field": "sharpe_3y", "op": op, "value": value},),
        )
    if metric.startswith(("drawdown", "fall")):
        # A fall "below 20%" is a drawdown no deeper than −20%.
        flipped = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}[op]
        return Clause(
            phrase,
            f"Worst 3Y fall {word} {_pct(value)}",
            ({"field": "mdd_3y", "op": flipped, "value": -abs(value) / 100},),
        )
    if metric in ("volatility", "risk"):
        return Clause(
            phrase,
            f"3Y volatility {word} {_pct(value)}",
            ({"field": "vol_3y", "op": op, "value": value / 100},),
        )
    return None


def _loose_horizon(r: _Reader) -> tuple[str, tuple[int, int]] | None:
    """A free "over the last 5 years" elsewhere in the request, for a clause that has none."""
    for match in r.find(
        rf"(?:over|in|for|across)\s+(?:the\s+)?(?:last\s+|past\s+)?{_HORIZON_PLAIN}"
    ):
        return match.group(), match.span()
    return None


def _concepts(r: _Reader) -> None:
    """Qualitative requests become category positions, which the screen states plainly."""
    for match in r.find(
        r"(?:(?:consistent|steady|reliable)(?:ly)?(?:\s+(?:good|strong|high|long-term))?"
        r"(?:\s+(?:performance|returns?|performers?|track record))?)|consistency"
    ):
        _, after = r.window(*match.span(), after=36)
        before, _ = r.window(*match.span(), before=24)
        end = match.end()
        trailing = re.match(
            rf"\s*(?:(?:over|in|for|of)\s+)?(?:the\s+)?(?:last\s+|past\s+)?{_HORIZON}(?:\s+(?:performance|returns?))?",
            after,
        )
        if trailing:
            end += trailing.end()
        h = _horizon(before[-14:] + " " + after[: (trailing.end() if trailing else 0)])
        start = match.start()
        leading = re.search(rf"{_HORIZON}\s*$", before)
        if leading:
            start -= len(before) - leading.start()
        conditions: tuple[Node, ...] = ({"field": "consistency_3y", "op": ">=", "value": 0.6},)
        text = (
            "Consistent: beat the category median rolling 3Y return in at least 60% of month-ends"
        )
        if h >= 5:
            conditions += ({"field": "cagr_5y_cat_pct", "op": ">=", "value": 50},)
            text += "; for five years, also a 5Y CAGR in the better half of its category"
        r.take(start, end, Clause(r.text[start:end], text, conditions))

    rules: tuple[tuple[str, str, Node, tuple[dict[str, str], ...]], ...] = (
        (
            r"(?:(?:very|the)\s+)?(?:lowest|minimal|smallest)\s+(?:drawdowns?|falls?|downside)",
            "Worst 3Y fall in the shallowest quarter of its category",
            {"field": "mdd_3y_cat_pct", "op": ">=", "value": 75},
            (),
        ),
        (
            r"(?:low(?:er)?|small(?:er)?|limited|shallow(?:er)?|less)\s+"
            r"(?:drawdowns?|falls?|downside)|downside protection",
            "Worst 3Y fall in the shallower half of its category",
            {"field": "mdd_3y_cat_pct", "op": ">=", "value": 50},
            (),
        ),
        (
            r"(?:low(?:er)?|less)\s+(?:volatility|volatile|swings)|calm(?:est)?|stable|less risky",
            "3Y volatility in the calmer half of its category",
            {"field": "vol_3y_cat_pct", "op": ">=", "value": 50},
            (),
        ),
        (
            r"(?:high(?:er)?|good|strong|best)\s+(?:sharpe|risk[- ]adjusted(?: returns?)?)",
            "3Y Sharpe ratio in the better half of its category",
            {"field": "sharpe_3y_cat_pct", "op": ">=", "value": 50},
            (),
        ),
        (
            r"cheapest|lowest (?:ter|cost|expense(?: ratio)?)",
            "TER in the cheaper half of its category, cheapest first",
            {"field": "ter_cat_pct", "op": ">=", "value": 50},
            ({"field": "ter", "dir": "asc"},),
        ),
        (
            r"low[- ]cost|cheap(?:er)?|inexpensive|low (?:ter|expense(?: ratio)?|fees?|costs?)",
            "TER in the cheaper half of its category",
            {"field": "ter_cat_pct", "op": ">=", "value": 50},
            (),
        ),
        (
            r"(?:high(?:ly)?|top)[- ](?:rated|scor(?:ed|ing))|high scores?",
            "Wickstreet score of 70 or more",
            {"field": "score", "op": ">=", "value": 70},
            (),
        ),
        (
            r"low[- ]risk|conservative",
            "SEBI riskometer at Moderate or lower",
            {"field": "riskometer_level", "op": "<=", "value": 3},
            (),
        ),
    )
    for pattern, text, condition, sort in rules:
        for match in r.find(pattern):
            r.take(
                *match.span(),
                Clause(r.text[match.start() : match.end()], text, (condition,), sort=sort),
            )

    for match in r.find(
        r"(?:beat(?:s|ing)?|outperform(?:s|ing|ed)?|ahead of)\s+"
        r"(?:the\s+|their\s+|its\s+)?(?:benchmarks?|index)"
    ):
        _, after = r.window(*match.span(), after=30)
        trailing = re.match(
            rf"\s*(?:(?:over|in|for)\s+)?(?:the\s+)?(?:last\s+|past\s+)?{_HORIZON}", after
        )
        end = match.end() + (trailing.end() if trailing else 0)
        h = _horizon(after[: trailing.end()] if trailing else None)
        h = h if h in (1, 3, 5, 10) else 3
        r.take(
            match.start(),
            end,
            Clause(
                r.text[match.start() : end],
                f"{h}Y return above its benchmark's, as AMFI publishes them",
                ({"field": f"excess_{h}y", "op": ">", "value": 0},),
            ),
        )

    for match in r.find(
        rf"(?:{_HORIZON_PLAIN}\s+)?"
        r"(?:(?:high(?:er)?|strong|good|best|top|above[- ]average)\s+"
        r"(?:returns?|performance|performers?|performing|cagr)"
        r"|best[- ]performing|top[- ]performing|outperform(?:ers?|ing)?(?: peers)?)"
    ):
        _, after = r.window(*match.span(), after=30)
        trailing = re.match(
            rf"\s*(?:(?:over|in|for)\s+)?(?:the\s+)?(?:last\s+|past\s+)?{_HORIZON}", after
        )
        end = match.end() + (trailing.end() if trailing else 0)
        phrase = r.text[match.start() : end]
        h = _horizon(phrase.lower(), default=0)
        if not h and (loose := _loose_horizon(r)):
            h = _horizon(loose[0])
            phrase += f" … {r.text[slice(*loose[1])]}"
            for i in range(*loose[1]):
                r.used[i] = True
        h = h or 3
        top = re.search(r"best|top", phrase.lower()) is not None
        field_id = {
            1: "ret_1y_cat_pct",
            3: "cagr_3y_cat_pct",
            5: "cagr_5y_cat_pct",
            10: "cagr_5y_cat_pct",
        }[h]
        h = 5 if h == 10 else h
        label = "1Y return" if h == 1 else f"{h}Y CAGR"
        share = "top quarter" if top else "better half"
        r.take(
            match.start(),
            end,
            Clause(
                phrase,
                f"{label} in the {share} of its category",
                ({"field": field_id, "op": ">=", "value": 75 if top else 50},),
                sort=({"field": field_id.removesuffix("_cat_pct"), "dir": "desc"},),
            ),
        )


def _categories(r: _Reader) -> None:
    for match in r.find(
        r"(?:nifty\s*(?:next\s*)?50|sensex|large\s*-?\s*cap|mid\s*-?\s*cap|small\s*-?\s*cap)\s+index(?:\s+funds?)?"
    ):
        r.take(
            *match.span(),
            Clause(
                r.text[match.start() : match.end()],
                "Category: Index funds. AMFI files every index fund in one category, so the index "
                "a fund tracks is not a screen field yet; check the fund names",
                ({"field": "category", "op": "in", "value": ["Other Scheme - Index Funds"]},),
                removes=frozenset({"asset_class"}),
            ),
        )
        return
    found: list[str] = []
    labels: list[str] = []
    phrases: list[tuple[int, int]] = []
    for pattern, categories, label in _CATEGORIES:
        for match in r.find(pattern):
            # "small" in "smaller falls" is never a category; patterns need the cap word.
            found.extend(c for c in categories if c not in found)
            labels.append(label)
            phrases.append(match.span())
            for i in range(*match.span()):
                r.used[i] = True
    if found:
        start = min(s for s, _ in phrases)
        r.clauses.append(
            (
                start,
                Clause(
                    ", ".join(r.text[s:e] for s, e in phrases),
                    "Category: " + ", ".join(labels),
                    ({"field": "category", "op": "in", "value": found},),
                    removes=frozenset({"asset_class"}),
                ),
            )
        )
        return
    for word, asset in _ASSET_CLASSES:
        for match in r.find(rf"{word}(?:\s+(?:funds?|schemes?|oriented))?"):
            r.take(
                *match.span(),
                Clause(
                    r.text[match.start() : match.end()],
                    f"Asset class: {asset}",
                    ({"field": "asset_class", "op": "in", "value": [asset]},),
                    removes=frozenset({"category"}),
                ),
            )
            return


def _houses(r: _Reader) -> None:
    names: dict[str, str] = dict(_HOUSE_BRANDS)
    for amc in AMCS:
        short = re.sub(r"\s+mutual fund$", "", amc.name, flags=re.I).lower()
        names.setdefault(short, amc.id)
        names.setdefault(amc.name.lower(), amc.id)
        names.setdefault(amc.master_label.lower(), amc.id)
    # A first word that names one house alone ("ICICI", "Kotak") is enough.
    firsts: dict[str, set[str]] = {}
    for name, amc_id in list(names.items()):
        firsts.setdefault(name.split()[0], set()).add(amc_id)
    for word, ids in firsts.items():
        if len(ids) == 1 and len(word) >= 4 and word not in _AMBIGUOUS_HOUSES | _COMMON_WORDS:
            names.setdefault(word, next(iter(ids)))
    by_id = {amc.id: amc for amc in AMCS}
    chosen: list[str] = []
    spans: list[tuple[int, int]] = []
    for name in sorted(names, key=len, reverse=True):
        suffix = r"\s+(?:mutual fund|mf|amc|asset management)" if name in _AMBIGUOUS_HOUSES else ""
        for match in r.find(re.escape(name) + suffix + r"(?:\s+(?:mutual fund|mf|amc))?"):
            house = by_id[names[name]].name
            if house not in chosen:
                chosen.append(house)
            spans.append(match.span())
            for i in range(*match.span()):
                r.used[i] = True
    if chosen:
        r.clauses.append(
            (
                min(s for s, _ in spans),
                Clause(
                    ", ".join(r.text[s:e] for s, e in spans),
                    "Fund house: " + ", ".join(chosen),
                    ({"field": "amc", "op": "in", "value": chosen},),
                ),
            )
        )


def _plans(r: _Reader) -> None:
    """Plans and options; "regular or direct" is one condition holding both."""
    for field_id, choices in (
        ("plan", ((r"direct(?:\s+plans?)?", "direct"), (r"regular(?:\s+plans?)?", "regular"))),
        (
            "option",
            (
                (r"growth(?:\s+option)?", "growth"),
                (r"idcw|dividend(?:\s+option|\s+payout)?", "idcw"),
            ),
        ),
    ):
        values: list[str] = []
        spans: list[tuple[int, int]] = []
        for pattern, value in choices:
            for match in r.find(pattern):
                if value not in values:
                    values.append(value)
                spans.append(match.span())
                for i in range(*match.span()):
                    r.used[i] = True
        if values:
            names = {"direct": "Direct", "regular": "Regular", "growth": "Growth", "idcw": "IDCW"}
            r.clauses.append(
                (
                    min(s for s, _ in spans),
                    Clause(
                        ", ".join(r.text[s:e] for s, e in sorted(spans)),
                        f"{' or '.join(names[v] for v in values)} "
                        f"{'plan' if field_id == 'plan' else 'option'}",
                        ({"field": field_id, "op": "in", "value": values},),
                    ),
                )
            )


_REMOVABLE: tuple[tuple[str, frozenset[str], str], ...] = (
    (r"ter|expense(?: ratio)?|cost(?: limit)?", frozenset({"ter", "ter_cat_pct"}), "TER"),
    (r"drawdowns?|falls?", frozenset({"mdd_3y", "mdd_3y_cat_pct"}), "drawdown"),
    (r"volatility", frozenset({"vol_3y", "vol_3y_cat_pct"}), "volatility"),
    (r"consistency", frozenset({"consistency_3y", "cagr_5y_cat_pct"}), "consistency"),
    (
        r"returns?|cagr|performance",
        frozenset(
            {
                "ret_1y",
                "cagr_3y",
                "cagr_5y",
                "cagr_10y",
                "ret_1y_cat_pct",
                "cagr_3y_cat_pct",
                "cagr_5y_cat_pct",
            }
        ),
        "return",
    ),
    (r"categor(?:y|ies)", frozenset({"category", "asset_class"}), "category"),
    (r"fund houses?|amcs?", frozenset({"amc"}), "fund house"),
    (r"aum|size", frozenset({"aum_cr"}), "AUM"),
    (r"sharpe", frozenset({"sharpe_3y", "sharpe_3y_cat_pct"}), "Sharpe"),
    (r"benchmark", frozenset({"excess_1y", "excess_3y", "excess_5y", "excess_10y"}), "benchmark"),
    (r"score|rating", frozenset({"score"}), "score"),
    (r"risk(?:ometer)?", frozenset({"riskometer_level"}), "riskometer"),
)


def _removals(r: _Reader) -> None:
    verbs = r"(?:remove|drop|without|ignore|forget|clear|no)\s+(?:the\s+|any\s+)?"
    for pattern, fields, label in _REMOVABLE:
        for match in r.find(rf"{verbs}(?:{pattern})(?:\s+(?:limit|filter|condition|rule|cap))?"):
            r.take(
                *match.span(),
                Clause(
                    r.text[match.start() : match.end()],
                    f"Removed the {label} condition",
                    removes=fields,
                ),
            )
    for match in r.find(r"(?:any|all)\s+(?:categor(?:y|ies)|fund houses?)"):
        fields = (
            frozenset({"amc"})
            if "house" in match.group()
            else frozenset({"category", "asset_class"})
        )
        r.take(
            *match.span(),
            Clause(
                r.text[match.start() : match.end()],
                f"Any {'fund house' if 'house' in match.group() else 'category'}",
                removes=fields,
            ),
        )


def _sorts(r: _Reader) -> None:
    for pattern, key, text in (
        (
            r"(?:sorted|ranked|ordered)\s+by\s+(?:lowest\s+)?(?:ter|cost|expense(?: ratio)?)"
            r"|lowest ter first",
            {"field": "ter", "dir": "asc"},
            "Lowest TER first",
        ),
        (
            r"(?:sorted|ranked|ordered)\s+by\s+(?:highest\s+)?(?:aum|size)"
            r"|largest(?: funds?)?(?: first)?|biggest",
            {"field": "aum_cr", "dir": "desc"},
            "Largest AUM first",
        ),
        (
            r"(?:sorted|ranked|ordered)\s+by\s+(?:lowest\s+)?volatility|least volatile",
            {"field": "vol_3y", "dir": "asc"},
            "Calmest first",
        ),
        (
            r"(?:sorted|ranked|ordered)\s+by\s+(?:highest\s+)?sharpe",
            {"field": "sharpe_3y", "dir": "desc"},
            "Highest Sharpe first",
        ),
        (
            r"(?:sorted|ranked|ordered)\s+by\s+(?:highest\s+)?(?:returns?|cagr)",
            {"field": "cagr_3y", "dir": "desc"},
            "Highest 3Y CAGR first",
        ),
    ):
        for match in r.find(pattern):
            r.take(*match.span(), Clause(r.text[match.start() : match.end()], text, sort=(key,)))
            break


# --- assembling --------------------------------------------------------------------

_DEFAULTS: tuple[tuple[Node, str], ...] = (
    ({"field": "status", "op": "in", "value": ["active"]}, "Active funds only"),
    (
        {"field": "plan", "op": "in", "value": ["direct"]},
        "Direct plan (say “regular” for regular plans)",
    ),
    (
        {"field": "option", "op": "in", "value": ["growth"]},
        "Growth option (say “IDCW” for payouts)",
    ),
)
_SHOWN_FOR = {
    "ter_cat_pct": "ter",
    "mdd_3y_cat_pct": "mdd_3y",
    "vol_3y_cat_pct": "vol_3y",
    "sharpe_3y_cat_pct": "sharpe_3y",
    "cagr_5y_cat_pct": "cagr_5y",
    "cagr_3y_cat_pct": "cagr_3y",
    "ret_1y_cat_pct": "ret_1y",
    "riskometer_level": "riskometer",
}


def _fields_of(nodes: Sequence[Node]) -> list[str]:
    out: list[str] = []
    for node in nodes:
        if "field" in node:
            out.append(node["field"])
        else:
            for children in node.values():
                out.extend(_fields_of(children))
    return out


def interpret(
    text: str,
    base: Sequence[Node] | None = None,
    base_sort: Sequence[dict[str, str]] | None = None,
) -> Interpretation:
    """Read ``text`` into a screen, refining ``base`` conditions when given."""
    r = _Reader(text)
    _removals(r)
    _sorts(r)
    _thresholds(r)
    _concepts(r)
    _categories(r)
    _houses(r)
    _plans(r)
    clauses = [c for _, c in sorted(r.clauses, key=lambda item: item[0])]
    not_understood = r.leftovers()

    refined = base is not None
    added = [cond for c in clauses for cond in c.conditions]
    replaced = {cond["field"] for cond in added} | {f for c in clauses for f in c.removes}
    kept = [node for node in (base or []) if not set(_fields_of([node])) & replaced]
    assumptions: list[str] = []
    defaults: list[Node] = []
    if not refined:
        present = set(_fields_of(added))
        for condition, note in _DEFAULTS:
            if condition["field"] not in present:
                defaults.append(condition)
                assumptions.append(note)
    conditions = [*defaults, *kept, *added]

    sort = (
        [key for c in clauses for key in c.sort][:1]
        or list(base_sort or [])
        or [{"field": "score", "dir": "desc"}]
    )
    columns: list[str] = []
    shown = [_SHOWN_FOR.get(f, f) for f in _fields_of(conditions)]
    # One named category needs no column; several, or none, do.
    if not any(n.get("field") == "category" and len(n["value"]) == 1 for n in conditions):
        columns.append("category")
    for column in [*shown, *_DEFAULT_COLUMNS]:
        if (
            column in ("status", "plan", "option", "category", "asset_class", "amc")
            or column in columns
        ):
            continue
        columns.append(column)
    columns = columns[:MAX_COLUMNS]
    if sort[0]["field"] not in columns and len(columns) < MAX_COLUMNS:
        columns.append(sort[0]["field"])

    tree = {"all": conditions}
    parse_filter(tree)
    parse_sort(sort)
    notes = []
    if not clauses and not refined:
        notes.append(
            "Nothing in the request matched a screen condition, so this is the default screen."
        )
    return Interpretation(tree, sort, columns, clauses, assumptions, not_understood, refined, notes)
