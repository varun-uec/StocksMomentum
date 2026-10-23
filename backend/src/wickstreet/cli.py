"""Wickstreet 2.0 operational CLI."""

from __future__ import annotations

import asyncio
import json
import resource
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import date, datetime, timedelta

import typer

from platform_common.database import Database
from wickstreet.config import WickstreetSettings, get_settings
from wickstreet.data_rights.domain.rights import Use
from wickstreet.data_rights.infrastructure.register import (
    list_grants,
    record_grants,
    revoke_grants,
)
from wickstreet.mf_data.application.ingest import Outcome, Summary
from wickstreet.mf_data.domain.model import AMFI
from wickstreet.mf_data.infrastructure.reader import SqlMfReader, record_link
from wickstreet.mf_data.infrastructure.report import coverage_report
from wickstreet.mf_data.infrastructure.scheduler import IST
from wickstreet.persistence.roles import ensure_roles
from wickstreet.wiring import Ingestion, build_analytics, build_ingestion

app = typer.Typer(help="Wickstreet 2.0 operational CLI.", no_args_is_help=True)
rights_app = typer.Typer(help="Data-rights register; writes use the owner login.")
mf_app = typer.Typer(help="MF data acquisition and verification.")
link_app = typer.Typer(help="Curated plan-option links (MF-3); writes use the owner login.")
app.add_typer(rights_app, name="rights")
app.add_typer(mf_app, name="mf")
mf_app.add_typer(link_app, name="link")


@app.callback()
def _root() -> None:
    """Keep subcommand names."""


@app.command(name="db-roles")
def db_roles(
    admin_url: str = typer.Option(
        ...,
        envvar="WICKSTREET_ADMIN_DATABASE_URL",
        help="A login that can create roles; used for this command only.",
    ),
) -> None:
    """Create or update the MF database roles and schema (ADR-023 U3)."""
    settings = get_settings()
    asyncio.run(
        ensure_roles(
            admin_url,
            owner_url=settings.migration_database_url,
            app_url=settings.database_url,
        )
    )
    typer.echo("wickstreet roles and schema are ready")


