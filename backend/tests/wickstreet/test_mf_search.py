"""Fund search terms and order (audit F-04): a beginner finds the plan they mean."""

from __future__ import annotations

from wickstreet.analytics.domain.search import Standing, ranked
from wickstreet.mf_data.domain.reads import FundRecord, compact, search_terms


def _fund(code: str, name: str, isin: str | None = None) -> FundRecord:
    return FundRecord(
        int(code), code, "PPFAS", name, name, None, None, None, None, isin, None, None
    )


def test_terms_ignore_case_spaces_and_punctuation() -> None:
    assert search_terms("SBI Small-cap ") == ["sbi", "small", "cap"]
    assert compact("Small Cap Fund - Direct") == "smallcapfunddirect"
    assert search_terms("  -- ") == []


def test_exact_code_then_phrase_then_direct_growth_then_oldest() -> None:
    funds = [
        _fund("1", "Parag Parikh Arbitrage Fund - Direct Growth"),
        _fund("2", "Parag Parikh Flexi Cap Fund - Direct Growth"),
        _fund("3", "Parag Parikh Flexi Cap Fund - Direct IDCW"),
        _fund("4", "Parag Parikh Flexi Cap Fund - Regular Growth"),
        _fund("5", "Parag Parikh Liquid Fund - Direct Growth"),
    ]
    standing = {
        "1": Standing(True, "2023-11-01"),
        "2": Standing(True, "2013-05-28"),
        "3": Standing(False, "2013-05-28"),
        "4": Standing(False, "2013-05-28"),
    }
    assert [f.amfi_code for f in ranked("parag", funds, standing)] == ["2", "1", "3", "4", "5"]
    assert ranked("4", funds, standing)[0].amfi_code == "4"


def test_current_plans_come_before_historical_phrase_matches() -> None:
    # Independent audit A-07: "nippon india" opened on eight closed IDCW series.
    funds = [
        _fund("144891", "NIPPON INDIA - INDIA OPPORTUNITIES FUND - SERIES A - DIRECT Plan - IDCW"),
        _fund("141898", "NIPPON INDIA CAPITAL BUILDER FUND IV - SERIES B - DIRECT Plan - IDCW"),
        _fund("118778", "Nippon India Small Cap Fund - Direct Plan Growth Plan - Growth Option"),
        _fund("118650", "Reliance Growth - Direct Growth"),
    ]
    standing = {"118778": Standing(True, "2013-01-01"), "118650": Standing(True, "2013-01-01")}
    order = [f.amfi_code for f in ranked("nippon india", funds, standing)]
    assert order[:2] == ["118778", "118650"]
    assert set(order[2:]) == {"144891", "141898"}
    # An exact code still opens a historical plan first.
    assert ranked("144891", funds, standing)[0].amfi_code == "144891"


def test_a_phrase_match_beats_an_older_fund() -> None:
    funds = [
        _fund("1", "HDFC Large & Mid Cap Fund - Direct"),
        _fund("2", "HDFC Mid Cap Fund - Direct"),
    ]
    standing = {"1": Standing(True, "2001-01-01"), "2": Standing(True, "2007-06-25")}
    assert [f.amfi_code for f in ranked("hdfc midcap", funds, standing)] == ["2", "1"]


def test_an_isin_matches_exactly_in_any_case() -> None:
    funds = [_fund("1", "A Fund"), _fund("2", "B Fund", isin="INF879O01027")]
    assert ranked("inf879o01027", funds, {})[0].amfi_code == "2"
