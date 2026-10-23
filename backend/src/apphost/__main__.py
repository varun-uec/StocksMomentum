"""``python -m apphost``: start the host where the settings allow (ADR-023 OM-2, U8).

Personal mode refuses a non-loopback bind while loading the settings, before the
server opens a socket.
"""

from __future__ import annotations

import uvicorn

from wickstreet.config import get_settings


def main() -> None:
    """Serve the host on the configured address."""
    settings = get_settings()
    # One process: Momentum25's scheduler runs inside it (ADR-007).
    uvicorn.run(
        "apphost.main:app",
        host=settings.bind_host,
        port=settings.bind_port,
        limit_concurrency=100,
    )


if __name__ == "__main__":
    main()