def _with_database[T](url: str, work: Callable[[Database], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(url)
        try:
            return await work(database)
        finally:
            await database.dispose()

    return asyncio.run(run())


@rights_app.command("grant")
def rights_grant(
    source: str,
    use: list[Use] = typer.Option(..., "--use", help="Repeat for each use."),  # noqa: B008
    basis: str = typer.Option(..., help="Why the use is allowed, in words."),
    granted_by: str = typer.Option(..., "--by", help="Who records the grant."),
) -> None:
    """Record grants for the configured mode."""
    settings = get_settings()
    created = _with_database(
        settings.migration_database_url,
        lambda db: record_grants(
            db, source=source, mode=settings.mode, uses=use, basis=basis, granted_by=granted_by
        ),
    )
    typer.echo(f"recorded {len(created)} new grant(s): {created}")


@rights_app.command("revoke")
def rights_revoke(
    source: str,
    use: list[Use] = typer.Option(..., "--use", help="Repeat for each use."),  # noqa: B008
) -> None:
    """Revoke grants for the configured mode."""
    settings = get_settings()
    count = _with_database(
        settings.migration_database_url,
        lambda db: revoke_grants(db, source=source, mode=settings.mode, uses=use),
    )
    typer.echo(f"revoked {count} grant(s)")


@rights_app.command("list")
def rights_list() -> None:
    """List every grant."""
    for row in _with_database(get_settings().database_url, list_grants):
        typer.echo(" | ".join(str(value) for value in row))


def _today() -> date:
    return datetime.now(IST).date()


def _print(outcome: Outcome) -> None:
    detail = (
        f"rows={outcome.rows} inserted={outcome.inserted} superseded={outcome.superseded} "
        f"anomalies={outcome.anomalies} conflicts={outcome.conflicts} "
        f"revision={outcome.revision}"
    )
    error = f" {outcome.error}" if outcome.error else ""
    typer.echo(f"{outcome.period} {outcome.status:<11} {detail}{error}")


def _summary(summary: Summary) -> None:
    typer.echo(
        json.dumps(
            {
                "statuses": dict(summary.statuses),
                "rows": summary.rows,
                "inserted": summary.inserted,
                "superseded": summary.superseded,
                "anomalies": summary.anomalies,
                "conflicts": summary.conflicts,
                "first_served": str(summary.first_served),
                "failures": [f"{o.period}: {o.error}" for o in summary.failures],
            },
            indent=2,
        )
    )


def _run[T](settings: WickstreetSettings, work: Callable[[Ingestion], Awaitable[T]]) -> T:
    async def run(database: Database) -> T:
        ingestion = build_ingestion(settings, database)
        try:
            return await work(ingestion)
        finally:
            await ingestion.aclose()

    return _with_database(settings.database_url, run)


def _ingest(settings: WickstreetSettings, work: Callable[[Ingestion], Awaitable[Summary]]) -> None:
    summary = _run(settings, work)
    _summary(summary)
    # Every publish path brings the snapshot up to the new pointer (MF-11).
    if summary.statuses["published"]:
        _compute(settings)


def _compute(settings: WickstreetSettings) -> None:
    started = time.perf_counter()
    outcome = _with_database(
        settings.database_url, lambda db: build_analytics(settings, db).compute.execute()
    )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is bytes on macOS and kilobytes on Linux.
    peak_mb = peak / 2**20 if sys.platform == "darwin" else peak / 2**10
    typer.echo(
        json.dumps(
            {
                "snapshot": outcome.status,
                "revision": outcome.revision,
                "snapshot_id": outcome.snapshot_id,
                "funds": outcome.funds,
                "seconds": round(time.perf_counter() - started, 1),
                "peak_rss_mb": round(peak_mb),
            }
        )
    )


def _history_start(settings: WickstreetSettings, today: date) -> date:
    # A week's margin, so a 10-year trailing return has its start NAV (ADR-023 U4).
    return today.replace(year=today.year - settings.history_years) - timedelta(days=7)


@mf_app.command("backfill")
def mf_backfill(
    start: str | None = typer.Option(None, help="First date, YYYY-MM-DD; default 10 years ago."),
    end: str | None = typer.Option(None, help="Last date, YYYY-MM-DD; default yesterday."),
) -> None:
    """Acquire the scheme master and NAV history; resumable (settled dates are skipped)."""
    settings = get_settings()
    today = _today()
    first = date.fromisoformat(start) if start else _history_start(settings, today)
    last = date.fromisoformat(end) if end else today - timedelta(days=1)
    _ingest(settings, lambda i: i.backfill.execute(first, last, today, _print))


@mf_app.command("archive")
def mf_archive(
    start: str | None = typer.Option(None, help="First date, YYYY-MM-DD; default 10 years ago."),
    end: str | None = typer.Option(None, help="Last date, YYYY-MM-DD; default yesterday."),
    refetch: bool = typer.Option(False, help="Re-publish months already settled."),
) -> None:
    """Import the TigZig archive: the record before AMFI's first served date, a fill after it.

    Run `mf backfill` first; the first date AMFI serves is the cutoff.
    """
    settings = get_settings()
    today = _today()
    first = date.fromisoformat(start) if start else _history_start(settings, today)
    last = date.fromisoformat(end) if end else today - timedelta(days=1)

    async def work(ingestion: Ingestion) -> Summary:
        cutoff = await ingestion.store.first_nav_day(AMFI)
        if cutoff is None:
            raise typer.BadParameter("No AMFI NAV date is stored yet: run `mf backfill` first.")
        typer.echo(f"cutoff (first AMFI date): {cutoff}")
        return await ingestion.archive.execute(
            first, last, cutoff, today, _print, refetch=refetch
        )

    _ingest(settings, work)


@mf_app.command("reparse")
def mf_reparse(
    start: str | None = typer.Option(None, help="First date, YYYY-MM-DD; default AMFI's first."),
    end: str | None = typer.Option(None, help="Last date, YYYY-MM-DD; default yesterday."),
) -> None:
    """Re-derive published AMFI dates from their kept raw files after a parser fix."""
    settings = get_settings()
    last = date.fromisoformat(end) if end else _today() - timedelta(days=1)

    async def work(ingestion: Ingestion) -> Summary:
        first = date.fromisoformat(start) if start else await ingestion.store.first_nav_day(AMFI)
        if first is None:
            raise typer.BadParameter("No AMFI NAV date is stored yet.")
        return await ingestion.reparse.execute(first, last, _print)

    _ingest(settings, work)


@mf_app.command("crosscheck")
def mf_crosscheck(
    sample: int = typer.Option(50, help="How many codes to compare."),
    start: str | None = typer.Option(None, help="First date, YYYY-MM-DD; default 10 years ago."),
    end: str | None = typer.Option(None, help="Last date, YYYY-MM-DD; default yesterday."),
    code: list[str] = typer.Option([], "--code", help="Compare these codes instead."),  # noqa: B008
) -> None:
    """Compare stored NAVs with MFAPI for a fixed sample of codes; publishes nothing."""
    settings = get_settings()
    today = _today()
    first = date.fromisoformat(start) if start else _history_start(settings, today)
    last = date.fromisoformat(end) if end else today - timedelta(days=1)

    async def work(ingestion: Ingestion) -> list[dict[str, object]]:
        codes = code or await ingestion.store.sample_codes(sample, first, last)
        results = await ingestion.crosscheck.execute(codes, first, last, today)
        return [asdict(result) for result in results]

    results = _run(settings, work)
    totals = {
        key: sum(int(str(r[key])) for r in results)
        for key in ("matched", "differing", "reference_only", "stored_only")
    }
    typer.echo(json.dumps({"codes": len(results), **totals, "by_code": results}, indent=2))


@mf_app.command("refresh")
def mf_refresh(
    today: str | None = typer.Option(None, help="Run as of this date, YYYY-MM-DD."),
) -> None:
    """Run the daily refresh now: the master, then the look-back window."""
    settings = get_settings()
    as_of = date.fromisoformat(today) if today else _today()
    _ingest(settings, lambda i: i.refresh.execute(as_of, _print))


@mf_app.command("report")
def mf_report() -> None:
    """Print coverage, gaps, anomalies and reconciliation as JSON."""
    report = _with_database(get_settings().database_url, coverage_report)
    typer.echo(json.dumps(report, indent=2, default=str))


@mf_app.command("metrics")
def mf_metrics() -> None:
    """Compute the metric snapshot of the published revision; a no-op when it exists."""
    _compute(get_settings())


@link_app.command("add")
def link_add(
    from_code: str = typer.Argument(..., help="AMFI code the link starts from."),
    to_code: str = typer.Argument(..., help="AMFI code the link goes to."),
    kind: str = typer.Option(..., help="merger, code_change or segregated_portfolio."),
    effective: str = typer.Option(..., help="Effective date, YYYY-MM-DD."),
    evidence: str = typer.Option(..., help="Where the link is documented."),
    recorded_by: str = typer.Option(..., "--by", help="Who records the link."),
) -> None:
    """Record a curated link between two plan-options; never inferred."""
    recorded = _with_database(
        get_settings().migration_database_url,
        lambda db: record_link(
            db,
            from_code=from_code,
            to_code=to_code,
            kind=kind,
            effective_date=date.fromisoformat(effective),
            evidence=evidence,
            recorded_by=recorded_by,
        ),
    )
    typer.echo("recorded" if recorded else "not recorded: unknown code or already recorded")


@link_app.command("list")
def link_list(code: str) -> None:
    """List the links from or to one plan-option."""
    for link in _with_database(get_settings().database_url, lambda db: SqlMfReader(db).links(code)):
        typer.echo(json.dumps(asdict(link), default=str))


def main() -> None:
    """Console-script entry point."""
    app()
