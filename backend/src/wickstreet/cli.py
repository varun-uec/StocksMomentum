"""Wickstreet 2.0 operational CLI."""

from __future__ import annotations

import asyncio

import typer

from wickstreet.config import get_settings
from wickstreet.persistence.roles import ensure_roles

app = typer.Typer(help="Wickstreet 2.0 operational CLI.", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """Keep subcommand names even while there is only one."""


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


def main() -> None:
    """Console-script entry point."""
    app()
