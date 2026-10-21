"""Ports for strategy evaluation (ADR-014 §5–7)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from momentum25.domain.entities.evaluation import Evaluation
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.research.strategy_evaluation import ResultClass
from momentum25.domain.value_objects.manifest import DataManifest
from momentum25.domain.value_objects.results import Ranking, StockScore


class EvaluationMarket(Protocol):
    """Market data at one data revision, read point in time per decision."""

    async def sessions(self) -> list[date]:
        """Trading sessions from the first to the last stored bar."""
        ...

    async def screen(
        self, strategy: Strategy, decision: date
    ) -> tuple[list[StockScore], list[Ranking], dict[int, str]]:
        """Score and rank the decision's universe; also return symbols by security id."""
        ...

    async def forward_excess(
        self, security_ids: list[int], decision: date, exit_on: date, benchmark: str
    ) -> dict[int, float]:
        """Each name's return from the decision close to the exit, less the benchmark's.

        A name with no bar at the exit keeps its last close before it.
        """
        ...

    async def benchmark_path(self, code: str, start: date, end: date) -> list[Decimal]:
        """The benchmark's closes from ``start`` to ``end``."""
        ...

    async def incomplete_months(self, start: date, end: date) -> list[str]:
        """Months (``YYYY-MM``) with any ``reconstructed`` input row."""
        ...


class EvaluationRepository(Protocol):
    """Persistence for evaluations: the Studio's research namespace."""

    async def create(
        self,
        family_id: int,
        config_hash: str,
        result_class: ResultClass,
        window: tuple[date, date],
        data_version: str,
    ) -> Evaluation:
        """Queue an evaluation; raise ``ConflictError`` if the family's hold-out is spent."""
        ...

    async def get(self, evaluation_id: int) -> Evaluation | None:
        """Return an evaluation, or ``None``."""
        ...

    async def list_for_family(self, family_id: int) -> list[Evaluation]:
        """Return a family's evaluations, newest first."""
        ...

    async def start(self, evaluation_id: int, total: int) -> None:
        """Mark an evaluation running with ``total`` steps."""
        ...

    async def advance(self, evaluation_id: int, done: int) -> None:
        """Record how many steps are done."""
        ...

    async def complete(self, evaluation_id: int, result: dict[str, Any]) -> None:
        """Store the result; the row is final afterwards."""
        ...

    async def rebase(self, evaluation_id: int, data_version: str) -> None:
        """Point an unfinished evaluation at a manifest with today's code state."""
        ...

    async def fail(self, evaluation_id: int, error: str) -> None:
        """Mark an evaluation failed."""
        ...

    async def requeue(self, evaluation_id: int) -> bool:
        """Queue a failed evaluation again; False if it was not failed."""
        ...

    async def families_on_window(self, window: tuple[date, date], up_to_id: int) -> int:
        """Families that submitted an Out-of-Sample Evaluation on ``window`` by ``up_to_id``."""
        ...

    async def find_in_sample(
        self, family_id: int, config_hash: str, window: tuple[date, date], data_version: str
    ) -> Evaluation | None:
        """The In-Sample evaluation with this run identity, or ``None``.

        The identity is the family, the config hash, the window and the data version.
        """
        ...

    async def research_runs(self, family_id: int) -> int:
        """Distinct Historical Research — In-Sample run identities in a family."""
        ...

    async def interrupt_unfinished(self) -> int:
        """Fail every queued or running evaluation (after a restart)."""
        ...


class ManifestRepository(Protocol):
    """Capture and read data-version manifests."""

    async def capture(self, revision: int | None = None) -> DataManifest:
        """Record the inputs at ``revision`` (default: now) and today's code state."""
        ...

    async def get(self, data_version: str) -> DataManifest | None:
        """Return a stored manifest, or ``None``."""
        ...
