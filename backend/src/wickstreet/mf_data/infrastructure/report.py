"""Coverage, gap and reconciliation report over the published MF data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from platform_common.database import Database

_QUERIES = {
    "publication": "SELECT revision_id, published_at FROM wickstreet.publication",
    "plan_options": "SELECT count(*) FROM wickstreet.plan_option",
    "plan_options_with_nav": "SELECT count(DISTINCT plan_option_id) FROM wickstreet.nav",
    "master_plan_options": (
        "SELECT count(DISTINCT plan_option_id) FROM wickstreet.plan_option_master "
        "WHERE superseded_revision IS NULL"
    ),
    "nav_rows_current": "SELECT count(*) FROM wickstreet.nav WHERE superseded_revision IS NULL",
    "nav_rows_superseded": (
        "SELECT count(*) FROM wickstreet.nav WHERE superseded_revision IS NOT NULL"
    ),
    "nav_dates": (
        "SELECT min(nav_date), max(nav_date), count(DISTINCT nav_date) FROM wickstreet.nav "
        "WHERE superseded_revision IS NULL"
    ),
    "revisions": "SELECT count(*) FROM wickstreet.revision",
    "anomalies": (
        "SELECT anomaly, count(*) FROM wickstreet.nav WHERE superseded_revision IS NULL "
        "AND anomaly IS NOT NULL GROUP BY anomaly ORDER BY anomaly"
    ),
    "runs": (
        "SELECT dataset, status, count(*) FROM wickstreet.ingestion_run "
        "GROUP BY dataset, status ORDER BY dataset, status"
    ),
    "unavailable_ranges": (
        "SELECT period_start, period_end FROM wickstreet.ingestion_run "
        "WHERE status = 'unavailable' ORDER BY period_start"
    ),
    "failed_runs": (
        "SELECT dataset, period_start, error FROM wickstreet.ingestion_run "
        "WHERE status IN ('failed', 'denied') ORDER BY period_start"
    ),
    "nav_rows_by_source": (
        "SELECT r.source, count(*), min(n.nav_date), max(n.nav_date) FROM wickstreet.nav n "
        "JOIN wickstreet.revision v ON v.id = n.revision_id "
        "JOIN wickstreet.ingestion_run r ON r.id = v.run_id "
        "WHERE n.superseded_revision IS NULL GROUP BY r.source ORDER BY r.source"
    ),
    "nav_rows_by_year": (
        "SELECT extract(year FROM nav_date)::int, count(*), count(DISTINCT plan_option_id) "
        "FROM wickstreet.nav WHERE superseded_revision IS NULL GROUP BY 1 ORDER BY 1"
    ),
    # Archive values that differ from a stored AMFI value; AMFI's value is kept.
    "archive_conflicts": (
        "SELECT source, coalesce(sum(conflicts), 0) FROM wickstreet.ingestion_run "
        "WHERE conflicts IS NOT NULL GROUP BY source ORDER BY source"
    ),
    # Dates between the first and last stored NAV that no settled run covers.
    "missing_dates": (
        "WITH span AS (SELECT min(nav_date) AS a, max(nav_date) AS b FROM wickstreet.nav) "
        "SELECT d::date FROM span, generate_series(span.a, span.b, interval '1 day') d "
        "WHERE NOT EXISTS (SELECT 1 FROM wickstreet.ingestion_run r WHERE r.dataset = 'nav-v1' "
        "AND r.period_start <= d::date AND r.period_end >= d::date "
        "AND r.status IN ('published', 'unchanged')) ORDER BY 1"
    ),
    # Monday-to-Friday dates with no NAV at all: market holidays, or a gap.
    "weekdays_without_nav": (
        "WITH span AS (SELECT min(nav_date) AS a, max(nav_date) AS b FROM wickstreet.nav), "
        "dates AS (SELECT DISTINCT nav_date FROM wickstreet.nav "
        "WHERE superseded_revision IS NULL) "
        "SELECT d::date FROM span, generate_series(span.a, span.b, interval '1 day') d "
        "WHERE extract(isodow FROM d) < 6 AND d::date NOT IN (SELECT nav_date FROM dates) "
        "ORDER BY 1"
    ),
    "rows_per_date": (
        "SELECT min(c), percentile_disc(0.5) WITHIN GROUP (ORDER BY c), max(c) FROM "
        "(SELECT nav_date, count(*) c FROM wickstreet.nav WHERE superseded_revision IS NULL "
        "GROUP BY nav_date) t"
    ),
    "weekday_low_dates": (
        "WITH d AS (SELECT nav_date, count(*) c FROM wickstreet.nav "
        "WHERE superseded_revision IS NULL GROUP BY nav_date), "
        "m AS (SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY c) med FROM d "
        "WHERE extract(isodow FROM nav_date) < 6) "
        "SELECT nav_date, c FROM d, m WHERE extract(isodow FROM nav_date) < 6 "
        "AND c < 0.5 * m.med ORDER BY nav_date"
    ),
    # A plan-option with NAVs that stop more than 10 days before the latest date.
    "stale_plan_options": (
        "WITH last AS (SELECT plan_option_id, max(nav_date) AS d FROM wickstreet.nav "
        "WHERE superseded_revision IS NULL GROUP BY plan_option_id) "
        "SELECT count(*) FROM last WHERE d < (SELECT max(nav_date) FROM wickstreet.nav) - 10"
    ),
    "nav_codes_not_in_master": (
        "SELECT count(DISTINCT n.plan_option_id) FROM wickstreet.nav n WHERE NOT EXISTS "
        "(SELECT 1 FROM wickstreet.plan_option_master m WHERE m.plan_option_id = n.plan_option_id)"
    ),
    "master_codes_without_nav": (
        "SELECT count(DISTINCT m.plan_option_id) FROM wickstreet.plan_option_master m "
        "WHERE NOT EXISTS (SELECT 1 FROM wickstreet.nav n "
        "WHERE n.plan_option_id = m.plan_option_id)"
    ),
    "isins_on_several_codes": (
        "SELECT count(*) FROM (SELECT isin_growth FROM wickstreet.plan_option_listing "
        "WHERE superseded_revision IS NULL AND isin_growth IS NOT NULL "
        "GROUP BY isin_growth HAVING count(DISTINCT plan_option_id) > 1) t"
    ),
    "plan_options_with_name_changes": (
        "SELECT count(*) FROM (SELECT plan_option_id FROM wickstreet.plan_option_listing "
        "WHERE superseded_revision IS NULL GROUP BY plan_option_id HAVING count(*) > 1) t"
    ),
}


async def coverage_report(database: Database) -> dict[str, Any]:
    """Run every report query and return plain values."""
    report: dict[str, Any] = {}
    async with database.engine.connect() as connection:
        for name, sql in _QUERIES.items():
            rows = [tuple(row) for row in (await connection.execute(text(sql))).all()]
            if len(rows) == 1 and len(rows[0]) == 1:
                report[name] = rows[0][0]
            elif name in ("missing_dates", "weekdays_without_nav"):
                report[name] = [row[0] for row in rows]
            else:
                report[name] = rows
    return report
