"""Data-version manifests (ADR-014 §7, M14): capture, store and read them back."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.engine_version import ENGINE_VERSION, REFERENCE_UNIVERSE_VERSION
from momentum25.domain.strategy.rule_schemas import registry_version
from momentum25.domain.value_objects.manifest import DataManifest
from momentum25.infrastructure.calendar.nse_calendar import calendar_version
from momentum25.infrastructure.observability.research_metadata import build_identity
from momentum25.infrastructure.persistence.models import DataManifestModel
from momentum25.infrastructure.persistence.point_in_time import current_revision
from momentum25.infrastructure.pipelines.indicator_pipeline import INDICATOR_VERSION


class SqlDataManifestRepository:
    """Stores manifests by their hash; a manifest stored twice keeps one row."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def capture(self, revision: int | None = None) -> DataManifest:
        """Record the inputs at ``revision`` (default: now), the engine versions and the build."""
        manifest = DataManifest(
            revision=await current_revision(self._session) if revision is None else revision,
            indicator_version=INDICATOR_VERSION,
            rule_registry_version=registry_version(),
            calendar_version=calendar_version(),
            build_id=build_identity(),
            engine_version=ENGINE_VERSION,
            reference_universe_version=REFERENCE_UNIVERSE_VERSION,
        )
        await self._session.execute(
            insert(DataManifestModel)
            .values(data_version=manifest.data_version, body=manifest.body())
            .on_conflict_do_nothing(index_elements=["data_version"])
        )
        return manifest

    async def get(self, data_version: str) -> DataManifest | None:
        """Return a stored manifest, or ``None``."""
        row = await self._session.get(DataManifestModel, data_version)
        return None if row is None else DataManifest.from_body(row.body)
