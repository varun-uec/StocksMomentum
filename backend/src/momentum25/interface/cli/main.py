"""Command-line interface for imports, screening, strategies and backtests."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

import typer
from sqlalchemy.exc import SQLAlchemyError

from momentum25.application.use_cases.import_market_data import (
    ImportBenchmarkCsv,
    ImportEodCsv,
)
from momentum25.application.use_cases.walk_forward import format_walk_forward_report
from momentum25.domain.errors import Momentum25Error
from momentum25.domain.identity import IdentityLink
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.config.strategy_loader import load_strategies_dir
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlBenchmarkIndexRepository,
    SqlCorporateActionRepository,
    SqlOHLCVRepository,
    SqlSecurityRepository,
)
from momentum25.infrastructure.persistence.repositories.identity_links import (
    import_identity_links,
    read_import_file,
)
from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    SURVIVORSHIP_ELIGIBILITY_WARNING,
)
from momentum25.interface.walk_forward_wiring import build_walk_forward_runner

app = typer.Typer(help="Momentum25 India operational CLI.", no_args_is_help=True)


@app.command()
def engines() -> None:
    """List registered evaluation engines."""
    registry = register_builtin_engines()
    for engine_id in registry.all_ids():
        typer.echo(engine_id)


@app.command()
def strategies() -> None:
    """List strategy definitions discovered on disk with their config hash."""
    directory = Path(get_settings().strategy_dir)
    for strategy in load_strategies_dir(directory):
        typer.echo(f"{strategy.name} v{strategy.version}  {strategy.config_hash[:12]}")


@app.command(name="import-eod")
def import_eod(
    file: Path = typer.Argument(..., exists=True, readable=True, dir_okay=False),  # noqa: B008
    actions: Path | None = typer.Option(  # noqa: B008
        None, "--actions", exists=True, readable=True, dir_okay=False,
        help="Optional complete corporate-action history for the imported symbols.",
    ),
) -> None:
    """Import authorized daily bars from a normalized CSV file without network access."""
    try:
        result = asyncio.run(_import_eod(file, actions))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        f"Imported {result['bars']} bars for {result['symbols']} symbols; "
        f"saved {result['actions']} actions and adjusted {result['adjusted_bars']} bars."
    )


@app.command(name="import-benchmark")
def import_benchmark(
    file: Path = typer.Argument(..., exists=True, readable=True, dir_okay=False),  # noqa: B008
) -> None:
    """Import an authorized benchmark close series from a normalized CSV file."""
    try:
        result = asyncio.run(_import_benchmark(file))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Imported {result['bars']} bars for {result['index_code']}.")


@app.command()
def ingest() -> None:
    """Retired: use import-eod for authorized local data; exchange scraping is not implicit."""
    typer.echo(
        "`ingest` was retired. Use `momentum25 import-eod <bars.csv>` "
        "with an authorized data export.",
        err=True,
    )
    raise typer.Exit(2)


@app.command()
def screen(strategy: str = typer.Option("minervini_trend_template")) -> None:
    """Screen data already stored locally; this command never downloads market data."""
    from momentum25.app.services.screening_job import run_screening_pipeline

    try:
        run_id = asyncio.run(run_screening_pipeline(strategy, ingest_enabled=False))
    except (RuntimeError, ValueError, Momentum25Error) as exc:
        typer.echo(f"Screening failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Screening result run {run_id} for {strategy} using stored data.")


@app.command(name="walk-forward")
def walk_forward(
    start: str = typer.Argument(..., help="Backtest start date, YYYY-MM-DD"),
    end: str = typer.Argument(..., help="Backtest end date, YYYY-MM-DD"),
    initial_capital: str = typer.Option("1000000", help="Starting capital"),
) -> None:
    """Run a walk-forward backtest and print its report.

    Real ``SqlPriceHistoryProvider``/``SqlBenchmarkProvider`` data, real trading
    calendar. Universe/eligibility uses ``SqlSurvivorshipEligibilityProvider``:
    real survivorship (delisted names correctly drop out as of their delisting
    date), but Nifty 500 membership and T2T/ASM surveillance status are still
    stub -- a known, explicitly-labeled gap (see
    ``SURVIVORSHIP_ELIGIBILITY_WARNING``).
    """
    typer.echo(f"WARNING: {SURVIVORSHIP_ELIGIBILITY_WARNING}")
    try:
        asyncio.run(_run_walk_forward(start, end, initial_capital))
    except ValueError as exc:  # invalid range/capital, same rule as the API
        raise typer.BadParameter(str(exc)) from exc


async def _run_walk_forward(start: str, end: str, initial_capital: str) -> None:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    runner, manifest = await build_walk_forward_runner(start_date, end_date)
    result = runner.run(start_date, end_date, Decimal(initial_capital))
    typer.echo(format_walk_forward_report(result))
    typer.echo(f"Market data: {manifest.market_data_version} (revision {manifest.revision})")


@app.command(name="import-identity-links")
def import_identity_links_command(
    file: Path = typer.Argument(..., exists=True, readable=True, dir_okay=False),  # noqa: B008
) -> None:
    """Import verified renames from an owner-supplied CSV (R3-B-31).

    Each row needs authoritative exchange evidence: the source and a reference
    that names the document and carries its SHA-256. Nothing is inferred. The
    whole file is checked before anything is written.
    """
    try:
        links = read_import_file(file)
        count = asyncio.run(_import_identity_links(links))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Imported {count} identity links.")


async def _import_identity_links(links: list[IdentityLink]) -> int:
    database = get_database()
    async with database.session() as session:
        count = await import_identity_links(session, links)
        await session.commit()
        return count


async def _import_eod(file: Path, actions: Path | None) -> dict[str, int]:
    database = get_database()
    async with database.session() as session:
        importer = ImportEodCsv(
            SqlSecurityRepository(session),
            SqlOHLCVRepository(session),
            SqlCorporateActionRepository(session),
            get_nse_trading_calendar(),
        )
        return await importer.execute(file, actions)


async def _import_benchmark(file: Path) -> dict[str, int | str]:
    database = get_database()
    async with database.session() as session:
        return await ImportBenchmarkCsv(SqlBenchmarkIndexRepository(session)).execute(file)


def main() -> None:
    """Run the CLI; a database or network failure prints one line, not a traceback (R3-B-20)."""
    try:
        app()
    except (OSError, SQLAlchemyError) as exc:
        typer.echo(f"Failed: {type(exc).__name__}: {exc}", err=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
