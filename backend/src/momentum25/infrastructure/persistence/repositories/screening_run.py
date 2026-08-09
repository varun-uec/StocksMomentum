"""Screening-run repository — run lifecycle plus append-only result snapshots."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.run import ScreeningRun
from momentum25.domain.research.forward_returns import ForwardReturn
from momentum25.domain.value_objects.results import (
    Ranking,
    RuleResult,
    ScorePoint,
    StockScore,
    UniverseMembership,
)
from momentum25.domain.value_objects.types import RunStatus, RunTrigger
from momentum25.infrastructure.persistence.models import ScreeningRunModel


def _to_domain(row: ScreeningRunModel) -> ScreeningRun:
    """Map an ORM row to a domain :class:`ScreeningRun`."""
    return ScreeningRun(
        id=row.id,
        strategy_id=row.strategy_id,
        run_date=row.run_date,
        data_version=row.data_version,
        config_hash=row.config_hash,
        status=RunStatus(row.status),
        trigger=RunTrigger(row.trigger),
        started_at=row.started_at,
        finished_at=row.finished_at,
        error=row.error,
        stats=row.stats or {},
    )


class SqlScreeningRunRepository:
    """Async SQLAlchemy implementation of :class:`ScreeningRunRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def create(self, run: ScreeningRun) -> int:
        """Persist a new run row; return its id."""
        model = ScreeningRunModel(
            strategy_id=run.strategy_id,
            run_date=run.run_date,
            data_version=run.data_version,
            config_hash=run.config_hash,
            status=run.status.value,
            trigger=run.trigger.value,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
            stats=run.stats or None,
        )
        self._session.add(model)
        await self._session.flush()
        return int(model.id)

    async def update(self, run: ScreeningRun) -> None:
        """Update a run's mutable lifecycle fields."""
        if run.id is None:
            raise ValueError("Cannot update a run without an id")
        model = await self._session.get(ScreeningRunModel, run.id)
        if model is None:
            raise ValueError(f"Run {run.id} not found")
        model.status = run.status.value
        model.started_at = run.started_at
        model.finished_at = run.finished_at
        model.error = run.error
        model.stats = run.stats or None

    async def get(self, run_id: int) -> ScreeningRun | None:
        """Return a run by id, or ``None``."""
        model = await self._session.get(ScreeningRunModel, run_id)
        return _to_domain(model) if model else None

    async def list_runs(
        self,
        status: str | None,
        limit: int,
        offset: int,
        exclude_historical: bool = True,
        exclude_research: bool = True,
        strategy_id: int | None = None,
    ) -> tuple[list[ScreeningRun], int]:
        """Return a page of runs and the total count, optionally scoped to one strategy.

        ``exclude_research`` filters out ad-hoc research/walk-forward runs
        (``data_version`` containing ``:research:`` or the specific
        ``:icv2:`` tag used by the 2026-07-02 Ranking-IC re-measurement
        walk-forward) -- these are real, permanent rows under ADR-006 and
        remain queryable directly, but including them in product-facing
        aggregate queries (scorecard/alpha/rule/engine effectiveness, the
        validation dashboard) makes those queries grow indefinitely slower
        every time a research script adds another batch of runs under the
        active production strategy, independent of any real product change.
        """
        base = select(ScreeningRunModel)
        if status:
            base = base.where(ScreeningRunModel.status == status.upper())
        if exclude_historical:
            base = base.where(
                ~ScreeningRunModel.data_version.like("historical:%")
            )
        if exclude_research:
            base = base.where(
                ~ScreeningRunModel.data_version.like("%:research:%"),
                ~ScreeningRunModel.data_version.like("%:icv2:%"),
            )
        if strategy_id is not None:
            base = base.where(ScreeningRunModel.strategy_id == strategy_id)
        total = await self._session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        result = await self._session.execute(
            base.order_by(ScreeningRunModel.run_date.desc(), ScreeningRunModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(r) for r in result.scalars().all()], int(total or 0)

    async def latest_completed(self, strategy_id: int) -> ScreeningRun | None:
        """Return the most recent completed *live* run for a strategy, or ``None``.

        Historical backfill runs (``data_version`` ``historical:%``) and ad-hoc
        research/walk-forward runs (``:research:``/``:icv2:``) are excluded, for
        the same reason they are excluded from :meth:`list_runs`: they are real,
        permanent rows under ADR-006 but are not the live production run. The
        Live Dashboard resolves its "latest run" through this method, so
        surfacing a historical backfill snapshot here would present stale,
        as-of-history data as the current live result.
        """
        result = await self._session.execute(
            select(ScreeningRunModel)
            .where(
                ScreeningRunModel.strategy_id == strategy_id,
                ScreeningRunModel.status == RunStatus.COMPLETED.value,
                ~ScreeningRunModel.data_version.like("historical:%"),
                ~ScreeningRunModel.data_version.like("%:research:%"),
                ~ScreeningRunModel.data_version.like("%:icv2:%"),
            )
            .order_by(ScreeningRunModel.run_date.desc(), ScreeningRunModel.id.desc())
        )
        row = result.scalars().first()
        return _to_domain(row) if row else None

    async def save_results(
        self, run_id: int, scores: list[StockScore], rankings: list[Ranking]
    ) -> None:
        """Append result rows for a completed run.

        Rank is supplied by the ranking engine (``Ranking.rank``) and joined onto the
        per-security score row; there is no separate rankings table.
        """
        from momentum25.infrastructure.persistence.models import (
            RuleResultModel,
            ScreeningResultModel,
        )

        rank_by_security = {ranking.security_id: ranking.rank for ranking in rankings}

        for score in scores:
            result_model = ScreeningResultModel(
                run_id=run_id,
                security_id=score.security_id,
                rank=rank_by_security.get(score.security_id),
                momentum_score=score.momentum_score,
                buy_setup_score=score.buy_setup_score,
                hard_filters_passed=score.hard_filters_passed,
            )
            self._session.add(result_model)
            for engine_result in score.engine_results:
                for rule in engine_result.rule_results:
                    rule_model = RuleResultModel(
                        run_id=run_id,
                        security_id=score.security_id,
                        rule_id=rule.rule_id,
                        engine_id=engine_result.engine_id,
                        passed=rule.passed,
                        raw_value=rule.raw_value,
                        threshold=rule.threshold,
                        operator=rule.operator,
                        weight=rule.weight,
                        contribution=rule.contribution,
                        explanation=rule.explanation,
                    )
                    self._session.add(rule_model)

    async def save_universe_membership(
        self, run_id: int, memberships: list[UniverseMembership]
    ) -> None:
        """Append per-run universe eligibility records."""
        from momentum25.infrastructure.persistence.models import UniverseMembershipModel

        for membership in memberships:
            self._session.add(
                UniverseMembershipModel(
                    run_id=run_id,
                    security_id=membership.security_id,
                    eligible=membership.eligible,
                    reason=membership.reason,
                )
            )

    async def save_forward_returns(self, run_id: int, returns: list[ForwardReturn]) -> None:
        """Append forward-return feature rows for a run."""
        from momentum25.infrastructure.persistence.models import ForwardReturnModel

        for fr in returns:
            self._session.add(
                ForwardReturnModel(
                    run_id=run_id,
                    security_id=fr.security_id,
                    horizon_days=fr.horizon_days,
                    forward_return=fr.forward_return,
                    forward_max_drawdown=fr.forward_max_drawdown,
                    forward_volatility=fr.forward_volatility,
                    forward_mfe=fr.forward_mfe,
                    forward_mae=fr.forward_mae,
                    benchmark_return=fr.benchmark_return,
                    excess_return=fr.excess_return,
                )
            )

    async def get_forward_returns(
        self, run_id: int, security_id: int | None = None
    ) -> list[ForwardReturn]:
        """Return persisted forward-return rows for a run, optionally scoped to one security."""
        from momentum25.infrastructure.persistence.models import ForwardReturnModel

        conditions = [ForwardReturnModel.run_id == run_id]
        if security_id is not None:
            conditions.append(ForwardReturnModel.security_id == security_id)
        result = await self._session.execute(
            select(ForwardReturnModel).where(*conditions).order_by(
                ForwardReturnModel.security_id, ForwardReturnModel.horizon_days
            )
        )
        return [
            ForwardReturn(
                security_id=row.security_id,
                horizon_days=row.horizon_days,
                forward_return=row.forward_return,
                forward_max_drawdown=row.forward_max_drawdown,
                forward_volatility=row.forward_volatility,
                forward_mfe=row.forward_mfe,
                forward_mae=row.forward_mae,
                benchmark_return=row.benchmark_return,
                excess_return=row.excess_return,
            )
            for row in result.scalars().all()
        ]

    async def get_rankings(
        self, run_id: int, limit: int, offset: int
    ) -> tuple[list[Ranking], int]:
        """Return a page of rankings for a run."""
        from momentum25.infrastructure.persistence.models import ScreeningResultModel

        base = (
            select(ScreeningResultModel)
            .where(ScreeningResultModel.run_id == run_id)
            .order_by(ScreeningResultModel.rank)
        )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        result = await self._session.execute(base.limit(limit).offset(offset))
        rows = result.scalars().all()
        rankings = [
            Ranking(
                security_id=r.security_id,
                momentum_score=r.momentum_score,
                buy_setup_score=r.buy_setup_score,
                rank=r.rank,
            )
            for r in rows
        ]
        return rankings, int(total or 0)

    async def get_screening_result(self, run_id: int, security_id: int) -> Ranking | None:
        """Return the persisted score/rank for one security in a run, or ``None``."""
        from momentum25.infrastructure.persistence.models import ScreeningResultModel

        result = await self._session.execute(
            select(ScreeningResultModel).where(
                ScreeningResultModel.run_id == run_id,
                ScreeningResultModel.security_id == security_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            return None
        return Ranking(
            security_id=row.security_id,
            momentum_score=row.momentum_score,
            buy_setup_score=row.buy_setup_score,
            rank=row.rank,
        )

    async def get_rule_results(self, run_id: int, security_id: int) -> list[RuleResult]:
        """Return all persisted rule results for one security in a run."""
        from momentum25.domain.value_objects.results import RuleResult
        from momentum25.infrastructure.persistence.models import RuleResultModel

        result = await self._session.execute(
            select(RuleResultModel)
            .where(RuleResultModel.run_id == run_id, RuleResultModel.security_id == security_id)
            .order_by(RuleResultModel.rule_id)
        )
        rows = result.scalars().all()
        return [
            RuleResult(
                rule_id=r.rule_id,
                engine_id=r.engine_id,
                passed=r.passed,
                operator=r.operator,
                explanation=r.explanation,
                raw_value=r.raw_value,
                threshold=r.threshold,
                contribution=r.contribution,
                weight=r.weight,
            )
            for r in rows
        ]

    async def get_rule_results_bulk(
        self, run_id: int, security_ids: list[int]
    ) -> dict[int, list[RuleResult]]:
        """Return persisted rule results for many securities in one run, grouped by security."""
        from momentum25.infrastructure.persistence.models import RuleResultModel

        if not security_ids:
            return {}

        result = await self._session.execute(
            select(RuleResultModel)
            .where(
                RuleResultModel.run_id == run_id,
                RuleResultModel.security_id.in_(security_ids),
            )
            .order_by(RuleResultModel.security_id, RuleResultModel.rule_id)
        )
        by_security: dict[int, list[RuleResult]] = {sid: [] for sid in security_ids}
        for r in result.scalars().all():
            by_security.setdefault(r.security_id, []).append(
                RuleResult(
                    rule_id=r.rule_id,
                    engine_id=r.engine_id,
                    passed=r.passed,
                    operator=r.operator,
                    explanation=r.explanation,
                    raw_value=r.raw_value,
                    threshold=r.threshold,
                    contribution=r.contribution,
                    weight=r.weight,
                )
            )
        return by_security

    async def get_previous_run_ranks(
        self, strategy_id: int, run_id: int, run_date: object
    ) -> dict[int, int]:
        """Return {security_id: rank} from the most recent completed run before this one."""
        from momentum25.infrastructure.persistence.models import ScreeningResultModel

        prev_run_id = await self._session.scalar(
            select(ScreeningRunModel.id)
            .where(
                ScreeningRunModel.strategy_id == strategy_id,
                ScreeningRunModel.status == RunStatus.COMPLETED.value,
                ScreeningRunModel.run_date < run_date,
            )
            .order_by(ScreeningRunModel.run_date.desc())
            .limit(1)
        )
        if prev_run_id is None:
            return {}

        result = await self._session.execute(
            select(ScreeningResultModel.security_id, ScreeningResultModel.rank).where(
                ScreeningResultModel.run_id == prev_run_id,
                ScreeningResultModel.rank.is_not(None),
            )
        )
        return {row.security_id: row.rank for row in result.all()}

    async def score_history(
        self, strategy_id: int, security_id: int, limit: int
    ) -> list[ScorePoint]:
        """Return a security's score/rank history across runs."""
        from momentum25.domain.value_objects.results import ScorePoint
        from momentum25.infrastructure.persistence.models import ScreeningResultModel

        result = await self._session.execute(
            select(
                ScreeningRunModel.run_date,
                ScreeningResultModel.momentum_score,
                ScreeningResultModel.buy_setup_score,
                ScreeningResultModel.rank,
            )
            .join(ScreeningResultModel, ScreeningRunModel.id == ScreeningResultModel.run_id)
            .where(
                ScreeningRunModel.strategy_id == strategy_id,
                # Only completed runs: a failed run's partial results are not a
                # point in the security's history.
                ScreeningRunModel.status == "COMPLETED",
                ScreeningResultModel.security_id == security_id,
            )
            .order_by(ScreeningRunModel.run_date.desc())
            .limit(limit)
        )
        rows = result.all()
        return [
            ScorePoint(
                run_date=row.run_date,
                momentum_score=row.momentum_score,
                buy_setup_score=row.buy_setup_score,
                rank=row.rank,
            )
            for row in rows
        ]
