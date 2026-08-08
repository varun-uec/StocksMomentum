"""Unit tests for git-commit research-provenance capture (Objective 9)."""

from __future__ import annotations

import subprocess

import pytest

from momentum25.infrastructure.observability.research_metadata import get_git_commit


def test_get_git_commit_returns_none_when_git_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", _raise)
    assert get_git_commit() is None


def test_get_git_commit_returns_none_when_not_a_git_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])

    monkeypatch.setattr(subprocess, "run", _raise)
    assert get_git_commit() is None


def test_get_git_commit_returns_the_commit_hash_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=(), returncode=0, stdout="abc123\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    assert get_git_commit() == "abc123"
