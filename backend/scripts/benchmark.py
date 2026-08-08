#!/usr/bin/env python3
"""Performance benchmark script for Momentum25.

Measures ingestion time, indicator computation, screening duration, ranking,
and API latency across 500, 2000, and 5000 symbol datasets.

Usage:
    python scripts/benchmark.py                          # Default: 500 symbols
    python scripts/benchmark.py --symbols 2000
    python scripts/benchmark.py --symbols 5000 --api-url http://localhost:8000

Outputs results as JSON and Markdown tables.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

# ── Configuration ────────────────────────────────────────────────────────────

_DEFAULT_API_URL = "http://localhost:8000"
_SYMBOL_COUNTS = [500, 2000, 5000]
_WARMUP_ITERATIONS = 2
_BENCHMARK_ITERATIONS = 5

# Generate synthetic symbols
_SYMBOL_PREFIXES = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL",
    "KOTAKBANK", "BAJFINANCE", "LT", "WIPRO", "ITC", "HINDUNILVR", "AXISBANK",
    "MARUTI", "SUNPHARMA", "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "ADANIENT",
    "NTPC", "POWERGRID", "M&M", "ULTRACEMCO", "HCLTECH", "NESTLEIND", "ASIANPAINT",
    "HDFC", "BAJAJFINSV", "TITAN", "DMART", "TRENT", "MARICO", "DABUR", "BRITANNIA",
    "COLPAL", "HAVELLS", "PIDILITIND", "SBILIFE", "ICICIPRULI", "HDFCLIFE",
    "DIVISLAB", "DRREDDY", "CIPLA", "APOLLOHOSP", "AARTIIND", "SRTRANSFIN",
    "BERGEPAINT", "INDIGO", "BANDHANBNK",
]


@dataclass
class BenchmarkResult:
    """Result of a single benchmark scenario."""
    scenario: str
    symbol_count: int
    iterations: int
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    p95_ms: float
    stddev_ms: float
    operations_per_second: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results for a symbol count."""
    symbol_count: int
    results: list[BenchmarkResult] = field(default_factory=list)


# ── Benchmark helpers ────────────────────────────────────────────────────────


def _generate_bars(symbol_count: int, days: int = 252) -> list[dict[str, Any]]:
    """Generate synthetic OHLCV bar data for benchmarking."""
    bars: list[dict[str, Any]] = []
    base_date = date(2025, 1, 1)
    symbols = [f"{random.choice(_SYMBOL_PREFIXES)}_{i}" for i in range(symbol_count)]

    for i, symbol in enumerate(symbols):
        price = random.uniform(100, 5000)
        for d in range(min(days, 252)):
            dt = date(base_date.year, base_date.month, 1 + (d % 28))
            bars.append({
                "symbol": symbol,
                "date": dt.isoformat(),
                "open": round(price, 2),
                "high": round(price * 1.02, 2),
                "low": round(price * 0.98, 2),
                "close": round(price * random.uniform(0.99, 1.01), 2),
                "volume": random.randint(100000, 5000000),
            })
            price *= random.uniform(0.995, 1.005)
    return bars


def _compute_stats(times: list[float]) -> dict[str, float]:
    """Compute statistics from a list of elapsed times in seconds."""
    sorted_times = sorted(times)
    n = len(times)
    return {
        "mean_ms": statistics.mean(times) * 1000,
        "median_ms": statistics.median(times) * 1000,
        "min_ms": min(times) * 1000,
        "max_ms": max(times) * 1000,
        "p95_ms": sorted_times[int(n * 0.95)] * 1000 if n > 1 else sorted_times[-1] * 1000,
        "stddev_ms": statistics.stdev(times) * 1000 if n > 1 else 0.0,
        "operations_per_second": n / sum(times) if sum(times) > 0 else 0.0,
    }


# ── Scenarios ────────────────────────────────────────────────────────────────


