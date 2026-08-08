"""Unit tests for the RP-013 historical correction backfill pure logic."""

from __future__ import annotations

from datetime import date, timedelta

from scripts.rp013_historical_correction_backfill import (
    CORRECTION_WINDOWS,
    CorrectionWindow,
    is_contaminated,
    weekly_run_dates,
)

from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.persistence.models import (
    LegacyOHLCVDailyModel,
    OHLCVDailyModel,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import (
    IndicatorPipelineImpl,
    LegacyIndicatorPipelineImpl,
)


def _sec(symbol: str, isin: str | None, name: str = "X", active: bool = True) -> Security:
    return Security(symbol=Symbol(symbol), name=name, id=1, isin=isin, is_active=active)


def test_six_named_correction_windows_present() -> None:
    regimes = {w.regime for w in CORRECTION_WINDOWS}
    assert regimes == {
        "2000_dotcom",
        "2008_gfc",
        "2011",
        "2013_taper_tantrum",
        "2015_16",
        "2018_midcap_crash",
    }
    for w in CORRECTION_WINDOWS:
        assert w.start < w.end


def test_weekly_run_dates_snaps_into_window_and_is_weekly() -> None:
    window = CorrectionWindow("t", date(2008, 1, 8), date(2008, 3, 31))
    # A dense (daily) legacy calendar restricted to weekdays.
    cal = [
        date(2008, 1, 1) + timedelta(days=i)
        for i in range(120)
        if (date(2008, 1, 1) + timedelta(days=i)).weekday() < 5
    ]
    dates = weekly_run_dates(window, cal)
    assert dates == sorted(set(dates))  # ascending, de-duplicated
    assert all(window.start <= d <= window.end for d in dates)
    assert all(d in cal for d in dates)  # every run date is a real session
    # Roughly weekly cadence: consecutive gaps never exceed the 7-day step + a
    # weekend snap-back margin.
    for a, b in zip(dates, dates[1:], strict=False):
        assert (b - a).days <= 9


def test_weekly_run_dates_empty_when_no_sessions_in_window() -> None:
    window = CorrectionWindow("t", date(2008, 1, 8), date(2008, 3, 31))
    assert weekly_run_dates(window, []) == []
    assert weekly_run_dates(window, [date(2019, 1, 1)]) == []


def test_contamination_prefilter_excludes_single_null_isin_and_etf() -> None:
    assert is_contaminated(_sec("SINGLE", "INE000000000")) is True
    assert is_contaminated(_sec("RELIANCE", None)) is True  # NULL ISIN
    assert is_contaminated(_sec("NIFTYBEES", "INE111111111", name="Nifty ETF")) is True
    assert is_contaminated(_sec("SOMEETF", "INE222222222")) is True  # symbol match
    # A clean liquid name passes.
    assert is_contaminated(_sec("TATAMOTORS", "INE333333333", name="Tata Motors")) is False


def test_legacy_pipeline_only_differs_by_source_table() -> None:
    assert LegacyIndicatorPipelineImpl._model is LegacyOHLCVDailyModel
    assert IndicatorPipelineImpl._model is OHLCVDailyModel
    # Same formulas: the legacy subclass adds no overrides beyond the source.
    overridden = set(vars(LegacyIndicatorPipelineImpl)) - {
        "__doc__",
        "__module__",
        "__annotations__",
        "_model",
    }
    assert overridden == set()
