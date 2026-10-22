"""Strategy evaluation (ADR-014 §5–7): judge a user strategy with the code that screens it.

Three result classes, each with its fixed label:

- **Screening Result**: what the rules select on the latest session. No
  performance figure.
- **Historical Research — In-Sample**: every fifth session of the research
  window. A family may run it any number of times; each run is counted.
- **Out-of-Sample Evaluation**: the family's one evaluation on the sealed
  hold-out. A second one on the same window is refused.

Every decision is screened point in time at the manifest's data revision, and
results go to the Studio's own table, never to screening runs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from typing import Any

from structlog import get_logger

from momentum25.application.dto.studio import EvaluationDTO, SubmitEvaluationRequest
from momentum25.domain.entities.evaluation import Evaluation
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.errors import ConflictError, NotFoundError, ValidationError
from momentum25.domain.ports.evaluation import (
    EvaluationMarket,
    EvaluationRepository,
    ManifestRepository,
)
from momentum25.domain.ports.repositories import StudioRepository
from momentum25.domain.research.strategy_evaluation import (
    INCOMPLETE_PROVENANCE,
    INSUFFICIENT,
    LABELS,
    NOT_EVIDENCE,
    DecisionOutcome,
    EvaluationPolicy,
    MetricSummary,
    ResultClass,
    decision_outcome,
    decision_sessions,
    exit_session,
    holdout_window,
    power_statement,
    research_window,
    summarize,
)

_logger = get_logger("strategy_evaluation")

MarketAt = Callable[[int], EvaluationMarket]
POLICY = EvaluationPolicy()
DEFAULT_BENCHMARK = "NIFTY500"
DEFAULT_TOP_N = 25
ONE_TEST_IS_NOT_VALIDATION = (
    "One evaluation is not validation. Families tested on the same window share it, "
    "so the p-value is adjusted for them."
)


def evaluation_dto(evaluation: Evaluation) -> EvaluationDTO:
    """Map an evaluation to its response, with its fixed label."""
    return EvaluationDTO(**asdict(evaluation), label=LABELS[evaluation.result_class])


def _months(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


async def _member(studio: StudioRepository, family_id: int, config_hash: str) -> Strategy:
    family = await studio.get_family(family_id)
    if family is None:
        raise NotFoundError(f"No family {family_id}")
    strategy = await studio.get_strategy(config_hash)
    if strategy is None or strategy.family_id != family_id:
        raise ValidationError(f"{config_hash[:12]} is not a member of family {family_id}")
    return strategy


class SubmitEvaluation:
    """Fix the window and the manifest, and queue the evaluation."""

    def __init__(
        self,
        studio: StudioRepository,
        evaluations: EvaluationRepository,
        manifests: ManifestRepository,
        market_at: MarketAt,
        policy: EvaluationPolicy = POLICY,
    ) -> None:
        """Wire the use case; ``market_at`` binds market data to a data revision."""
        self._studio = studio
        self._evaluations = evaluations
        self._manifests = manifests
        self._market_at = market_at
        self._policy = policy

    async def execute(self, family_id: int, request: SubmitEvaluationRequest) -> EvaluationDTO:
        """Queue one evaluation. The hold-out is spent once it is queued."""
        return (await self.submit(family_id, request))[0]

    async def submit(
        self, family_id: int, request: SubmitEvaluationRequest
    ) -> tuple[EvaluationDTO, bool]:
        """Queue one evaluation; also say whether it is new.

        An In-Sample run is identified by its family, config hash, window and
        data version. Submitting the same identity again returns the stored run
        and does not count a second research run (ADR-014 section 12).
        """
        await _member(self._studio, family_id, request.config_hash)
        manifest = await self._manifests.capture()
        market = self._market_at(manifest.revision)
        window = await self._window(request.result_class, market)
        if request.result_class == "in_sample":
            known = await self._evaluations.find_in_sample(
                family_id, request.config_hash, window, manifest.data_version
            )
            if known is not None:
                return evaluation_dto(known), False
        try:
            evaluation = await self._evaluations.create(
                family_id, request.config_hash, request.result_class, window, manifest.data_version
            )
        except ConflictError:
            if request.result_class != "in_sample":
                raise
            # A concurrent identical submit stored the run first. Return that row.
            known = await self._evaluations.find_in_sample(
                family_id, request.config_hash, window, manifest.data_version
            )
            if known is None:
                raise
            return evaluation_dto(known), False
        return evaluation_dto(evaluation), True

    async def _window(
        self, result_class: ResultClass, market: EvaluationMarket
    ) -> tuple[date, date]:
        sessions = await market.sessions()
        label = LABELS[result_class]
        if not sessions:
            raise ValidationError(f"{label} {INSUFFICIENT}: no stored sessions")
        if result_class == "screening":
            return sessions[-1], sessions[-1]
        if result_class == "in_sample":
            window = research_window(sessions, self._policy)
            if window is None:
                raise ValidationError(f"{label} {INSUFFICIENT}: no research window yet")
            return window
        holdout = holdout_window(sessions, self._policy)
        if holdout is None:
            raise ValidationError(
                f"{label} {INSUFFICIENT}: no {self._policy.holdout_months}-month hold-out "
                "window has matured"
            )
        incomplete = await market.incomplete_months(*holdout)
        if len(incomplete) > self._policy.max_reconstructed_share * _months(*holdout):
            raise ValidationError(
                f"{label} {INSUFFICIENT}: {len(incomplete)} of {_months(*holdout)} months "
                "have reconstructed inputs"
            )
        return holdout


class GetEvaluation:
    """Return one evaluation."""

    def __init__(self, evaluations: EvaluationRepository) -> None:
        """Wire the use case with the evaluation repository."""
        self._evaluations = evaluations

    async def execute(self, evaluation_id: int) -> EvaluationDTO:
        """The evaluation with its progress and result."""
        evaluation = await self._evaluations.get(evaluation_id)
        if evaluation is None:
            raise NotFoundError(f"No evaluation {evaluation_id}")
        return evaluation_dto(evaluation)


class ListEvaluations:
    """Return a family's evaluations."""

    def __init__(self, evaluations: EvaluationRepository) -> None:
        """Wire the use case with the evaluation repository."""
        self._evaluations = evaluations

    async def execute(self, family_id: int) -> list[EvaluationDTO]:
        """Newest first."""
        return [evaluation_dto(e) for e in await self._evaluations.list_for_family(family_id)]


