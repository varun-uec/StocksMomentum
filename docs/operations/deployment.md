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
| `M25_CORS_ORIGINS` | Allowed CORS origins | `["https://app.momentum25.com"]` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `M25_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `M25_LOG_JSON` | `true` | Structured JSON logging |
| `M25_SCHEDULER_ENABLED` | `false` | Enable daily screening scheduler |
| `M25_SCHEDULE_CRON` | `30 18 * * 1-5` | Cron expression for daily run |
| `M25_DB_POOL_SIZE` | `10` | Database connection pool size |
| `M25_DB_MAX_OVERFLOW` | `5` | Database connection pool overflow |
| `M25_RATE_LIMIT_MAX_REQUESTS` | `200` | API rate limit per window |
| `M25_RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window in seconds |
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
- [ ] CORS origins restricted to known domains
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