"""The metric snapshot table: shared reference data, not tenant-owned (ADR-023 §2.6)."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Identity,
    Index,
    Integer,
    LargeBinary,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY

from wickstreet.persistence.database import metadata

# One serving snapshot per (revision, method version) (MF-11); a retired one stays
# for audit and is never served. The revision is MF data's id;
# no foreign key across contexts (A3 §7.1).
metric_snapshot = Table(
    "metric_snapshot",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("revision_id", BigInteger, nullable=False),
    Column("method_version", Integer, nullable=False),
    Column("as_of", Date, nullable=False),
    Column("funds", Integer, nullable=False),
    Column("sources", ARRAY(Text), nullable=False),
    # The derived_metrics grants the computation ran under.
    Column("grant_ids", ARRAY(BigInteger), nullable=False),
    # SHA-256 of the JSON body; the payload is that body, gzipped.
    Column("payload_sha256", Text, nullable=False),
    Column("payload", LargeBinary, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("retired_at", DateTime(timezone=True)),
    Column("retired_by", Text),
    Column("retired_reason", Text),
    CheckConstraint(
        "(retired_at IS NULL) = (retired_by IS NULL) "
        "AND (retired_at IS NULL) = (retired_reason IS NULL)",
        name="retired",
    ),
    Index(
        "uq_metric_snapshot_revision",
        "revision_id",
        "method_version",
        unique=True,
        postgresql_where=text("retired_at IS NULL"),
    ),
)
