# Wickstreet image: the API serves the built web app from its own origin (ADR-013).
# Build context is the repository root. Multi-stage for a slim runtime.
# =============================================================================
# Stage 1: Build the web app
# =============================================================================
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# =============================================================================
# Stage 2: Build Python dependencies
# =============================================================================
FROM python:3.12-slim AS builder
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive
WORKDIR /build

# Install uv (fast resolver) from the official image, pinned so builds repeat.
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

# Install system dependencies required by numpy/pandas at build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install the locked dependency versions (uv.lock), not the newest that pyproject allows,
# then the project itself without dependencies for the `momentum25` command. The code
# runs from /app/src through PYTHONPATH.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv export --frozen --no-dev --no-emit-project --no-hashes -o requirements.txt \
    && uv pip install --system --no-cache -r requirements.txt \
    && uv pip install --system --no-cache --no-deps .

# =============================================================================
# Stage 3: Runtime image (slim)
# =============================================================================
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app/src \
    M25_STRATEGY_DIR=/app/strategies \
    M25_WEB_DIST_DIR=/app/web \
    WICKSTREET_BIND_HOST=0.0.0.0 \
    WICKSTREET_IN_CONTAINER=true
WORKDIR /app

# Install only runtime system dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source, migration config, strategy configs and the web build.
COPY backend/src ./src
COPY backend/alembic.ini backend/alembic-wickstreet.ini ./
COPY docs/architecture/strategies ./strategies
COPY --from=web /web/dist ./web

# Run as non-root user for security.
RUN addgroup --system --gid 1001 momentum25 && \
    adduser --system --uid 1001 --ingroup momentum25 momentum25 && \
    chown -R momentum25:momentum25 /app
USER momentum25

EXPOSE 8000

# Build identity for data manifests (ADR-014 §7): informational, never hashed.
# `make up` passes the git commit; an empty value leaves it unset.
ARG BUILD_ID=
ENV M25_BUILD_ID=${BUILD_ID}

# Health check for container orchestration.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')"

# One process: the scheduler (ADR-007) and Studio evaluations run inside it, and a
# second worker would run them twice. docker-compose adds the migration steps.
# The host serves Momentum25 and Wickstreet 2.0 (ADR-023 U1). Personal mode refuses
# to start unless WICKSTREET_PUBLISHED_BIND names a loopback address (U8).
CMD ["python", "-m", "apphost"]