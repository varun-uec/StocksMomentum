"""The metric snapshot table: shared reference data, not tenant-owned (ADR-023 §2.6)."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Identity,
    Integer,
    LargeBinary,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY

from wickstreet.persistence.database import metadata

# One snapshot per (revision, method version) (MF-11). The revision is MF data's id;
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
    UniqueConstraint("revision_id", "method_version", name="uq_metric_snapshot_revision"),
)
