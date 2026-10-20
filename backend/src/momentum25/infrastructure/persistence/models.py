"""SQLAlchemy ORM models mirroring ``IMPLEMENTATION_SPEC.md`` §4.

These models are the persistence representation only; they never cross into the
domain layer (repositories map between models and domain objects). Numeric columns
use ``Numeric`` to preserve the determinism contract (ADR-009).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from momentum25.infrastructure.persistence.history import (
    ALL_VERSIONED,
    PROVENANCE,
    history_table,
    install_on_create,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _table_name(cls: object) -> str:
    return str(vars(cls)["__tablename__"])


class Versioned:
    """Columns the versioning trigger maintains (ADR-014 §7; see ``history.py``).

    Writers never set them: the trigger stamps every insert and real change.
    """

    revision_id: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @declared_attr
    def provenance(cls) -> Mapped[str]:  # noqa: N805 - SQLAlchemy passes the class
        """How far the row can be trusted as point in time; set per table."""
        default = ALL_VERSIONED[_table_name(cls)][1]
        return mapped_column(String, nullable=False, server_default=default)

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:  # noqa: N805
        """The table's own arguments plus the provenance check."""
        allowed = ", ".join(f"'{p}'" for p in PROVENANCE)
        return (
            *getattr(cls, "_extra_table_args", ()),
            Index(f"ix_{_table_name(cls)}_revision_id", "revision_id"),
            CheckConstraint(f"provenance IN ({allowed})", name=f"ck_{_table_name(cls)}_provenance"),
        )


class SecurityModel(Versioned, Base):
    """Instrument master row."""

    __tablename__ = "securities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sector: Mapped[str | None] = mapped_column(String)
    industry: Mapped[str | None] = mapped_column(String)
    exchange: Mapped[str] = mapped_column(String, nullable=False, default="NSE")
    listing_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delisting_date: Mapped[date | None] = mapped_column(Date)
    last_trade_date: Mapped[date | None] = mapped_column(Date)
    termination_reason: Mapped[str | None] = mapped_column(Text)
    tenant_id: Mapped[int | None] = mapped_column(BigInteger)  # SaaS extension point
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OHLCVDailyModel(Versioned, Base):
    """Daily price bar (optionally a TimescaleDB hypertable)."""

    __tablename__ = "ohlcv_daily"

    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True
    )
    # Indexed on its own: the primary key leads with ``security_id``, so a
    # date-range scan across the whole universe (market breadth) cannot use it.
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    adj_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    turnover_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))


class CorporateActionModel(Versioned, Base):
    """Corporate action (split/bonus/dividend) for price adjustment."""

    __tablename__ = "corporate_actions"
    _extra_table_args = (UniqueConstraint("security_id", "ex_date", "type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("securities.id"), index=True)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class HistoricalUniverseModel(Versioned, Base):
    """Point-in-time historical universe eligibility (RP-012 §2).

    Immutable audit record: one row per ``(as_of_date, security_id)`` recording
    whether the security was eligible for the reconstructed historical universe
    on that date and why. Rows are insert-only; production enforces
    no-update/no-delete at the database layer (migration ``0004`` trigger).
    """

    __tablename__ = "historical_universe"

    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


class SecurityIdentityLinkModel(Versioned, Base):
    """A verified rename (R3-B-31, IMPLEMENTATION_SPEC §4).

    Written only by ``momentum25 identity-links import`` from an owner-supplied
    file with authoritative exchange evidence. Nothing infers a row.
    """

    __tablename__ = "security_identity_links"
    _extra_table_args = (
        CheckConstraint("predecessor_id <> successor_id", name="ck_identity_links_distinct"),
        CheckConstraint("ratio > 0", name="ck_identity_links_ratio"),
    )

    predecessor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True
    )
    successor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), nullable=False, unique=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    ratio: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False, server_default="1")
    evidence_source: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)


class LegacyOHLCVDailyModel(Base):
    """Legacy-archive EOD bars for the RP-012 overlap window (Phase 2 §1).

    A dedicated staging table so legacy-sourced bars for 2019-09-30→~2024-07-05
    can coexist with the current provider's live ``ohlcv_daily`` rows for the
    same ``(security_id, date)`` — Gate 4a reconciliation requires *both* sources
    to be present and comparable, and production's live dashboard must never be
    corrupted by legacy-sourced duplicates. OHLC/volume are raw prints;
    ``adj_factor``/``adj_close`` carry the same backward adjustment the live
    table uses (``adj_close == close * adj_factor``).
    """

    __tablename__ = "legacy_ohlcv_daily"

    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    adj_factor: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=1, server_default="1"
    )
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    turnover_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))


