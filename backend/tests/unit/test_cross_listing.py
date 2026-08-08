"""ISIN-based cross-listing reconciliation (Phase 5.1)."""

from __future__ import annotations

from datetime import date

from momentum25.domain.ports.market_data import RawInstrument
from momentum25.domain.research.cross_listing import reconcile_cross_listings
from momentum25.domain.value_objects.types import Exchange


def nse(symbol: str, isin: str | None, name: str = "N", listed: date | None = None):
    return RawInstrument(symbol=symbol, name=name, isin=isin, series="EQ", listing_date=listed)


def bse(symbol: str, isin: str | None, name: str = "B", series: str = "A"):
    return RawInstrument(symbol=symbol, name=name, isin=isin, series=series)


def test_same_company_on_both_exchanges_is_one_record_marked_both() -> None:
    result = reconcile_cross_listings(
        [nse("RELIANCE", "INE002A01018", name="Reliance Industries Ltd")],
        [bse("RELIANCE", "ine002a01018", name="RELIANCE INDUSTRIES LTD.")],
    )

    assert len(result.instruments) == 1
    only = result.instruments[0]
    assert only.exchange is Exchange.BOTH
    # NSE stays canonical: the platform's existing identity is untouched.
    assert only.name == "Reliance Industries Ltd"
    assert result.cross_listed == 1
    assert result.nse_only == 0


def test_different_ticker_same_isin_still_reconciles_to_one_record() -> None:
    result = reconcile_cross_listings(
        [nse("MOTHERSON", "INE775A01035")],
        [bse("MOTHERSUMI", "INE775A01035")],
    )

    assert [i.symbol for i in result.instruments] == ["MOTHERSON"]
    assert result.instruments[0].exchange is Exchange.BOTH
    assert result.bse_only_withheld == ()


def test_same_ticker_different_isin_is_not_treated_as_the_same_company() -> None:
    result = reconcile_cross_listings(
        [nse("ACME", "INE111A01011")],
        [bse("ACME", "INE999Z01019")],
    )

    assert [(i.symbol, i.exchange) for i in result.instruments] == [("ACME", Exchange.NSE)]
    assert result.cross_listed == 0
    assert result.bse_only_withheld == ("ACME",)


def test_bse_only_names_are_withheld_from_the_universe_by_default() -> None:
    result = reconcile_cross_listings(
        [nse("INFY", "INE009A01021")], [bse("BSEONLY", "INE777A01010")]
    )

    assert [i.symbol for i in result.instruments] == ["INFY"]
    assert result.bse_only_admitted == 0
    assert result.bse_only_withheld == ("BSEONLY",)


def test_bse_only_names_enter_only_via_an_explicit_group_whitelist() -> None:
    result = reconcile_cross_listings(
        [nse("INFY", "INE009A01021")],
        [bse("BSEONLY", "INE777A01010", series="A"), bse("ETFUNIT", "INF200KA1FS1", series="B")],
        admit_bse_only_series=frozenset({"A"}),
    )

    assert [i.symbol for i in result.instruments] == ["BSEONLY", "INFY"]
    assert result.instruments[0].exchange is Exchange.BSE
    assert result.bse_only_admitted == 1
    assert result.bse_only_withheld == ("ETFUNIT",)


def test_whitelisted_bse_ticker_colliding_with_an_nse_ticker_is_excluded_and_disclosed() -> None:
    result = reconcile_cross_listings(
        [nse("ACME", "INE111A01011")],
        [bse("ACME", "INE999Z01019", series="A")],
        admit_bse_only_series=frozenset({"A"}),
    )

    assert [i.symbol for i in result.instruments] == ["ACME"]
    assert result.instruments[0].isin == "INE111A01011"
    assert result.symbol_collisions == ("ACME",)


def test_missing_isins_never_merge_two_companies() -> None:
    result = reconcile_cross_listings(
        [nse("AAA", None), nse("BBB", None)],
        [bse("CCC", None, series="A"), bse("DDD", "", series="A")],
        admit_bse_only_series=frozenset({"A"}),
    )

    assert [i.symbol for i in result.instruments] == ["AAA", "BBB", "CCC", "DDD"]
    assert result.cross_listed == 0


def test_result_is_deterministic_regardless_of_provider_ordering() -> None:
    nse_master = [nse("ZZZ", "INE003A01010"), nse("AAA", "INE001A01010")]
    bse_master = [bse("AAA", "INE001A01010"), bse("QQQ", "INE009A01021", series="A")]
    whitelist = frozenset({"A"})

    first = reconcile_cross_listings(nse_master, bse_master, admit_bse_only_series=whitelist)
    second = reconcile_cross_listings(
        list(reversed(nse_master)), list(reversed(bse_master)), admit_bse_only_series=whitelist
    )

    assert first == second
    assert [i.symbol for i in first.instruments] == ["AAA", "QQQ", "ZZZ"]
