"""MF reference-data tables: shared, not tenant-owned (ADR-023 §2.6).

Fact rows are append-only. A row is visible at revision R when ``revision_id <= R``
and ``superseded_revision`` is null or greater than R (ADR-017 MF-5).
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)

from wickstreet.persistence.database import metadata

# One source, dataset and period: the durable job record (MF-10).
ingestion_run = Table(
    "ingestion_run",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("source", Text, nullable=False),
    Column("dataset", Text, nullable=False),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("status", Text, nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    # Hash of the content last published or found unchanged (MF-7).
    Column("raw_sha256", Text),
    Column("revision_id", BigInteger),
    Column("rows", Integer),
    Column("inserted", Integer),
    Column("superseded", Integer),
    Column("anomalies", Integer),
    # Archive values that differ from a stored value they did not replace.
    Column("conflicts", Integer),
    Column("error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    UniqueConstraint(
        "source", "dataset", "period_start", "period_end", name="uq_ingestion_run_period"
    ),
)

# One published content of one run, with its provenance (MF-9).
revision = Table(
    "revision",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("run_id", BigInteger, ForeignKey(ingestion_run.c.id), nullable=False),
    Column("contract", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("raw_sha256", Text, nullable=False),
    Column("raw_path", Text, nullable=False),
    Column("adapter_version", Text, nullable=False),
    # Ids in the data-rights register; no foreign key across contexts (A3 §7.1).
    Column("retrieval_grant_id", BigInteger, nullable=False),
    Column("storage_grant_id", BigInteger, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

# The single pointer readers read at (MF-6).
publication = Table(
    "publication",
    metadata,
    Column("id", SmallInteger, primary_key=True),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("id = 1", name="single_row"),
)

# The AMFI scheme code is the source key; the surrogate id is the store's key (MF-2).
plan_option = Table(
    "plan_option",
    metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("amfi_code", Text, nullable=False, unique=True),
    Column("first_revision", BigInteger, ForeignKey(revision.c.id), nullable=False),
)

nav = Table(
    "nav",
    metadata,
    Column("plan_option_id", Integer, ForeignKey(plan_option.c.id), nullable=False),
    Column("nav_date", Date, nullable=False),
    # As filed: no scale, so 10.0000 stays 10.0000. Null when the source gave no number.
    Column("nav", Numeric),
    Column("anomaly", Text),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("superseded_revision", BigInteger),
    PrimaryKeyConstraint("plan_option_id", "nav_date", "revision_id", name="pk_nav"),
    # Current rows: one per plan-option and date; also serves date-range reads.
    Index(
        "uq_nav_current",
        "nav_date",
        "plan_option_id",
        unique=True,
        postgresql_where=text("superseded_revision IS NULL"),
    ),
)

# Attributes seen in NAV files, effective from the first date they were seen (MF-4).
plan_option_listing = Table(
    "plan_option_listing",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("plan_option_id", Integer, ForeignKey(plan_option.c.id), nullable=False),
    Column("effective_from", Date, nullable=False),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("superseded_revision", BigInteger),
    Column("amc", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("nav_name", Text, nullable=False),
    Column("plan", Text),
    Column("option", Text),
    Column("isin_growth", Text),
    Column("isin_reinvest", Text),
    Index("ix_plan_option_listing_plan_option_id", "plan_option_id", "effective_from"),
)

# Attributes from the scheme master, effective from the snapshot date (MF-4).
plan_option_master = Table(
    "plan_option_master",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("plan_option_id", Integer, ForeignKey(plan_option.c.id), nullable=False),
    Column("effective_from", Date, nullable=False),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("superseded_revision", BigInteger),
    Column("amc", Text, nullable=False),
    Column("scheme_name", Text, nullable=False),
    Column("scheme_type", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("nav_name", Text, nullable=False),
    Column("min_amount", Text),
    Column("launch_date", Date),
    Column("closure_date", Date),
    Column("isin_growth", Text),
    Column("isin_reinvest", Text),
    Index("ix_plan_option_master_plan_option_id", "plan_option_id", "effective_from"),
)