class BSELegacyOHLCVDailyModel(Base):
    """Legacy BSE EOD bars for the RP-014 pre-UDiFF range (2006-03-01 → 2023-12-29).

    A dedicated staging table mirroring ``legacy_ohlcv_daily`` so BSE-sourced
    bars can never be confused with the NSE-anchored legacy surface the
    historical screening pipeline reads. OHLC/volume are raw prints;
    ``adj_factor``/``adj_close`` carry the same backward adjustment the live
    table uses (``adj_close == close * adj_factor``).
    """

    __tablename__ = "bse_legacy_ohlcv_daily"

    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    adj_factor: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=1, server_default="1"
    )
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    turnover_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))


class BSEScripJunctionModel(Base):
    """Learned BSE ``SC_CODE`` → ISIN identity junction (RP-014).

    Insert-only: one row per BSE scrip code, recording the ISIN/name BSE's
    UDiFF bhavcopy reported for it on the first observed session (first
    observation wins). BSE ``SC_CODE`` values are stable across the exchange's
    history, so this junction lets 2006–2023 legacy bars — which carry no ISIN
    — resolve to the canonical table by ISIN.
    """

    __tablename__ = "bse_scrip_junction"

    sc_code: Mapped[str] = mapped_column(String, primary_key=True)
    isin: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)


