"""R3-B-20: stdlib log records (APScheduler) render as JSON like structlog events."""

import json
import logging

import pytest

from momentum25.infrastructure.logging.setup import configure_logging


def test_stdlib_record_is_one_json_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json_logs=True)
    logging.getLogger("apscheduler.scheduler").info("Scheduler started")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    event = json.loads(line)
    assert event["event"] == "Scheduler started"
    assert event["logger"] == "apscheduler.scheduler"
    assert event["level"] == "info"
    assert "timestamp" in event
