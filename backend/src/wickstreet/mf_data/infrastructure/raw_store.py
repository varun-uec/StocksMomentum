"""Raw source files, gzip-compressed, outside the repository (ADR-022 §2.11, MF-9).

Path: ``<root>/<source>/<dataset>/<year>/<period>-<sha256 prefix>.gz``. A file is
written once; the same content for the same period is not written again.
"""

from __future__ import annotations

import gzip
import os
from datetime import date
from pathlib import Path

from wickstreet.mf_data.domain.model import RawFile


class FileRawStore:
    """Raw files on the local disk."""

    def __init__(self, root: Path) -> None:
        """Keep files under ``root``."""
        self._root = root

    def save(self, source: str, dataset: str, period: date, raw: RawFile) -> str:
        """Write ``raw`` unless it is already stored; return its path."""
        folder = self._root / source / dataset / str(period.year)
        path = folder / f"{period.isoformat()}-{raw.sha256[:16]}.gz"
        if not path.exists():
            folder.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".partial")
            partial.write_bytes(gzip.compress(raw.content))
            os.replace(partial, path)
        return str(path)

    def load(self, path: str) -> bytes:
        """Return the content stored at ``path``."""
        return gzip.decompress(Path(path).read_bytes())