class CorporateActionInferenceLogModel(Base):
    """PREVCLOSE-inferred corporate-action factors (RP-012 condition C1).

    Insert-only audit log. An inferred factor is *never* applied to price
    history — it is recorded here (with ``flagged`` set when it exceeds the
    tolerance band) for later reconciliation against NSE's corporate-actions API.
    """

    __tablename__ = "corporate_action_inference_log"
    __table_args__ = (UniqueConstraint("security_id", "session_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("securities.id"))
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    prev_close_reported: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    prior_session_close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    inferred_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SurvivorshipGapEventModel(Base):
    """Detected trading-gap / survivorship events (RP-012 condition C2).

    Insert-only. Records that a security stopped appearing for longer than the
    gap threshold; does not by itself classify a delisting.
    """

    __tablename__ = "survivorship_gap_event"
    __table_args__ = (UniqueConstraint("security_id", "last_seen_date", "detected_on_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("securities.id"))
    last_seen_date: Mapped[date] = mapped_column(Date, nullable=False)
    detected_on_date: Mapped[date] = mapped_column(Date, nullable=False)
    gap_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ForwardReturnModel(Base):
    """A security's realized forward return/drawdown/volatility for one run/horizon.

    Append-only (ADR-006): a row is written only once market data reaches its
    exit session, and is never revised afterward. ``horizon_basis`` says what
    the horizon counts (R3-B-32): ``sessions`` (NSE sessions, engine v2) or
    ``own_bars`` (the security's own bars, rows written before it).
    """

    __tablename__ = "forward_returns"
    __table_args__ = (
        CheckConstraint(
            "horizon_basis IN ('sessions', 'own_bars')", name="ck_forward_returns_horizon_basis"
        ),
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("screening_runs.id"), primary_key=True
    )
    # Indexed on its own: the primary key leads with ``run_id``, so a
    # per-security join across runs cannot use it.
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True, index=True
    )
    horizon_days: Mapped[int] = mapped_column(Integer, primary_key=True)
    horizon_basis: Mapped[str] = mapped_column(String, primary_key=True)
    exit_date: Mapped[date | None] = mapped_column(Date)
    exit_stale_sessions: Mapped[int | None] = mapped_column(Integer)
    forward_return: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    forward_max_drawdown: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    forward_volatility: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    forward_mfe: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    forward_mae: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    benchmark_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    excess_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BenchmarkIndexDailyModel(Versioned, Base):
    """Daily benchmark index close used for relative strength."""

    __tablename__ = "benchmark_index_daily"

    index_code: Mapped[str] = mapped_column(String, primary_key=True)
    # Indexed on its own: the primary key leads with ``index_code``.
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class StrategyModel(Base):
    """A versioned, hashed strategy definition."""

    __tablename__ = "strategies"
    __table_args__ = (
        UniqueConstraint("name", "version"),
        CheckConstraint("(kind = 'user') = (family_id IS NOT NULL)", name="ck_strategies_family"),
        # A user config is addressed by its hash, so each hash names one row.
        Index(
            "uq_strategies_user_config_hash",
            "config_hash",
            unique=True,
            postgresql_where=text("kind = 'user'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, server_default="production")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    config_hash: Mapped[str] = mapped_column(String, nullable=False)
    # User strategies only (ADR-014 §3–4): the family, and the config it came from.
    family_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("strategy_families.id"), index=True
    )
    parent_config_hash: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StrategyFamilyModel(Base):
    """A hypothesis and its root config, fixed at creation (ADR-014 §4)."""

    __tablename__ = "strategy_families"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    # Lower-cased, single-spaced: two families cannot state the same hypothesis.
    hypothesis_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    root_config_hash: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(BigInteger)  # SaaS extension point (ADR-010)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScreeningRunModel(Base):
    """A screening run (one immutable snapshot once COMPLETED)."""

    __tablename__ = "screening_runs"
    __table_args__ = (
        UniqueConstraint("strategy_id", "run_date", "data_version", "config_hash"),
        # ``status`` is only ever written from ``RunStatus``, but nothing in the
        # database enforced that, so a bad writer could persist a value the
        # application cannot map back to the enum.
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_screening_runs_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("strategies.id"))
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_version: Mapped[str] = mapped_column(String, nullable=False)
    config_hash: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class UniverseMembershipModel(Base):
    """Per-run universe eligibility record."""

    __tablename__ = "universe_membership"

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("screening_runs.id"), primary_key=True
    )
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True
    )
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


class ScreeningResultModel(Base):
    """Per-run, per-security scores and rank (append-only)."""

    __tablename__ = "screening_results"

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("screening_runs.id"), primary_key=True
    )
    # Indexed on its own: the primary key leads with ``run_id``, so a
    # per-security scan across runs (score history) cannot use it.
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True, index=True
    )
    rank: Mapped[int | None] = mapped_column(Integer, index=True)
    momentum_score: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    buy_setup_score: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    hard_filters_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RuleResultModel(Base):
    """Per-run, per-security, per-rule explainability record (append-only)."""

    __tablename__ = "rule_results"

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("screening_runs.id"), primary_key=True
    )
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True
    )
    rule_id: Mapped[str] = mapped_column(String, primary_key=True)
    engine_id: Mapped[str] = mapped_column(String, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    operator: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    contribution: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class WatchlistItemModel(Base):
    """A security on the single global watchlist (Phase 6.9)."""

    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), nullable=False, unique=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserDocumentModel(Base):
    """A saved workspace or drawing set, versioned for optimistic concurrency (ADR-013 §5)."""

    __tablename__ = "user_documents"
    __table_args__ = (CheckConstraint("revision >= 1", name="ck_user_documents_revision"),)

    kind: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(BigInteger)  # SaaS extension point (ADR-010)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AlertModel(Base):
    """A daily alert on one value of a symbol's chart series (FR-22, M15)."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'triggered')", name="ck_alerts_status"),
        CheckConstraint(
            "(status = 'active') = (triggered_on IS NULL)", name="ck_alerts_triggered_on"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    interval: Mapped[str] = mapped_column(String, nullable=False)
    condition: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    drawing: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")
    armed_after: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active", index=True)
    triggered_on: Mapped[date | None] = mapped_column(Date)
    trigger_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    data_version: Mapped[str | None] = mapped_column(String)
    seen: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    tenant_id: Mapped[int | None] = mapped_column(BigInteger)  # SaaS extension point (ADR-010)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DataManifestModel(Base):
    """A stored data-version manifest (ADR-014 §7); the primary key is its hash."""

    __tablename__ = "data_manifests"

    data_version: Mapped[str] = mapped_column(String(12), primary_key=True)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StrategyEvaluationModel(Base):
    """One evaluation of a user strategy in one result class (ADR-014 §5–7).

    The research namespace: evaluations never write screening runs.
    """

    __tablename__ = "strategy_evaluations"
    __table_args__ = (
        CheckConstraint(
            "result_class IN ('screening', 'in_sample', 'out_of_sample')",
            name="ck_strategy_evaluations_class",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_strategy_evaluations_status",
        ),
        # One Out-of-Sample Evaluation per family per hold-out window.
        Index(
            "uq_strategy_evaluations_holdout",
            "family_id",
            "window_start",
            "window_end",
            unique=True,
            postgresql_where=text("result_class = 'out_of_sample'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strategy_families.id"), nullable=False, index=True
    )
    config_hash: Mapped[str] = mapped_column(String, nullable=False)
    result_class: Mapped[str] = mapped_column(String, nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    data_version: Mapped[str] = mapped_column(
        String(12), ForeignKey("data_manifests.data_version"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="queued")
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    tenant_id: Mapped[int | None] = mapped_column(BigInteger)  # SaaS extension point (ADR-010)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# History tables of the versioned inputs, and their triggers in test schemas.
HISTORY_TABLES = {
    name: history_table(Base.metadata.tables[name], Base.metadata) for name in ALL_VERSIONED
}
install_on_create(Base.metadata)
