# Deployment Guide

## Overview

Momentum25 deploys as a set of Docker containers orchestrated via Docker Compose.
For production, deploy to a container orchestration platform (Kubernetes, ECS, Nomad).

## Prerequisites

- Docker 24+ and Docker Compose v2+
- PostgreSQL 16+
- Redis 7+
- Python 3.12+ (for local development only)
- Node.js 20+ (for local frontend development only)

## Environment Configuration

All configuration is via environment variables prefixed with `M25_`.

### Required (Production)

| Variable | Description | Example |
|---|---|---|
| `M25_DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://user:pass@host:5432/momentum25` |
| `M25_REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `M25_ENVIRONMENT` | Runtime environment | `production` |
| `M25_ALLOWED_HOSTS` | Host names (no ports) the API answers to. Anything else gets `421`. Default: loopback names. | `["localhost","127.0.0.1","[::1]","wickstreet.lan"]` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `M25_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `M25_LOG_JSON` | `true` | Structured JSON logging |
| `M25_SCHEDULER_ENABLED` | `false` | Enable the daily screening scheduler. The sample configuration keeps it off. |
| `M25_DIRECT_EXCHANGE_DOWNLOADS_ENABLED` | `false` | Allow optional direct NSE/BSE adapters. Keep off unless the operator has confirmed permission for the source and intended use. Authorized CSV import is the supported offline path. |
| `M25_SCHEDULE_CRON` | `30 18 * * 1-5` | Cron expression for daily run |
| `M25_DB_POOL_SIZE` | `10` | Database connection pool size |
| `M25_DB_MAX_OVERFLOW` | `5` | Database connection pool overflow |
| `M25_RATE_LIMIT_MAX_REQUESTS` | `200` | API rate limit per window |
| `M25_RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window in seconds |
| `M25_WEB_DIST_DIR` | `""` (image: `/app/web`) | Built web app to serve at `/`. Empty = API only. |
| `APP_BIND` (Compose) | `127.0.0.1` | Interface the app port binds to. The app has no authentication and is intended for one local user. `0.0.0.0` exposes unauthenticated read/write access to the LAN; that instance is not secure. Use an authenticating proxy before any network exposure. |
| `M25_RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts for external calls |
| `M25_REQUEST_TIMEOUT_SECONDS` | `30.0` | Request timeout for external calls |

## Deployment Steps

### 1. Build Images

```bash
# Build all images
docker compose build

# Build individual services
docker compose build api
docker compose build web
```

### 2. Run Database Migrations

```bash
docker compose run --rm api alembic upgrade head
```

### 3. Start Services

```bash
# Production
docker compose up -d

# With monitoring tools
docker compose --profile monitoring up -d
```

### 4. Verify Deployment

```bash
# Check health endpoints
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready
curl http://localhost:8000/api/v1/health/startup

# Check metrics
curl http://localhost:8000/metrics
```

## Production Checklist

- [ ] Database connection uses TLS
- [ ] Redis connection uses TLS (rediss://)
- [ ] Secrets managed via environment or vault (not .env files)
- [ ] `M25_ALLOWED_HOSTS` lists only the names this instance serves
- [ ] Keep `APP_BIND=127.0.0.1` for the single-user deployment. Any network exposure requires an authenticating reverse proxy; Host/Origin checks are not authentication (ADR-012).
- [ ] Rate limiting configured appropriately
- [ ] Log level set to `INFO` or `WARNING` (not `DEBUG`)
- [ ] Scheduler enabled only on one instance (or use distributed locking)
- [ ] Health check endpoints configured in orchestrator
- [ ] Resource limits set for all containers
- [ ] Read-only filesystem for containers where possible
- [ ] Backup strategy implemented (see backup.md)
- [ ] Monitoring and alerting configured
- [ ] Security headers verified
- [ ] SSL/TLS termination configured at load balancer

## Scaling

### Horizontal Scaling (API)

The API service is stateless and can be scaled horizontally:

```bash
docker compose up -d --scale api=3
```

For Kubernetes, configure HPA based on CPU/memory or request latency.

### Database

- Connection pool size should match the number of API replicas × connections per replica
- Consider PgBouncer for connection pooling at scale
- TimescaleDB for hypertable performance on large OHLCV datasets

## Health Checks

| Endpoint | Purpose | Expected Response |
|---|---|---|
| `/api/v1/health/live` | Liveness probe (process alive) | `{"status": "ok"}` |
| `/api/v1/health/ready` | Readiness probe (dependencies reachable) | `{"status": "ok"}` |
| `/api/v1/health/startup` | Startup probe (initialization complete) | `{"status": "ok"}` |
| `/api/v1/health` | Combined health check | `{"status": "ok"}` |
| `/metrics` | Prometheus metrics | Prometheus text format |

## Monitoring

### Prometheus Metrics

All metrics use the `m25_` prefix:

| Metric | Type | Description |
|---|---|---|
| `m25_http_requests_total` | Counter | Total HTTP requests by method, path, status |
| `m25_http_request_duration_seconds` | Histogram | HTTP request latency |
| `m25_screening_runs_total` | Counter | Screening run count by strategy, status |
| `m25_screening_duration_seconds` | Histogram | Screening run duration |
| `m25_ingestion_duration_seconds` | Histogram | Market data ingestion duration |
| `m25_indicator_computation_duration_seconds` | Histogram | Indicator computation duration |
| `m25_db_connection_pool_size` | Gauge | Database connection pool size |
| `m25_scheduler_jobs_total` | Gauge | Registered scheduler jobs |

### Logging

All logs are structured JSON with the following keys:

- `event`: Event name for filtering
- `timestamp`: ISO 8601 UTC timestamp
- `level`: Log level
- `logger`: Logger name
- `request_id`: Per-request correlation ID
- `correlation_id`: Distributed tracing ID
- `duration_ms`: Operation duration in milliseconds (where applicable)

## Test databases and memory limits

The development stack and test databases share one Docker VM (8 GB on the reference machine). A restored real-data copy on tmpfs once filled that VM, and the development API was OOM-killed. These rules prevent a repeat.

- **Stack limits.** `docker-compose.yml` caps `db` and `api` at 2 GB and 2 CPUs each, and `redis` at 256 MB and 0.5 CPU. All three restart `unless-stopped`.
- **Test databases.** Use `scripts/test-infra.sh` or the Make targets, never a hand-made container:
  - `make test-db` starts `m25-test` on port 65479 with database `momentum25_test`. Then run `M25_DATABASE_URL=<printed URL> make test`.
  - `make e2e-db` starts `m25-e2e` on port 65480 with an empty `momentum25_e2e` database for Playwright.
  - `make test-infra-down` removes both containers and their volumes.
  - `scripts/test-infra.sh up NAME PORT [MEMORY_MB] [DB_NAME]` starts any other copy, for example for a restored dump. `scripts/test-infra.sh list` and `scripts/test-infra.sh free` show what runs and how much memory is free.
- **What the script enforces.**
  - Data lives on a named volume, never tmpfs.
  - Each container has a hard memory cap (default 2 GB), and `shared_buffers` is a quarter of it.
  - It refuses to start when the VM's free memory is below the cap plus `MIN_FREE_MB` (default 1024 MB).
  - It binds 127.0.0.1 only, and removes only containers it labelled `wickstreet.test-infra=true`.
- **Never** point a test, seed or restore at the `momentum25` database. The suite refuses any database whose name does not end in `_test`.

