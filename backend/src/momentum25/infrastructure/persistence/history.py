"""System-versioned input tables (ADR-014 §7).

Every table an evaluation reads keeps its past: a trigger stamps each inserted
or changed row with a ``revision_id`` from one global sequence and the time it
was stored, and copies the version it replaces into ``<table>_history``. An
upsert that changes nothing records nothing. The current tables keep their
shape and their writers, so the live pipeline does not change.

A row version is visible at revision R when its ``revision_id`` <= R and it was
not yet superseded at R: a current row, or a history row whose
``superseded_revision`` > R. Rows stored before versioning have revision 0.

``provenance`` says how far a row can be trusted as point in time:
``recorded`` (stored within days of its session or ex-date: live ingestion),
``published`` (taken later from an official archive) or ``reconstructed``
(rebuilt later; the original information state is unknown).

The DDL here is version 1. The migration ``0016_history_tables`` calls it, and
the test schema (``create_all``) runs it through the metadata event below. A
later change must add a version 2, never edit version 1.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    event,
    text,
)
from sqlalchemy.engine import Connection

SEQUENCE = "data_revision_seq"
FUNCTION = "versioned_row_v1"
PROVENANCE = ("recorded", "published", "reconstructed")
# Calendar days within which a stored row still counts as recorded live:
# a weekend and a holiday after the session.
RECORDED_WITHIN_DAYS = 4

# table -> (the date its row describes, its default provenance)
VERSIONED: dict[str, tuple[str | None, str]] = {
    "securities": (None, "published"),
    "ohlcv_daily": ("date", "published"),
    "corporate_actions": ("ex_date", "published"),
    "benchmark_index_daily": ("date", "published"),
    "historical_universe": ("as_of_date", "reconstructed"),
}

# Compared without these. The first four change on every write. ``adj_factor``
# and ``adj_close`` are derived: every new corporate action rewrites them on all
# earlier bars, and the point-in-time port recomputes factors from the actions
# themselves, so versioning them would only copy every bar per action.
_VOLATILE = ("revision_id", "recorded_at", "provenance", "updated_at", "adj_factor", "adj_close")


def history_name(table: str) -> str:
    """Return the history table's name."""
    return f"{table}_history"


def history_table(current: Table, metadata: MetaData) -> Table:
    """Declare ``<table>_history``: every column of ``current``, then the supersession.

    No keys or constraints: it holds many versions of one key.
    """
    return Table(
        history_name(current.name),
        metadata,
        *(Column(c.name, c.type, nullable=True) for c in current.columns),
        Column("superseded_revision", BigInteger, nullable=False, index=True),
        Column("superseded_at", DateTime(timezone=True), nullable=False),
        Column("operation", String(1), nullable=False),
    )


def ddl_v1() -> list[str]:
    """The sequence, the trigger function and one trigger per versioned table."""
    volatile = " - ".join(f"'{c}'" for c in _VOLATILE)
    statements = [
        f"CREATE SEQUENCE IF NOT EXISTS {SEQUENCE}",
        f"""
CREATE OR REPLACE FUNCTION {FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    rev bigint;
    described date;
BEGIN
    IF TG_OP = 'UPDATE'
       AND (to_jsonb(NEW) - {volatile}) = (to_jsonb(OLD) - {volatile}) THEN
        NEW.revision_id := OLD.revision_id;
        NEW.recorded_at := OLD.recorded_at;
        NEW.provenance := OLD.provenance;
        RETURN NEW;
    END IF;
    rev := nextval('{SEQUENCE}');
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        EXECUTE format('INSERT INTO %I SELECT ($1).*, $2, now(), $3', TG_TABLE_NAME || '_history')
            USING OLD, rev, left(TG_OP, 1);
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    NEW.revision_id := rev;
    NEW.recorded_at := now();
    IF TG_ARGV[0] <> '' AND NEW.provenance <> 'reconstructed' THEN
        described := (to_jsonb(NEW) ->> TG_ARGV[0])::date;
        NEW.provenance := CASE
            WHEN (now() AT TIME ZONE 'Asia/Kolkata')::date - described <= {RECORDED_WITHIN_DAYS}
                THEN 'recorded'
            ELSE 'published'
        END;
    END IF;
    RETURN NEW;
END
$$""",
    ]
    for table, (described, _) in VERSIONED.items():
        statements.append(f"DROP TRIGGER IF EXISTS {table}_versioned ON {table}")
        statements.append(
            f"CREATE TRIGGER {table}_versioned BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {FUNCTION}('{described or ''}')"
        )
    return statements


# Tables whose rows never change once written (ADR-014 §4, §6).
APPEND_ONLY = ("strategy_families",)


def append_only_ddl(tables: tuple[str, ...]) -> list[str]:
    """A trigger that refuses every update and delete on ``tables``.

    ``TRUNCATE`` fires no row trigger, so the test schema can still be reset.
    """
    statements = [
        """
CREATE OR REPLACE FUNCTION refuse_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only: % refused', TG_TABLE_NAME, TG_OP;
END
$$"""
    ]
    for table in tables:
        statements.append(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
        statements.append(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION refuse_change()"
        )
    return statements


def evaluation_guard_ddl() -> list[str]:
    """Keep a finished evaluation as it is, and every hold-out evaluation (ADR-014 §6).

    A queued, running or failed evaluation may still change (progress, retry).
    A completed one may not. An Out-of-Sample Evaluation is never deleted: it
    records that the family spent its hold-out.
    """
    return [
        """
CREATE OR REPLACE FUNCTION guard_evaluation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'completed' THEN
        RAISE EXCEPTION 'strategy_evaluations: a completed evaluation is final (% refused)', TG_OP;
    END IF;
    IF TG_OP = 'DELETE' AND OLD.result_class = 'out_of_sample' THEN
        RAISE EXCEPTION 'strategy_evaluations: an Out-of-Sample Evaluation is never deleted';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$$""",
        "DROP TRIGGER IF EXISTS strategy_evaluations_guard ON strategy_evaluations",
        "CREATE TRIGGER strategy_evaluations_guard BEFORE UPDATE OR DELETE ON "
        "strategy_evaluations FOR EACH ROW EXECUTE FUNCTION guard_evaluation()",
    ]


def install_on_create(metadata: MetaData) -> None:
    """Run the trigger DDL whenever ``metadata.create_all`` builds the schema (tests)."""

    @event.listens_for(metadata, "after_create")
    def _install(target: MetaData, connection: Connection, **_: object) -> None:
        for statement in ddl_v1() + append_only_ddl(APPEND_ONLY) + evaluation_guard_ddl():
            connection.execute(text(statement))
