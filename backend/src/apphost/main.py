"""One ASGI app that serves the MF app at ``/api/v1/mf`` and Momentum25 at ``/``.

Starlette does not run the lifespan of a mounted app, so this host enters both:
Momentum25 first, because its lifespan configures logging, then the MF app. Exit
runs in reverse. If either startup fails, the host does not start.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.routing import Mount

from momentum25.main import app as momentum25_app
from wickstreet.app import create_app as create_wickstreet_app

MF_PREFIX = "/api/v1/mf"


def create_host(momentum25: FastAPI, wickstreet: FastAPI) -> Starlette:
    """Mount both apps and chain their lifespans."""

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with (
            momentum25.router.lifespan_context(momentum25),
            wickstreet.router.lifespan_context(wickstreet),
        ):
            yield

    # The MF mount comes first: Momentum25's catch-all SPA route would otherwise match.
    return Starlette(
        routes=[Mount(MF_PREFIX, app=wickstreet), Mount("/", app=momentum25)],
        lifespan=lifespan,
    )


app = create_host(momentum25_app, create_wickstreet_app())
