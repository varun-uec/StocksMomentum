"""ADR-009: the domain never reads the clock; the report date is an input."""

from datetime import date

from momentum25.domain.research.validation_services import compute_validation_summary


def test_report_date_is_the_one_given() -> None:
    report = compute_validation_summary([], date(2026, 10, 21))
    assert report.generated_at == "2026-10-21"
