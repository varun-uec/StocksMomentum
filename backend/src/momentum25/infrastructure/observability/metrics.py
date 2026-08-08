"""Prometheus metrics instrumentation.

Provides counters, histograms, and gauges for the entire application lifecycle:
HTTP requests, screening runs, engine evaluations, provider calls, and cache operations.

All metrics use the ``m25_`` prefix for easy identification.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from prometheus_client import Counter, Gauge, Histogram, generate_latest

# ── HTTP metrics ────────────────────────────────────────────────────────────

http_requests_total = Counter(
    "m25_http_requests_total",
    "Total HTTP requests processed",
    labelnames=["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "m25_http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Screening pipeline metrics ──────────────────────────────────────────────

screening_runs_total = Counter(
    "m25_screening_runs_total",
    "Total screening runs executed",
    labelnames=["strategy", "status"],
)

screening_duration_seconds = Histogram(
    "m25_screening_duration_seconds",
    "Duration of a full screening run",
    labelnames=["strategy"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

screening_securities_evaluated = Histogram(
    "m25_screening_securities_evaluated",
    "Number of securities evaluated per run",
    labelnames=["strategy"],
    buckets=(10, 50, 100, 500, 1000, 2000, 5000),
)

screening_securities_passed = Gauge(
    "m25_screening_securities_passed",
    "Number of securities that passed the gate in the latest run",
    labelnames=["strategy"],
)

# ── Engine evaluation metrics ───────────────────────────────────────────────

engine_evaluations_total = Counter(
    "m25_engine_evaluations_total",
    "Total engine evaluations",
    labelnames=["engine_id", "passed"],
)

engine_evaluation_duration_seconds = Histogram(
    "m25_engine_evaluation_duration_seconds",
    "Duration of a single engine evaluation",
    labelnames=["engine_id"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

# ── Provider / external service metrics ─────────────────────────────────────

provider_calls_total = Counter(
    "m25_provider_calls_total",
    "Total calls to external data providers",
    labelnames=["provider", "operation", "status"],
)

provider_call_duration_seconds = Histogram(
    "m25_provider_call_duration_seconds",
    "Duration of external provider calls",
    labelnames=["provider", "operation"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# ── Cache metrics ───────────────────────────────────────────────────────────

cache_operations_total = Counter(
    "m25_cache_operations_total",
    "Total cache operations",
    labelnames=["operation", "hit"],
)

# ── Database metrics ────────────────────────────────────────────────────────

db_connection_pool_size = Gauge(
    "m25_db_connection_pool_size",
    "Database connection pool size",
)

db_connection_pool_overflow = Gauge(
    "m25_db_connection_pool_overflow",
    "Database connection pool max overflow",
)

# ── Scheduler metrics ───────────────────────────────────────────────────────

scheduler_jobs_total = Gauge(
    "m25_scheduler_jobs_total",
    "Number of registered scheduler jobs",
    labelnames=["state"],
)

# ── Active screening gauge ──────────────────────────────────────────────────

active_screening = Gauge(
    "m25_active_screening",
    "1 if a screening run is currently in progress, 0 otherwise",
)

# ── Data ingestion metrics ──────────────────────────────────────────────────

ingestion_duration_seconds = Histogram(
    "m25_ingestion_duration_seconds",
    "Duration of market data ingestion",
    labelnames=["provider", "date"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

ingestion_records_total = Counter(
    "m25_ingestion_records_total",
    "Total records ingested per operation",
    labelnames=["provider", "operation"],
)

# ── Indicator computation metrics ───────────────────────────────────────────

indicator_computation_duration_seconds = Histogram(
    "m25_indicator_computation_duration_seconds",
    "Duration of indicator computation pipeline",
    labelnames=["indicator_type"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

indicator_computations_total = Counter(
    "m25_indicator_computations_total",
    "Total indicator computations",
    labelnames=["indicator_type", "status"],
)

# ── Persistence metrics ─────────────────────────────────────────────────────

persistence_read_duration_seconds = Histogram(
    "m25_persistence_read_duration_seconds",
    "Duration of database read operations",
    labelnames=["repository", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

persistence_write_duration_seconds = Histogram(
    "m25_persistence_write_duration_seconds",
    "Duration of database write operations",
    labelnames=["repository", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
)

# ── Research metrics ────────────────────────────────────────────────────────

research_duration_seconds = Histogram(
    "m25_research_duration_seconds",
    "Duration of research/analysis operations",
    labelnames=["analysis_type"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# ── Ranking metrics ─────────────────────────────────────────────────────────

ranking_duration_seconds = Histogram(
    "m25_ranking_duration_seconds",
    "Duration of security ranking",
    labelnames=["method"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)


F = TypeVar("F", bound=Callable[..., Any])


def measure_duration(
    metric: Histogram,
    labels: dict[str, str] | None = None,
) -> Callable[[F], F]:
    """Decorator that measures and records function execution duration.

    Args:
        metric: A Prometheus Histogram to record the duration into.
        labels: Static label values to attach (e.g. ``{"provider": "nse"}``).

    Returns:
        A decorator wrapping the function with duration measurement.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

        return cast(F, wrapper)

    return decorator


def metrics_endpoint() -> tuple[bytes, dict[str, str]]:
    """Return the Prometheus metrics payload and content-type headers."""
    return generate_latest(), {"content-type": "text/plain; charset=utf-8"}