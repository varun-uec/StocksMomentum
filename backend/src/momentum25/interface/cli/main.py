"""Command-line interface.

Provides operational commands. ``ingest`` and ``screen`` are wired to their use cases
in milestones M1/M4; this phase exposes the command surface and the strategy/registry
utilities that already work.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

import typer

from momentum25.application.use_cases.walk_forward import format_walk_forward_report
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.config.strategy_loader import load_strategies_dir
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


@app.command()
def ingest(date: str = typer.Argument(None, help="YYYY-MM-DD; default latest")) -> None:
    """Ingest market data for a date (implemented in milestone M1)."""
    typer.echo("`ingest` is implemented in milestone M1.")
    raise typer.Exit(0)


@app.command()
def screen(strategy: str = typer.Option("minervini_trend_template")) -> None:
    """Run a screening pipeline for a strategy (implemented in milestone M4)."""
    typer.echo("`screen` is implemented in milestone M4.")
    raise typer.Exit(0)


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
    runner = await build_walk_forward_runner(start_date, end_date)
    result = runner.run(start_date, end_date, Decimal(initial_capital))
    typer.echo(format_walk_forward_report(result))


if __name__ == "__main__":
    app()
