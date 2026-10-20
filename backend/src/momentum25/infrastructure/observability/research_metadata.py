"""Research provenance metadata (Objective 9).

Captures the git commit hash the running code was built from, so a
screening run can be traced back to the exact source revision that
produced it -- ``config_hash`` (ADR-009) already pins the *strategy*
config, but not the engine/scoring/rule code itself, which can only change
via a code deploy.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache

from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("research_metadata")


def get_git_commit() -> str | None:
    """Return the current git commit hash, or ``None`` if unavailable.

    ``None`` (never a guessed/placeholder value) whenever the working
    directory isn't a git repository, ``git`` isn't installed, or the
    command otherwise fails -- a fabricated commit hash would be worse
    than an honestly-missing one.
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.SubprocessError, OSError) as exc:
        _logger.warning("git_commit_unavailable", error=str(exc))
        return None


@lru_cache(maxsize=1)
def build_identity() -> str | None:
    """Return the build identity, resolved once per process.

    ``M25_BUILD_ID`` (baked into the image) wins; otherwise the git commit at
    first call; otherwise ``None``. Cached, so manifest capture never shells
    out to git per call and a commit made while the process runs does not
    change what this process reports.
    """
    from momentum25.infrastructure.config.settings import get_settings

    configured = (get_settings().build_id or "").strip()
    return configured or get_git_commit()
