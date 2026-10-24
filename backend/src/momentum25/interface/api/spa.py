"""Serve the built web app from the API's own origin (ADR-013).

The browser then calls ``/api/v1`` on the same origin, so no API URL is configured
anywhere. Client-side routes (``/chart/RELIANCE``) fall back to ``index.html``, and
routes under ``/mf`` to ``mf.html``, the mutual-fund app's own page, when the build has it.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

# Paths the API itself owns; a miss under these is a real 404, never the web app.
_API_PATHS = ("api/", "docs", "openapi.json", "metrics")


def mount_spa(app: FastAPI, dist_dir: Path) -> None:
    """Serve ``dist_dir`` (a Vite build) at ``/``. Register after every API route."""
    index = dist_dir / "index.html"
    if not index.is_file():
        raise RuntimeError(f"web_dist_dir has no index.html: {dist_dir}")
    root = dist_dir.resolve()
    mf = root / "mf.html"

    # ponytail: no long-lived Cache-Control on hashed assets; ETag revalidation is
    # enough on loopback. Add `immutable` if a remote deployment needs it.
    # Compressed, because the entry script alone is over 600 kB (acceptance review R-02).
    assets = GZipMiddleware(StaticFiles(directory=root / "assets"), minimum_size=1000)
    app.mount("/assets", assets, name="web-assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def _web_app(path: str) -> FileResponse:
        if path.startswith(_API_PATHS):
            raise HTTPException(status_code=404)
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        page = mf if (path == "mf" or path.startswith("mf/")) and mf.is_file() else index
        return FileResponse(page, headers={"Cache-Control": "no-cache"})
