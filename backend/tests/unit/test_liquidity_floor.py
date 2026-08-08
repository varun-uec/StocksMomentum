"""Unit tests for the RP-012 Phase 2 liquidity-floor eligibility rule.

Pure, deterministic golden tests of the research-specified admission rule
(``avg_tottrdval50 >= ₹1cr``, ``close >= ₹20``, ``series == EQ``, ``>=252``
prior sessions). No I/O.
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.research.liquidity_floor import (
    MIN_AVG_TURNOVER,
    MIN_PRIOR_SESSIONS,
    REASON_BELOW_LIQUIDITY_FLOOR,
    REASON_CLOSE_BELOW_FLOOR,
    REASON_ELIGIBLE,
    REASON_INSUFFICIENT_HISTORY,
    REASON_INSUFFICIENT_TURNOVER_DATA,
    REASON_SERIES_NOT_EQ,
    TURNOVER_WINDOW,
    compute_avg_tottrdval50,
    evaluate_liquidity_eligibility,
)


def _turnovers(value: Decimal, n: int = TURNOVER_WINDOW) -> list[Decimal]:
    return [value] * n


class TestComputeAvgTurnover:
    def test_mean_of_full_window(self) -> None:
        assert compute_avg_tottrdval50(_turnovers(Decimal("2000000"))) == Decimal("2000000")

    def test_uses_only_last_window(self) -> None:
        series = [Decimal("0")] * 10 + _turnovers(Decimal("5000000"))
        assert compute_avg_tottrdval50(series) == Decimal("5000000")

    def test_none_when_too_few_sessions(self) -> None:
        assert compute_avg_tottrdval50(_turnovers(Decimal("1"), TURNOVER_WINDOW - 1)) is None

    def test_none_when_any_missing_turnover(self) -> None:
        series: list[Decimal | None] = _turnovers(Decimal("2000000"))  # type: ignore[assignment]
        series[-1] = None
        assert compute_avg_tottrdval50(series) is None


class TestEligibility:
    def _eval(self, **kw: object) -> object:
        defaults = {
            "close": Decimal("100"),
            "series": "EQ",
            "prior_session_count": MIN_PRIOR_SESSIONS,
            "trailing_turnovers": _turnovers(MIN_AVG_TURNOVER * 2),
        }
        defaults.update(kw)
        return evaluate_liquidity_eligibility(**defaults)  # type: ignore[arg-type]

    def test_all_conditions_met(self) -> None:
        decision = self._eval()
        assert decision.eligible is True
        assert decision.reason == REASON_ELIGIBLE
        assert decision.avg_tottrdval50 == MIN_AVG_TURNOVER * 2

    def test_non_eq_series_rejected(self) -> None:
        decision = self._eval(series="BE")
        assert decision.eligible is False
        assert decision.reason == REASON_SERIES_NOT_EQ

    def test_insufficient_history_rejected(self) -> None:
        decision = self._eval(prior_session_count=MIN_PRIOR_SESSIONS - 1)
        assert decision.eligible is False
        assert decision.reason == REASON_INSUFFICIENT_HISTORY

    def test_missing_turnover_data_rejected(self) -> None:
        turnovers: list[Decimal | None] = _turnovers(MIN_AVG_TURNOVER * 2)  # type: ignore[assignment]
        turnovers[0] = None
        decision = self._eval(trailing_turnovers=turnovers)
        assert decision.eligible is False
        assert decision.reason == REASON_INSUFFICIENT_TURNOVER_DATA

    def test_close_below_floor_rejected(self) -> None:
        decision = self._eval(close=Decimal("19.99"))
        assert decision.eligible is False
        assert decision.reason == REASON_CLOSE_BELOW_FLOOR

    def test_below_liquidity_floor_rejected(self) -> None:
        decision = self._eval(trailing_turnovers=_turnovers(Decimal("9999999")))
        assert decision.eligible is False
        assert decision.reason == REASON_BELOW_LIQUIDITY_FLOOR

    def test_exactly_at_floor_is_eligible(self) -> None:
        decision = self._eval(
            close=Decimal("20"), trailing_turnovers=_turnovers(MIN_AVG_TURNOVER)
        )
        assert decision.eligible is True