class RetryEvaluation:
    """Queue a failed evaluation again, on the same window and data revision."""

    def __init__(self, evaluations: EvaluationRepository) -> None:
        """Wire the use case with the evaluation repository."""
        self._evaluations = evaluations

    async def execute(self, evaluation_id: int) -> EvaluationDTO:
        """Refuse anything but a failed evaluation."""
        if not await self._evaluations.requeue(evaluation_id):
            raise ValidationError(f"Evaluation {evaluation_id} is not failed")
        return await GetEvaluation(self._evaluations).execute(evaluation_id)


class RunEvaluation:
    """Run a queued evaluation to completion (a background job)."""

    def __init__(
        self,
        studio: StudioRepository,
        evaluations: EvaluationRepository,
        manifests: ManifestRepository,
        market_at: MarketAt,
        policy: EvaluationPolicy = POLICY,
    ) -> None:
        """Wire the use case; ``market_at`` binds market data to a data revision."""
        self._studio = studio
        self._evaluations = evaluations
        self._manifests = manifests
        self._market_at = market_at
        self._policy = policy

    async def execute(self, evaluation_id: int) -> None:
        """Screen every decision, then store the result. A failure is recorded, not raised."""
        evaluation = await self._evaluations.get(evaluation_id)
        if evaluation is None or evaluation.status != "queued":
            return
        try:
            evaluation = await self._rebase(evaluation)
            strategy = await self._studio.get_strategy(evaluation.config_hash)
            if strategy is None:
                raise NotFoundError(f"No user strategy {evaluation.config_hash[:12]}")
            market = self._market_at(await self._revision(evaluation))
            if evaluation.result_class == "screening":
                await self._evaluations.start(evaluation.id, 1)
                result = await self._screening(evaluation, strategy, market)
            else:
                result = await self._history(evaluation, strategy, market)
            await self._evaluations.complete(evaluation.id, result)
        except Exception as exc:
            _logger.exception("strategy_evaluation_failed", evaluation_id=evaluation_id)
            await self._evaluations.fail(evaluation_id, f"{type(exc).__name__}: {exc}")

    async def _revision(self, evaluation: Evaluation) -> int:
        manifest = await self._manifests.get(evaluation.data_version)
        if manifest is None:
            raise NotFoundError(f"No manifest {evaluation.data_version}")
        return manifest.revision

    async def _rebase(self, evaluation: Evaluation) -> Evaluation:
        """Keep the data revision; take today's code state if it changed.

        That happens when a failed evaluation is retried after an upgrade.
        """
        current = await self._manifests.capture(await self._revision(evaluation))
        if current.data_version == evaluation.data_version:
            return evaluation
        await self._evaluations.rebase(evaluation.id, current.data_version)
        return replace(evaluation, data_version=current.data_version)

    async def _screening(
        self, evaluation: Evaluation, strategy: Strategy, market: EvaluationMarket
    ) -> dict[str, Any]:
        decision = evaluation.window_end
        scores, rankings, symbols = await market.screen(strategy, decision)
        top_n = int(strategy.config.ranking.get("top_n", DEFAULT_TOP_N))
        by_id = {s.security_id: s for s in scores}
        selected = sorted(
            (r for r in rankings if r.rank is not None and r.rank <= top_n),
            key=lambda r: r.rank or 0,
        )
        await self._evaluations.advance(evaluation.id, 1)
        return {
            "label": LABELS["screening"],
            "session": decision.isoformat(),
            "evaluated": len(scores),
            "qualified": sum(1 for r in rankings if r.rank is not None),
            "selection": [
                {
                    "rank": r.rank,
                    "symbol": symbols.get(r.security_id, str(r.security_id)),
                    "momentum_score": str(r.momentum_score),
                    "buy_setup_score": str(r.buy_setup_score),
                    "rules": [
                        {"rule_id": rr.rule_id, "passed": rr.passed, "explanation": rr.explanation}
                        for er in by_id[r.security_id].engine_results
                        for rr in er.rule_results
                    ],
                }
                for r in selected
            ],
        }

    async def _history(
        self, evaluation: Evaluation, strategy: Strategy, market: EvaluationMarket
    ) -> dict[str, Any]:
        policy = self._policy
        window = (evaluation.window_start, evaluation.window_end)
        sessions = await market.sessions()
        decisions = decision_sessions(sessions, *window, policy.step)
        await self._evaluations.start(evaluation.id, len(decisions))
        top_n = int(strategy.config.ranking.get("top_n", DEFAULT_TOP_N))
        benchmark = strategy.config.benchmark_index or DEFAULT_BENCHMARK
        outcomes: list[DecisionOutcome] = []
        for done, decision in enumerate(decisions, start=1):
            outcomes.append(
                await self._decision(market, strategy, sessions, decision, top_n, benchmark)
            )
            await self._evaluations.advance(evaluation.id, done)

        out_of_sample = evaluation.result_class == "out_of_sample"
        tests = (
            await self._evaluations.families_on_window(window, evaluation.id)
            if out_of_sample
            else 1
        )
        metrics = {
            "top_n_excess": (
                "Top-N excess return",
                [o.top_n_excess for o in outcomes],
                policy.plausible_excess,
            ),
            "qualified_excess": (
                "Qualified-set excess return",
                [o.qualified_excess for o in outcomes],
                policy.plausible_excess,
            ),
            "rank_ic": ("Rank IC", [o.rank_ic for o in outcomes], policy.plausible_ic),
        }
        summaries = {
            key: (name, summarize(values, policy, plausible, tests))
            for key, (name, values, plausible) in metrics.items()
        }
        incomplete = await market.incomplete_months(*window)
        result: dict[str, Any] = {
            "label": LABELS[evaluation.result_class],
            "strategy": {
                "name": strategy.name,
                "version": strategy.version,
                "config_hash": strategy.config_hash,
                "parent_config_hash": strategy.parent_config_hash,
            },
            "notice": ONE_TEST_IS_NOT_VALIDATION if out_of_sample else NOT_EVIDENCE,
            "window": {"start": window[0].isoformat(), "end": window[1].isoformat()},
            "horizon_sessions": policy.horizon,
            "top_n": top_n,
            "benchmark": benchmark,
            "decisions": len(outcomes),
            "policy": {k: str(v) for k, v in asdict(policy).items()},
            "metrics": {
                key: _metric(name, summary, policy) for key, (name, summary) in summaries.items()
            },
            "provenance": {
                "incomplete_months": incomplete,
                "label": INCOMPLETE_PROVENANCE if incomplete else None,
            },
            "regime": _regime(benchmark, await market.benchmark_path(benchmark, *window)),
            "outcomes": [{**asdict(o), "decision": o.decision.isoformat()} for o in outcomes],
        }
        if out_of_sample:
            result["families_on_window"] = tests
            if all(summary is None for _, summary in summaries.values()):
                result["unavailable"] = f"{LABELS['out_of_sample']} {INSUFFICIENT}"
        else:
            result["research_runs"] = await self._evaluations.research_runs(evaluation.family_id)
        return result

    async def _decision(
        self,
        market: EvaluationMarket,
        strategy: Strategy,
        sessions: list[date],
        decision: date,
        top_n: int,
        benchmark: str,
    ) -> DecisionOutcome:
        _, rankings, _ = await market.screen(strategy, decision)
        qualified = [(r.rank, r.security_id) for r in rankings if r.rank is not None]
        exit_on = exit_session(sessions, decision, self._policy.horizon)
        excess = (
            await market.forward_excess([sid for _, sid in qualified], decision, exit_on, benchmark)
            if exit_on is not None
            else {}
        )
        ranked = [(rank, excess[sid]) for rank, sid in qualified if sid in excess]
        return decision_outcome(decision, ranked, top_n, self._policy.min_qualified)


def _metric(name: str, summary: MetricSummary | None, policy: EvaluationPolicy) -> dict[str, Any]:
    statement = power_statement(summary, name, policy.power)
    if summary is None:
        return {"name": name, "available": False, "statement": statement}
    return {"name": name, "available": True, "statement": statement, **asdict(summary)}


def _regime(benchmark: str, closes: list[Decimal]) -> dict[str, Any]:
    """Describe the window's market plainly: its return and its largest fall."""
    if len(closes) < 2 or closes[0] <= 0:
        return {"text": f"No {benchmark} closes for this window."}
    total = float(closes[-1] / closes[0] - 1)
    peak, fall = closes[0], 0.0
    for close in closes:
        peak = max(peak, close)
        fall = min(fall, float(close / peak - 1))
    return {
        "benchmark_return": total,
        "largest_fall": fall,
        "text": (
            f"{benchmark} returned {total:+.1%} over this window, with a largest fall of "
            f"{fall:.1%}. Results from one market regime may not hold in another."
        ),
    }
