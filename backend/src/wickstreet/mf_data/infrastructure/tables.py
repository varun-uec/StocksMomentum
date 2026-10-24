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
    # Null for an imported file, which Wickstreet did not retrieve (migration 0004).
    Column("retrieval_grant_id", BigInteger),
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

# A curated link between two plan-options (MF-3): written by the owner, never inferred.
plan_option_link = Table(
    "plan_option_link",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("from_plan_option_id", Integer, ForeignKey(plan_option.c.id), nullable=False),
    Column("to_plan_option_id", Integer, ForeignKey(plan_option.c.id), nullable=False),
    Column("kind", Text, nullable=False),
    Column("effective_date", Date, nullable=False),
    Column("evidence", Text, nullable=False),
    Column("recorded_by", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("kind IN ('merger', 'code_change', 'segregated_portfolio')", name="kind"),
    UniqueConstraint(
        "from_plan_option_id", "to_plan_option_id", "kind", name="uq_plan_option_link"
    ),
)

# Reference rates by series and effective date, revisioned like NAVs (doc 21 E2).
rate_point = Table(
    "rate_point",
    metadata,
    Column("series", Text, nullable=False),
    Column("effective_date", Date, nullable=False),
    # As published, % a year.
    Column("value", Numeric, nullable=False),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("superseded_revision", BigInteger),
    PrimaryKeyConstraint("series", "effective_date", "revision_id", name="pk_rate_point"),
    Index(
        "uq_rate_point_current",
        "series",
        "effective_date",
        unique=True,
        postgresql_where=text("superseded_revision IS NULL"),
    ),
)

# AMFI schemes (``SD_Id``) as AMFI lists them (doc 21 E1). Names are as last listed.
scheme = Table(
    "scheme",
    metadata,
    Column("sd_id", Integer, primary_key=True, autoincrement=False),
    Column("mf_id", Integer, nullable=False),
    Column("name", Text, nullable=False),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
)

# The ISIN join from plan-options to schemes, from each scheme's SSD (doc 21 E1).
scheme_isin = Table(
    "scheme_isin",
    metadata,
    Column("isin", Text, primary_key=True),
    Column("sd_id", Integer, ForeignKey(scheme.c.sd_id), nullable=False),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
)

# One filed value of one scheme, in force from ``as_of``; revisioned like NAVs.
scheme_fact = Table(
    "scheme_fact",
    metadata,
    Column("sd_id", Integer, ForeignKey(scheme.c.sd_id), nullable=False),
    Column("name", Text, nullable=False),
    # '' for the whole scheme, else 'regular' or 'direct'.
    Column("plan", Text, nullable=False),
    Column("as_of", Date, nullable=False),
    Column("num", Numeric),
    Column("txt", Text),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("superseded_revision", BigInteger),
    PrimaryKeyConstraint("sd_id", "name", "plan", "as_of", "revision_id", name="pk_scheme_fact"),
    CheckConstraint("plan IN ('', 'regular', 'direct')", name="plan"),
    Index(
        "uq_scheme_fact_current",
        "sd_id",
        "name",
        "plan",
        "as_of",
        unique=True,
        postgresql_where=text("superseded_revision IS NULL"),
    ),
)

# One filed line of a scheme's monthly portfolio (doc 21 E4). A re-filed portfolio
# supersedes every current line of that scheme and date.
holding = Table(
    "holding",
    metadata,
    Column("sd_id", Integer, ForeignKey(scheme.c.sd_id), nullable=False),
    Column("as_of", Date, nullable=False),
    Column("seq", Integer, nullable=False),
    Column("name", Text, nullable=False),
    Column("isin", Text),
    Column("industry", Text),
    Column("section", Text, nullable=False),
    Column("asset", Text, nullable=False),
    Column("quantity", Numeric),
    Column("value", Numeric),
    # A fraction of net assets.
    Column("weight", Numeric, nullable=False),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("superseded_revision", BigInteger),
    PrimaryKeyConstraint("sd_id", "as_of", "seq", "revision_id", name="pk_holding"),
    CheckConstraint("asset IN ('equity', 'debt', 'cash', 'derivative', 'other')", name="asset"),
    Index(
        "uq_holding_current",
        "sd_id",
        "as_of",
        "seq",
        unique=True,
        postgresql_where=text("superseded_revision IS NULL"),
    ),
    Index("ix_holding_isin", "isin"),
)

# AMFI's half-yearly market-cap list: each company's class for a period (doc 21 E4).
security_class = Table(
    "security_class",
    metadata,
    Column("isin", Text, nullable=False),
    Column("as_of", Date, nullable=False),
    Column("name", Text, nullable=False),
    Column("market_cap_cr", Numeric),
    Column("cap_class", Text, nullable=False),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("superseded_revision", BigInteger),
    PrimaryKeyConstraint("isin", "as_of", "revision_id", name="pk_security_class"),
    Index(
        "uq_security_class_current",
        "isin",
        "as_of",
        unique=True,
        postgresql_where=text("superseded_revision IS NULL"),
    ),
)

# IDCW payouts per plan-option (doc 21 E5): ₹ per unit on the record date.
distribution = Table(
    "distribution",
    metadata,
    Column("plan_option_id", Integer, ForeignKey(plan_option.c.id), nullable=False),
    Column("record_date", Date, nullable=False),
    Column("per_unit", Numeric, nullable=False),
    Column("revision_id", BigInteger, ForeignKey(revision.c.id), nullable=False),
    Column("superseded_revision", BigInteger),
    PrimaryKeyConstraint("plan_option_id", "record_date", "revision_id", name="pk_distribution"),
    Index(
        "uq_distribution_current",
        "plan_option_id",
        "record_date",
        unique=True,
        postgresql_where=text("superseded_revision IS NULL"),
    ),
)