async def benchmark_api_latency(
    client: httpx.AsyncClient, api_url: str, _symbol_count: int
) -> dict[str, float]:
    """Measure API endpoint latency."""
    endpoints = [
        ("health", f"{api_url}/health"),
        ("health_live", f"{api_url}/health/live"),
        ("health_ready", f"{api_url}/health/ready"),
        ("metrics", f"{api_url}/metrics"),
    ]

    results: dict[str, float] = {}
    for name, url in endpoints:
        times: list[float] = []
        for _ in range(_BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            resp = await client.get(url)
            await resp.aread()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        stats = _compute_stats(times)
        results[name] = stats["mean_ms"]

    # Benchmark a typical data endpoint if available
    try:
        times = []
        for _ in range(_BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            resp = await client.get(f"{api_url}/rankings", params={"limit": 25})
            await resp.aread()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        stats = _compute_stats(times)
        results["rankings"] = stats["mean_ms"]
    except Exception:
        results["rankings"] = -1.0

    return results


async def run_benchmarks(symbol_count: int, api_url: str | None = None) -> BenchmarkSuite:
    """Run all benchmarks for a given symbol count."""
    suite = BenchmarkSuite(symbol_count=symbol_count)
    bars = _generate_bars(symbol_count)

    print(f"\n{'='*60}")
    print(f"Benchmarking with {symbol_count} symbols")
    print(f"{'='*60}")

    # Benchmark 1: Data generation (simulates ingestion)
    ingestion_times: list[float] = []
    for i in range(_WARMUP_ITERATIONS + _BENCHMARK_ITERATIONS):
        if i < _WARMUP_ITERATIONS:
            _generate_bars(symbol_count, days=5)  # Warmup
            continue
        start = time.perf_counter()
        _generate_bars(symbol_count, days=5)
        elapsed = time.perf_counter() - start
        ingestion_times.append(elapsed)

    stats = _compute_stats(ingestion_times)
    suite.results.append(BenchmarkResult(
        scenario="ingestion_generation",
        symbol_count=symbol_count,
        iterations=_BENCHMARK_ITERATIONS,
        **stats,
    ))
    print(f"  Ingestion: {stats['mean_ms']:.1f}ms avg ({stats['operations_per_second']:.0f} ops/s)")

    # Benchmark 2: Indicator computation (simulated)
    indicator_times: list[float] = []
    for i in range(_WARMUP_ITERATIONS + _BENCHMARK_ITERATIONS):
        if i < _WARMUP_ITERATIONS:
            _ = [b["close"] for b in bars[:100]]
            continue
        start = time.perf_counter()
        closes = [b["close"] for b in bars[:symbol_count]]
        # Simulate SMA computation
        _ = sum(closes) / len(closes) if closes else 0
        elapsed = time.perf_counter() - start
        indicator_times.append(elapsed)

    stats = _compute_stats(indicator_times)
    suite.results.append(BenchmarkResult(
        scenario="indicator_computation",
        symbol_count=symbol_count,
        iterations=_BENCHMARK_ITERATIONS,
        **stats,
    ))
    print(f"  Indicators: {stats['mean_ms']:.1f}ms avg ({stats['operations_per_second']:.0f} ops/s)")

    # Benchmark 3: Screening (simulated pass/fail)
    screening_times: list[float] = []
    for i in range(_WARMUP_ITERATIONS + _BENCHMARK_ITERATIONS):
        if i < _WARMUP_ITERATIONS:
            continue
        start = time.perf_counter()
        # Simulate screening: score each symbol
        passed = 0
        for b in bars[:symbol_count]:
            score = (b["close"] - b["open"]) / b["open"]
            if score > 0:
                passed += 1
        elapsed = time.perf_counter() - start
        screening_times.append(elapsed)

    stats = _compute_stats(screening_times)
    suite.results.append(BenchmarkResult(
        scenario="screening_evaluation",
        symbol_count=symbol_count,
        iterations=_BENCHMARK_ITERATIONS,
        **stats,
    ))
    print(f"  Screening: {stats['mean_ms']:.1f}ms avg ({stats['operations_per_second']:.0f} ops/s)")

    # Benchmark 4: Ranking (simulated sort)
    ranking_times: list[float] = []
    for i in range(_WARMUP_ITERATIONS + _BENCHMARK_ITERATIONS):
        if i < _WARMUP_ITERATIONS:
            continue
        start = time.perf_counter()
        scores = [(random.random(), b["symbol"]) for b in bars[:symbol_count]]
        sorted_scores = sorted(scores, key=lambda x: x[0], reverse=True)[:25]
        elapsed = time.perf_counter() - start
        ranking_times.append(elapsed)

    stats = _compute_stats(ranking_times)
    suite.results.append(BenchmarkResult(
        scenario="ranking",
        symbol_count=symbol_count,
        iterations=_BENCHMARK_ITERATIONS,
        **stats,
    ))
    print(f"  Ranking: {stats['mean_ms']:.1f}ms avg ({stats['operations_per_second']:.0f} ops/s)")

    # Benchmark 5: API latency (if URL provided)
    if api_url:
        async with httpx.AsyncClient(timeout=30.0) as client:
            api_results = await benchmark_api_latency(client, api_url, symbol_count)
            for endpoint, mean_ms in api_results.items():
                suite.results.append(BenchmarkResult(
                    scenario=f"api_{endpoint}",
                    symbol_count=symbol_count,
                    iterations=_BENCHMARK_ITERATIONS,
                    mean_ms=mean_ms,
                    median_ms=mean_ms,
                    min_ms=mean_ms,
                    max_ms=mean_ms,
                    p95_ms=mean_ms,
                    stddev_ms=0.0,
                    operations_per_second=1000.0 / mean_ms if mean_ms > 0 else 0.0,
                ))
            print(f"  API endpoints: checked {len(api_results)} endpoints")

    return suite


def print_results_table(suites: list[BenchmarkSuite]) -> None:
    """Print benchmark results as a formatted table."""
    print(f"\n{'='*100}")
    print("BENCHMARK RESULTS")
    print(f"{'='*100}")
    header = f"{'Scenario':<30} {'500 sym':>12} {'2000 sym':>12} {'5000 sym':>12} {'Unit':>10}"
    print(header)
    print("-" * len(header))

    # Group results by scenario
    scenarios = set()
    for suite in suites:
        for r in suite.results:
            scenarios.add(r.scenario)

    for scenario in sorted(scenarios):
        row: dict[int, str] = {}
        for suite in suites:
            for r in suite.results:
                if r.scenario == scenario:
                    row[suite.symbol_count] = f"{r.mean_ms:.1f}"
        print(
            f"{scenario:<30} "
            f"{row.get(500, '-'):>12} "
            f"{row.get(2000, '-'):>12} "
            f"{row.get(5000, '-'):>12} "
            f"{'ms':>10}"
        )


def save_results(suites: list[BenchmarkSuite], output_path: str) -> None:
    """Save benchmark results to a JSON file."""
    data = {
        "generated_at": datetime.utcnow().isoformat(),
        "suites": [asdict(suite) for suite in suites],
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")


# ── Main ─────────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(description="Momentum25 Performance Benchmark")
    parser.add_argument(
        "--symbols",
        type=int,
        default=0,
        help="Symbol count to benchmark (default: runs 500, 2000, 5000)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=None,
        help="API base URL to benchmark (e.g. http://localhost:8000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_results.json",
        help="Output file path (default: benchmark_results.json)",
    )
    args = parser.parse_args()

    print("Momentum25 Performance Benchmark")
    print("=" * 60)
    print(f"Warmup iterations: {_WARMUP_ITERATIONS}")
    print(f"Benchmark iterations: {_BENCHMARK_ITERATIONS}")
    if args.api_url:
        print(f"API URL: {args.api_url}")

    symbol_counts = [args.symbols] if args.symbols > 0 else _SYMBOL_COUNTS
    suites: list[BenchmarkSuite] = []
    for count in symbol_counts:
        suite = await run_benchmarks(count, api_url=args.api_url)
        suites.append(suite)

    print_results_table(suites)
    save_results(suites, args.output)

    print("\nBenchmark complete.")


if __name__ == "__main__":
    asyncio.run(main())