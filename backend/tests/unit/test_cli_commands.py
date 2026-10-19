"""The CLI must perform its advertised action or fail explicitly."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from momentum25.interface.cli.main import app


def test_retired_ingest_exits_nonzero_with_replacement_command() -> None:
    result = CliRunner().invoke(app, ["ingest"])

    assert result.exit_code == 2
    assert "was retired" in result.output
    assert "import-eod" in result.output


def test_screen_runs_against_stored_data_without_enabling_ingest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    async def run(strategy: str, *, ingest_enabled: bool) -> int:
        received.update(strategy=strategy, ingest_enabled=ingest_enabled)
        return 47

    monkeypatch.setattr(
        "momentum25.app.services.screening_job.run_screening_pipeline", run
    )
    result = CliRunner().invoke(app, ["screen", "--strategy", "fixture"])

    assert result.exit_code == 0, result.output
    assert received == {"strategy": "fixture", "ingest_enabled": False}
    assert "Completed screening run 47" in result.output
