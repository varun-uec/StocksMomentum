"""Create the two MF database roles and the MF schema (ADR-023 U3).

``wickstreet_owner`` owns the schema and runs only the MF migrations.
``wickstreet_app`` is the runtime login: no superuser, no BYPASSRLS, and table
grants on the MF schema only, given table by table in the migrations. Momentum25's
role and tables are not touched.

Idempotent: a second run only re-applies passwords and attributes.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from wickstreet.persistence.database import APP_ROLE, OWNER_ROLE, SCHEMA

_ATTRIBUTES = "LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"


def _password(url: str, role: str) -> str:
    parsed = make_url(url)
    if parsed.username != role or not parsed.password:
        raise ValueError(f"Expected a database URL that logs in as {role!r} with a password.")
    return parsed.password


async def ensure_roles(admin_url: str, *, owner_url: str, app_url: str) -> None:
    """Create or update both roles, then the schema owned by ``wickstreet_owner``.

    ``admin_url`` must log in as a role that can create roles (in Compose, the
    PostgreSQL image's superuser). Passwords come from the owner and app URLs, so
    they are configured once.
    """
    passwords = {
        OWNER_ROLE: _password(owner_url, OWNER_ROLE),
        APP_ROLE: _password(app_url, APP_ROLE),
    }
    engine = create_async_engine(admin_url)
    try:
        async with engine.begin() as connection:
            for role, password in passwords.items():
                exists = await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role)"),
                    {"role": role},
                )
                verb = "ALTER" if exists else "CREATE"
                # DDL takes no bind parameters; the server quotes the identifier and literal.
                statement = await connection.scalar(
                    text(
                        f"SELECT format('{verb} ROLE %I WITH {_ATTRIBUTES} PASSWORD %L', "
                        "CAST(:r AS text), CAST(:p AS text))"
                    ),
                    {"r": role, "p": password},
                )
                # Raw, so a ":" in the password is never read as a bind parameter.
                await connection.exec_driver_sql(statement)
            await connection.execute(
                text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}" AUTHORIZATION "{OWNER_ROLE}"')
            )
            await connection.execute(text(f'ALTER SCHEMA "{SCHEMA}" OWNER TO "{OWNER_ROLE}"'))
            await connection.execute(text(f'GRANT USAGE ON SCHEMA "{SCHEMA}" TO "{APP_ROLE}"'))
    finally:
        await engine.dispose()
