"""Regression test: scorecard averages carry 4 decimal places, not 28.

The 2026-08-15 functional audit (F10) found ``/validation/scorecard`` serving
``avg_momentum_score`` as ``"32.80407073184481310143477908"``. Dividing two
``Decimal`` values keeps the full 28-digit context precision, and the
unmeasured-scorecard path returned that mean straight to the API without
quantizing it -- which reads as far more precision than a mean of a handful of
0-100 scores can carry.
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.research.validation_services import _screening_metrics

_QUANT_PLACES = 4


def _run(momentum: str, buy_setup: str) -> dict[str, object]:
    return {
        "total_evaluated": 3,
        "total_passed": 1,
        "avg_momentum_score": Decimal(momentum),
        "avg_buy_setup_score": Decimal(buy_setup),
    }


def _places(value: Decimal) -> int:
    return -value.as_tuple().exponent


def test_screening_metric_averages_are_quantized_to_four_places() -> None:
    # 100/3 and 10/3 do not terminate, so an unquantized mean runs to 28 digits.
    metrics = _screening_metrics(
        [_run("100", "10"), _run("100", "10"), _run("100", "10.00000001")], []
    )

    assert _places(metrics["avg_momentum_score"]) == _QUANT_PLACES
    assert _places(metrics["avg_buy_setup_score"]) == _QUANT_PLACES
    assert _places(metrics["avg_pass_rate"]) == _QUANT_PLACES


def test_no_runs_still_reports_zero_averages() -> None:
    """An empty sample keeps reporting 0, not None -- these are not return metrics."""
    metrics = _screening_metrics([], [])

    assert metrics["avg_momentum_score"] == Decimal("0")
    assert metrics["avg_buy_setup_score"] == Decimal("0")
    # Return-derived metrics stay None: unmeasured is not zero.
    assert metrics["false_positive_rate"] is None
    assert metrics["false_negative_rate"] is None
