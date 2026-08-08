# Backend image — Python 3.12 + uv. Multi-stage for a slim runtime.
# =============================================================================
# Stage 1: Build dependencies
# =============================================================================
FROM python:3.12-slim AS builder
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive
WORKDIR /build

# Install uv (fast resolver) from the official image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system dependencies required by numpy/pandas at build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
RUN uv pip install --system --no-cache .

# =============================================================================
# Stage 2: Runtime image (slim)
# =============================================================================
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app/src
WORKDIR /app

# Install only runtime system dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source and migration config.
COPY src ./src
COPY alembic.ini ./

# Run as non-root user for security.
RUN addgroup --system --gid 1001 momentum25 && \
    adduser --system --uid 1001 --ingroup momentum25 momentum25 && \
    chown -R momentum25:momentum25 /app
USER momentum25

EXPOSE 8000

# Health check for container orchestration.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')"

# Use uvicorn with workers for production concurrency.
# Override CMD in docker-compose for migration + startup.
CMD ["uvicorn", "momentum25.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--limit-concurrency", "100"]