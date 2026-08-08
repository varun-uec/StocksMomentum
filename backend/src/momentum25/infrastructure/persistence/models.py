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
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class SecurityModel(Base):
    """Instrument master row."""

    __tablename__ = "securities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(String)
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


class OHLCVDailyModel(Base):
    """Daily price bar (optionally a TimescaleDB hypertable)."""

    __tablename__ = "ohlcv_daily"

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
    adj_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    turnover_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))


class CorporateActionModel(Base):
    """Corporate action (split/bonus/dividend) for price adjustment."""

    __tablename__ = "corporate_actions"
    __table_args__ = (UniqueConstraint("security_id", "ex_date", "type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("securities.id"))
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class HistoricalUniverseModel(Base):
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


class LegacyOHLCVDailyModel(Base):
    """Legacy-archive EOD bars for the RP-012 overlap window (Phase 2 §1).

    A dedicated staging table so legacy-sourced bars for 2019-09-30→~2024-07-05
    can coexist with the current provider's live ``ohlcv_daily`` rows for the
    same ``(security_id, date)`` — Gate 4a reconciliation requires *both* sources
    to be present and comparable, and production's live dashboard must never be
    corrupted by legacy-sourced duplicates. Raw (pre-adjustment) prints only;
    no adjustment columns are carried here.
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
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    turnover_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ForwardReturnModel(Base):
    """A security's realized forward return/drawdown/volatility for one run/horizon.

    Append-only (ADR-006): a row is written only once ``horizon_days`` worth
    of bars exist after the run date, and is never revised afterward.
    """

    __tablename__ = "forward_returns"

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("screening_runs.id"), primary_key=True
    )
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True
    )
    horizon_days: Mapped[int] = mapped_column(Integer, primary_key=True)
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


class BenchmarkIndexDailyModel(Base):
    """Daily benchmark index close used for relative strength."""

    __tablename__ = "benchmark_index_daily"

    index_code: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class StrategyModel(Base):
    """A versioned, hashed strategy definition."""

    __tablename__ = "strategies"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    config_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScreeningRunModel(Base):
    """A screening run (one immutable snapshot once COMPLETED)."""

    __tablename__ = "screening_runs"
    __table_args__ = (
        UniqueConstraint("strategy_id", "run_date", "data_version", "config_hash"),
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
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id"), primary_key=True
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
