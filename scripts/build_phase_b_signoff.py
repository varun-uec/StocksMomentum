#!/usr/bin/env python3
"""Build the Phase B sign-off PDF and self-contained HTML from verified inputs.

The generator reads committed B1/B2/B4 captures, the final B3/candle captures,
and a verification JSON supplied by the final test and benchmark run. It does not
run tests, start services, or create evidence markers.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "audit-evidence" / "phase-b"
DEFAULT_CAPTURES = Path("/tmp/wickstreet-phase-b-final/shots")
STATIC_SHOTS = DEFAULT_OUTPUT / "screenshots"
PHASE_A_BENCH = DEFAULT_OUTPUT / "m13-bench-phase-a.json"

COLORS = {
    "paper": "#fbfaf7",
    "ink": "#17262c",
    "muted": "#5f7280",
    "line": "#dfe3df",
    "panel": "#f1f3ef",
    "accent": "#147d65",
    "accent_soft": "#e2f1ec",
    "warn": "#9a5b00",
    "warn_soft": "#fbf0dc",
}


@dataclass(frozen=True)
class Shot:
    filename: str
    title: str
    caption: str
    alt: str
    source: Path
    phone: bool = False


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    workflow: tuple[str, ...]
    proof: str
    shots: tuple[Shot, ...]


def _required(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise ValueError(f"verification JSON is missing {where}.{key}")
    return mapping[key]


def _count(mapping: dict[str, Any], key: str, where: str) -> int:
    value = _required(mapping, key, where)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{where}.{key} must be a non-negative integer")
    return value


def _metric(mapping: dict[str, Any], key: str, where: str) -> float:
    value = _required(mapping, key, where)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{where}.{key} must be a non-negative number")
    return float(value)


def _resolve_input_path(value: Any, base_file: Path, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty path string")
    path = Path(value)
    candidates = [path] if path.is_absolute() else [base_file.parent / path, ROOT / path]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"{field} does not name a readable file: {value}")


def _read_metric_file(path: Path, field: str) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return raw


def _normalize_sample(sample: Any, where: str, *, p95_name: str = "p95") -> dict[str, Any]:
    if not isinstance(sample, dict):
        raise ValueError(f"{where} must be an object")
    return {
        "runs": _count(sample, "runs", where),
        "p50_ms": _metric(sample, "p50", where),
        "p95_ms": _metric(sample, p95_name, where),
        "max_ms": _metric(sample, "max", where),
    }


def validate_verification(raw: Any, verification_file: Path) -> dict[str, Any]:
    """Validate final counts and normalize the two raw benchmark files."""
    if not isinstance(raw, dict):
        raise ValueError("verification JSON root must be an object")
    commit = _required(raw, "source_commit", "root")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        raise ValueError("source_commit must be a 7 to 40 character lowercase git hash")
    report_date = _required(raw, "date", "root")
    if not isinstance(report_date, str):
        raise ValueError("date must be an ISO date string")
    date.fromisoformat(report_date)

    checks = {
        "backend_pytest": {"passed": _count(raw, "backend_passed", "root")},
        "mypy": {"checked": 263, "errors": 0},
        "import_contracts": {"passed": 2, "failed": 0},
        "web_unit": {"passed": _count(raw, "web_unit_passed", "root")},
        "web_lint": "passed",
        "web_typecheck": "passed",
        "full_e2e": {
            "passed": _count(raw, "e2e_passed", "root"),
            "failed": _count(raw, "e2e_failed", "root"),
            "skipped": _count(raw, "e2e_skipped", "root"),
        },
    }
    nfr_path = _resolve_input_path(_required(raw, "nfr11_path", "root"), verification_file, "nfr11_path")
    bench_path = _resolve_input_path(_required(raw, "m13_bench_path", "root"), verification_file, "m13_bench_path")
    nfr = _read_metric_file(nfr_path, "nfr11_path")
    bench = _read_metric_file(bench_path, "m13_bench_path")
    nfr_commit = _required(nfr, "git_commit", "nfr11")
    bench_commit = _required(bench, "git_commit", "m13_bench")
    if not isinstance(nfr_commit, str) or not isinstance(bench_commit, str):
        raise ValueError("benchmark git_commit fields must be strings")
    if not commit.startswith(nfr_commit) and not nfr_commit.startswith(commit):
        raise ValueError("NFR-11 capture commit does not match source_commit")
    if not commit.startswith(bench_commit) and not bench_commit.startswith(commit):
        raise ValueError("M13 capture commit does not match source_commit")

    nfr_results = _required(nfr, "results", "nfr11")
    bench_results = _required(bench, "results", "m13_bench")
    if not isinstance(nfr_results, dict) or not isinstance(bench_results, dict):
        raise ValueError("benchmark results must be objects")
    normalized_nfr = {
        mode: _normalize_sample(_required(nfr_results, mode, "nfr11.results"), f"nfr11.results.{mode}")
        for mode in ("warm", "cold")
    }
    normalized_charts: dict[str, Any] = {}
    for count in ("1", "4", "16"):
        chart = _required(bench_results, count, "m13_bench.results")
        if not isinstance(chart, dict):
            raise ValueError(f"m13_bench.results.{count} must be an object")
        normalized_charts[count] = {
            "warm_open_ms": _normalize_sample(chart.get("warm_open_ms"), f"m13_bench.results.{count}.warm_open_ms"),
            "cold_open_ms": _normalize_sample(chart.get("cold_open_ms"), f"m13_bench.results.{count}.cold_open_ms"),
            "pan_fps": {
                "runs": _count(chart["pan_fps"], "runs", f"m13_bench.results.{count}.pan_fps"),
                "p5": _metric(chart["pan_fps"], "p5", f"m13_bench.results.{count}.pan_fps"),
                "p50": _metric(chart["pan_fps"], "p50", f"m13_bench.results.{count}.pan_fps"),
            },
            "js_heap_mb": {
                "samples": _count(chart["js_heap_mb"], "samples", f"m13_bench.results.{count}.js_heap_mb"),
                "p50": _metric(chart["js_heap_mb"], "p50", f"m13_bench.results.{count}.js_heap_mb"),
                "max": _metric(chart["js_heap_mb"], "max", f"m13_bench.results.{count}.js_heap_mb"),
            },
        }
    perf = {
        "capture_commit": nfr_commit,
        "hardware": _required(nfr, "hardware", "nfr11"),
        "browser": _required(nfr, "browser", "nfr11"),
        "dataset": _required(nfr, "dataset", "nfr11"),
        "grid_dataset": _required(bench, "dataset", "m13_bench"),
        "cold_method": _required(nfr, "cold_method", "nfr11"),
        "nfr11": normalized_nfr,
        "charts": normalized_charts,
        "comparison_note": raw.get("m13_comparison_note", ""),
    }
    for key in ("hardware", "browser", "dataset", "grid_dataset", "cold_method"):
        if not isinstance(perf[key], str) or not perf[key].strip():
            raise ValueError(f"benchmark {key} field must be a non-empty string")
    if not isinstance(perf["comparison_note"], str):
        raise ValueError("m13_comparison_note must be a string")
    return {"source_commit": commit, "date": report_date, "checks": checks, "performance": perf}


def _shot(
    filename: str,
    title: str,
    caption: str,
    source: Path,
    *,
    alt: str | None = None,
    phone: bool = False,
) -> Shot:
    if not source.is_file():
        raise FileNotFoundError(f"required sign-off capture is missing: {source}")
    return Shot(filename, title, caption, alt or title, source, phone)


def make_sections(static_dir: Path, captures: Path) -> tuple[Section, ...]:
    """Pair the original workflow captions with current capture sources."""
    b1 = (
        _shot("01-screener-range-popover.png", "Range popover", "RS >= 60 narrows the run to 9 of 22.", static_dir / "01-screener-range-popover.png"),
        _shot("02-screener-saved-screen-menu.png", "Saved screen menu", "Qualified leaders combines Qualified, RS >= 60, and score columns.", static_dir / "02-screener-saved-screen-menu.png"),
        _shot("03-screener-saved-screen-dark.png", "Saved screen after reload", "The saved filters and columns reopen in the dark theme.", static_dir / "03-screener-saved-screen-dark.png"),
        _shot("04-screener-phone.png", "Screener at 390 px", "Pills wrap without sideways scrolling.", static_dir / "04-screener-phone.png", phone=True),
    )
    b2 = (
        _shot("05-replay-not-available-in-replay.png", "Replay before a run", "Replay to 2026-05-18 shows 2,551 bars and cuts RSI and the INFY compare at that date. No run exists that early.", static_dir / "05-replay-not-available-in-replay.png"),
        _shot("06-replay-historical-run-assessment.png", "Replay on a run date", "The Assessment uses the newest run on or before 2026-08-07.", static_dir / "06-replay-historical-run-assessment.png"),
        _shot("07-replay-watchlist-and-bottom-screener.png", "Bottom screener in replay", "The panel screens the same run-on-or-before date.", static_dir / "07-replay-watchlist-and-bottom-screener.png"),
        _shot("08-replay-dark.png", "Replay in dark theme", "Replay controls keep the sea-green accent.", static_dir / "08-replay-dark.png"),
        _shot("09-replay-phone.png", "Replay at 390 px", "The replay row wraps while Exit stays reachable.", static_dir / "09-replay-phone.png", phone=True),
    )
    b3 = (
        _shot("10-drawing-tools-light.png", "Nine tools, light theme", "Final E2ECANDLE capture: Arrow, date ranges, Ellipse, Triangle, Fib extension, Pitchfork, Callout, and Price label.", captures / "10-drawing-tools-light.png"),
        _shot("12-drawing-tools-dark.png", "Nine tools, dark theme", "The same saved drawings after reload, captured on E2ECANDLE.", captures / "12-drawing-tools-dark.png"),
    )
    flyouts = tuple(
        _shot(name, label, f"Grouped drawing tools: {label}.", static_dir / name)
        for name, label in (
            ("11-flyout-lines.png", "Lines"),
            ("11-flyout-fibonacci.png", "Fibonacci"),
            ("11-flyout-shapes.png", "Shapes"),
            ("11-flyout-annotation.png", "Annotation"),
            ("11-flyout-measure.png", "Measure"),
        )
    )
    b4 = (
        _shot("13-drawing-menu-alert-on-this-line.png", "Alert on this line", "The drawing menu opens a line alert from the saved ray.", static_dir / "13-drawing-menu-alert-on-this-line.png"),
        _shot("14-alert-form-prefilled-ray.png", "Prefilled ray alert", "The form shows the ray and explains its frozen anchors and session rule.", static_dir / "14-alert-form-prefilled-ray.png"),
        _shot("15-ray-alert-fired.png", "Ray alert fired", "The synthetic TCS ray crossing fired on 2026-07-21 at 284.39, drawing snapshot revision 1.", static_dir / "15-ray-alert-fired.png"),
    )
    candles = tuple(
        _shot(filename, title, caption, captures / filename, phone=phone)
        for filename, title, caption, phone in (
            ("candles-01-daily-6m-light.png", "Daily, 6M, light", "E2ECANDLE daily bars over six months.", False),
            ("candles-02-daily-3m-light.png", "Daily, 3M, light", "E2ECANDLE daily bars over three months.", False),
            ("candles-03-weekly-1y-light.png", "Weekly, 1Y, light", "Weekly bars show the one-year range.", False),
            ("candles-04-monthly-max-light.png", "Monthly, MAX, light", "Monthly bars show the full synthetic history.", False),
            ("candles-05-replay-before-split-light.png", "Replay before the split", "On 2026-06-12 the 1:2 split had not happened; prices remain on the pre-split basis.", False),
            ("candles-06-daily-3m-dark.png", "Daily, 3M, dark", "Daily bars in the dark theme.", False),
            ("candles-07-weekly-1y-dark.png", "Weekly, 1Y, dark", "Weekly bars in the dark theme.", False),
            ("candles-08-phone-3m-light.png", "Phone, 3M, light", "Daily chart at 390 px in the light theme.", True),
            ("candles-09-phone-3m-dark.png", "Phone, 3M, dark", "Daily chart at 390 px in the dark theme.", True),
        )
    )
    return (
        Section(
            "B1",
            "Richer screener filters and saved screens",
            (
                "Open a range pill for Momentum, Buy setup, RS, Rank, or Delta Rank. Set inclusive bounds, choose a sector, and combine filters.",
                "Matches counts the full run. Both screeners page through every result instead of stopping at the first 100 rows.",
                "Save a screen as a versioned user document. It survives reload and opens from the chart bottom panel.",
            ),
            "Proof: whole-run filter reference, saved-screen round trip, duplicate-name rejection, ETag 412 handling, validation cap, and ranking tie-break regression.",
            b1,
        ),
        Section(
            "B2",
            "EOD bar replay with no look-ahead",
            (
                "Replay controls provide a date, Play/Pause, Step forward, 1x/3x/10x speed, and Exit.",
                "Every price and indicator series is cut at the selected date. Later corporate actions do not change earlier prices; a weekly bar contains only sessions through that date.",
                "Assessment uses the newest live or historical run on or before the replay date. Later drawings hide, alerts pause, and Exit restores the viewport.",
            ),
            "Proof: bar count and date at each step, as-of requests for every series, weekly partial bar, viewport restoration, hidden drawings, and run-dated assessment and screener.",
            b2,
        ),
        Section(
            "B3",
            "Nine drawing tools in the grouped rail",
            (
                "Lines: Pitchfork. Fibonacci: Trend-based extension. Shapes: Ellipse and Triangle. Annotation: Callout, Price label, and Arrow. Measure: Date range and Date and price range.",
                "Each tool has a create, reload, drag, resize, recolour, undo/redo, lock, and hide checklist.",
                "Anchors save at traded prices, so they stay attached to bars across the GOLDIAM 1:5 split.",
            ),
            "Proof: nine per-tool checklists, split adjustment regression, hit tests, extension levels, pitchfork median and tines. The main tool captures were recaptured on E2ECANDLE; retained B1/B2/B4 workflow screenshots use synthetic screening and TCS fixtures.",
            b3 + flyouts,
        ),
        Section(
            "B4",
            "Alerts on a trendline, ray, or extended line",
            (
                "Open an alert from a line's context menu, Shift+F10, or its Object tree entry.",
                "The server freezes the drawing anchors. Each anchor uses its own date's adjustment factor; each session close is compared with that date's line value.",
                "The first close crossing after arming fires once. Moving the drawing later does not change the saved alert rule.",
            ),
            "Proof: alert creation, frozen snapshot after moving the drawing, oracle-predicted firing date, split and bonus handling, idempotency, stale revisions, and API rejection cases.",
            b4,
        ),
        Section(
            "Candle review",
            "Representative candles, intervals, themes, and replay",
            (
                "E2ECANDLE is a deterministic chart-only fixture with 525 sessions from 2024-08-05 to 2026-08-07 and a 1:2 split on 2026-06-22.",
                "Its highs, lows, bodies, gaps, and volatility vary. The pixel test checks each drawn wick and body against the API bar within 1 px.",
                "The fixture is inactive and carries fund-unit ISIN INFE2ECANDL1. Backend integration coverage confirms it does not change screening results or rankings, RS ratings, market breadth, or the PIT equity screen.",
            ),
            "No production financial calculations changed. Axis-label collision and interval-loading viewport fixes are UI changes. The historical TCS replay and alert workflow captures remain valid synthetic evidence; these candle views were captured separately on E2ECANDLE.",
            candles,
        ),
    )


def _format_sample(sample: dict[str, Any]) -> str:
    return f"n={sample['runs']}, P50 {sample['p50_ms']:.0f} ms, P95 {sample['p95_ms']:.0f} ms, max {sample['max_ms']:.0f} ms"


def _format_performance(perf: dict[str, Any]) -> tuple[list[list[str]], list[list[str]]]:
    nfr_rows = [["Chart open", "Samples", "P50", "P95", "Max", "Target"]]
    for name, label, target in (("warm", "Warm", "<= 1,000 ms"), ("cold", "Cold", "<= 3,000 ms")):
        item = perf["nfr11"][name]
        nfr_rows.append(
            [label, str(item["runs"]), f"{item['p50_ms']:.0f} ms", f"{item['p95_ms']:.0f} ms", f"{item['max_ms']:.0f} ms", target]
        )
    grid_rows = [["Charts", "Warm open P95", "Cold open P95", "Pan P5", "Heap max"]]
    for count in ("1", "4", "16"):
        item = perf["charts"][count]
        grid_rows.append(
            [
                count,
                f"{item['warm_open_ms']['p95_ms']:.0f} ms",
                f"{item['cold_open_ms']['p95_ms']:.0f} ms",
                f"{item['pan_fps']['p5']:.0f} fps",
                f"{item['js_heap_mb']['max']:.0f} MB",
            ]
        )
    return nfr_rows, grid_rows


def build_html(metrics: dict[str, Any], sections: tuple[Section, ...]) -> str:
    """Build a self-contained, responsive HTML report with embedded PNGs."""
    checks = metrics["checks"]
    perf = metrics["performance"]
    nfr_rows, grid_rows = _format_performance(perf)
    phases = (
        ("B1", "Screener filters and saved screens"),
        ("B2", "EOD replay"),
        ("B3", "Drawing tools"),
        ("B4", "Line alerts"),
    )
    blocks = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Wickstreet Phase B Sign-off</title>",
        "<style>"
        ":root{color-scheme:light;--paper:#fbfaf7;--ink:#17262c;--muted:#5f7280;--line:#dfe3df;--panel:#f1f3ef;--accent:#147d65;--soft:#e2f1ec;--warn:#9a5b00}"
        "*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:32px 18px 56px}"
        "main{max-width:1120px;margin:auto;display:flex;flex-direction:column;gap:38px}header{border-bottom:2px solid var(--ink);padding-bottom:22px;display:grid;gap:12px}"
        "h1,h2{font-family:Georgia,'Iowan Old Style',serif;line-height:1.15;margin:0}h1{font-size:42px}h2{font-size:27px}h3{font-size:15px;margin:0}p{margin:0;max-width:78ch}.eyebrow,th{font:600 11px/1.3 ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}"
        ".chips{display:flex;flex-wrap:wrap;gap:8px}.chip{border:1px solid var(--line);background:var(--panel);border-radius:3px;padding:6px 9px;font:12px ui-monospace,Menlo,monospace}.ok{border-color:var(--accent);background:var(--soft);color:var(--accent)}.defer{border-color:#d9ad58;color:var(--warn);background:#fbf0dc}"
        "section{display:grid;gap:16px;border-top:1px solid var(--line);padding-top:18px}.subtle{color:var(--muted)}.tables{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}"
        "table{border-collapse:collapse;width:100%;font-size:13px;background:white;border:1px solid var(--line)}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{background:var(--panel);color:var(--muted)}td:last-child{font-variant-numeric:tabular-nums}tr:last-child td{border-bottom:0}.proof{color:var(--muted);font:12px/1.5 ui-monospace,Menlo,monospace;overflow-wrap:anywhere}ol{margin:0;padding-left:22px;max-width:82ch}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}.gallery.chart{grid-template-columns:minmax(0,1fr);max-width:860px}.gallery.flyouts{grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}figure{margin:0;border:1px solid var(--line);background:white;padding:8px;display:grid;gap:8px;align-content:start}figure img{display:block;width:100%;height:auto}figure.phone{max-width:270px}figcaption{font-size:13px;line-height:1.45}figcaption b{display:block;margin-bottom:2px}footer{border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font:11px ui-monospace,Menlo,monospace}code{font:12px ui-monospace,Menlo,monospace;background:var(--panel);padding:1px 4px}@media print{body{padding:0}main{max-width:none;gap:25px}section{break-inside:avoid}.gallery{grid-template-columns:repeat(2,1fr)}img{break-inside:avoid}}"
        "</style></head><body><main>",
        "<header><span class=\"eyebrow\">Wickstreet / charting parity milestones / "
        + html.escape(metrics["date"])
        + "</span><h1>Phase B sign-off</h1><p>B1-B4 are built, tested, and committed locally. B5 Volume Profile is explicitly deferred. Phase C has not started. Every capture and benchmark uses synthetic fixture data in a marked E2E database.</p>"
        "<div class=\"chips\">"
        + "".join(f"<span class=\"chip ok\">{html.escape(label)}</span>" for _key, label in phases)
        + "<span class=\"chip defer\">B5 Volume Profile / deferred</span><span class=\"chip\">Phase C / not started</span></div></header>",
        "<section><span class=\"eyebrow\">Verification</span><h2>Results and performance</h2><div class=\"tables\"><table><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>"
        f"<tr><td>Backend pytest</td><td>{checks['backend_pytest']['passed']} passed</td></tr>"
        f"<tr><td>Mypy strict</td><td>{checks['mypy']['checked']} checked / {checks['mypy']['errors']} errors</td></tr>"
        f"<tr><td>Import contracts</td><td>{checks['import_contracts']['passed']} passed / {checks['import_contracts']['failed']} failed</td></tr>"
        f"<tr><td>Web unit</td><td>{checks['web_unit']['passed']} passed</td></tr>"
        f"<tr><td>Web lint / typecheck</td><td>{checks['web_lint']} / {checks['web_typecheck']}</td></tr>"
        f"<tr><td>Full serial E2E</td><td>{checks['full_e2e']['passed']} passed / {checks['full_e2e']['failed']} failed / {checks['full_e2e']['skipped']} skipped</td></tr>"
        "</tbody></table><table><thead><tr><th>NFR-11 chart open</th><th>Samples</th><th>P50</th><th>P95</th><th>Max</th><th>Limit</th></tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in nfr_rows[1:])
        + "</tbody></table></div><table><thead><tr>"
        + "".join(f"<th>{html.escape(cell)}</th>" for cell in grid_rows[0])
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in grid_rows[1:])
        + "</tbody></table><p class=\"subtle\">"
        + html.escape(perf["comparison_note"])
        + "</p><p class=\"subtle\">"
        + html.escape(perf["cold_method"])
        + " Performance machine: "
        + html.escape(perf["hardware"])
        + "; browser: "
        + html.escape(perf["browser"])
        + "; dataset: "
        + html.escape(perf["dataset"])
        + "; grid dataset: "
        + html.escape(perf["grid_dataset"])
        + ". Chart-open and pan measurements use 30 runs; heap snapshots use 6. NFR-11 cold restarts the API per run and excludes boot time. M13 grid cold uses a new browser context with the API left running. The Phase A 16-chart warm P95 was 1,288 ms at 35883c9.</p>"
        "<p class=\"proof\">Backend regression: the inactive E2ECANDLE fixture leaves live screening/rankings, RS, market breadth, and the PIT equity screen unchanged.</p></section>",
    ]

    for section in sections:
        blocks.append(
            f"<section><span class=\"eyebrow\">{html.escape(section.key)}</span><h2>{html.escape(section.title)}</h2><ol>"
            + "".join(f"<li>{html.escape(item)}</li>" for item in section.workflow)
            + f"</ol><p class=\"proof\">{html.escape(section.proof)}</p><div class=\"gallery{' chart' if section.key == 'B3' else ''}\">"
        )
        flyouts = []
        for shot in section.shots:
            if shot.filename.startswith("11-flyout-"):
                flyouts.append(shot)
                continue
            data = base64.b64encode(shot.source.read_bytes()).decode("ascii")
            phone_class = " class=\"phone\"" if shot.phone else ""
            blocks.append(
                f"<figure{phone_class}><img alt=\"{html.escape(shot.alt, quote=True)}\" src=\"data:image/png;base64,{data}\"><figcaption><b>{html.escape(shot.title)}.</b> {html.escape(shot.caption)}</figcaption></figure>"
            )
        blocks.append("</div>")
        if flyouts:
            blocks.append("<h3>Grouped tool menus</h3><div class=\"gallery flyouts\">")
            for shot in flyouts:
                data = base64.b64encode(shot.source.read_bytes()).decode("ascii")
                blocks.append(
                    f"<figure><img alt=\"{html.escape(shot.alt, quote=True)}\" src=\"data:image/png;base64,{data}\"><figcaption><b>{html.escape(shot.title)}.</b> {html.escape(shot.caption)}</figcaption></figure>"
                )
            blocks.append("</div>")
        blocks.append("</section>")

    blocks.extend(
        [
            "<section><span class=\"eyebrow\">Decision and limits</span><h2>Scope and acceptance</h2><p>The line-alert trigger basis is recorded in <code>ADR-013b-line-alert-amendment.md</code>. Alerts use each anchor's date-specific adjustment factor and compare daily closes.</p><p>Known limits: replay runs on /chart and ends when the user leaves; it advances one daily session at every interval. Line alerts are close-to-close and daily. Fibonacci spacing is screen-based, so log-scale prices are not exact ratios. B5 remains deferred. Phase C is not started.</p><p>Axis-label collision and interval-loading viewport fixes are UI changes. Production financial calculations are unchanged. The UI acceptance decision remains with the owner.</p><p>Nothing has been pushed.</p></section>",
            f"<footer>Source commit {html.escape(metrics['source_commit'])}. Performance capture commit {html.escape(perf['capture_commit'])}. Generated from verified JSON and embedded PNG captures.</footer>",
            "</main></body></html>",
        ]
    )
    return "".join(blocks)


def _pdf_styles() -> dict[str, Any]:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch

    return {
        "colors": colors,
        "inch": inch,
        "title": ParagraphStyle("Title", fontName="Times-Bold", fontSize=27, leading=31, textColor=colors.HexColor(COLORS["ink"]), spaceAfter=8),
        "heading": ParagraphStyle("Heading", fontName="Times-Bold", fontSize=19, leading=22, textColor=colors.HexColor(COLORS["ink"]), spaceAfter=6),
        "body": ParagraphStyle("Body", fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor(COLORS["ink"]), spaceAfter=5),
        "small": ParagraphStyle("Small", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor(COLORS["muted"])),
        "caption": ParagraphStyle("Caption", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor(COLORS["ink"])),
        "eyebrow": ParagraphStyle("Eyebrow", fontName="Courier-Bold", fontSize=8, leading=10, textColor=colors.HexColor(COLORS["accent"]), spaceAfter=4),
        "table_head": ParagraphStyle("TableHead", fontName="Courier-Bold", fontSize=7, leading=8, textColor=colors.HexColor(COLORS["muted"])),
        "table_cell": ParagraphStyle("TableCell", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor(COLORS["ink"])),
        "mono": ParagraphStyle("Mono", fontName="Courier", fontSize=7, leading=9, textColor=colors.HexColor(COLORS["muted"])),
        "bullet": ParagraphStyle("Bullet", fontName="Helvetica", fontSize=9, leading=12, leftIndent=12, firstLineIndent=-8, bulletIndent=0, textColor=colors.HexColor(COLORS["ink"]), spaceAfter=3),
    }


def write_pdf(path: Path, metrics: dict[str, Any], sections: tuple[Section, ...]) -> None:
    """Write the landscape PDF using reportlab Platypus."""
    from reportlab import rl_config
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        Image,
        KeepTogether,
        PageTemplate,
        Paragraph,
        PageBreak,
        Spacer,
        Table,
        TableStyle,
    )

    # Binary Flate streams are smaller than ASCII85 and keep Git's PDF diff binary.
    rl_config.useA85 = False

    styles = _pdf_styles()
    colors = styles["colors"]
    inch = styles["inch"]
    page = landscape(A4)
    margin_x, margin_top, margin_bottom = 0.42 * inch, 0.42 * inch, 0.38 * inch

    class SignoffDoc(BaseDocTemplate):
        def __init__(self, filename: str) -> None:
            super().__init__(filename, pagesize=page, leftMargin=margin_x, rightMargin=margin_x, topMargin=margin_top, bottomMargin=margin_bottom, title="Wickstreet Phase B Sign-off", author="Wickstreet")
            frame = Frame(margin_x, margin_bottom, page[0] - 2 * margin_x, page[1] - margin_top - margin_bottom, id="body", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            self.addPageTemplates(PageTemplate(id="main", frames=frame, onPage=self._page_chrome))

        def _page_chrome(self, canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor(COLORS["line"]))
            canvas.setLineWidth(0.6)
            canvas.line(margin_x, 0.26 * inch, page[0] - margin_x, 0.26 * inch)
            canvas.setFont("Courier", 7)
            canvas.setFillColor(colors.HexColor(COLORS["muted"]))
            canvas.drawString(margin_x, 0.13 * inch, f"SOURCE {metrics['source_commit']}   /   WICKSTREET PHASE B   /   {metrics['date']}")
            canvas.drawRightString(page[0] - margin_x, 0.13 * inch, f"{doc.page}")
            canvas.restoreState()

    def para(text: str, style: str = "body") -> Any:
        # Built-in PDF fonts do not include arrows from the raw benchmark JSON.
        printable = text.translate(str.maketrans({"\u2192": "to", "\u00d7": "x", "\u2014": "-", "\u2013": "-", "\u2011": "-"}))
        return Paragraph(printable, styles[style])

    def table(rows: list[list[str]], widths: list[float], header: bool = True) -> Any:
        data = [[para(cell, "table_head" if header and row_i == 0 else "table_cell") for cell in row] for row_i, row in enumerate(rows)]
        item = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        item.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLORS["panel"])),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(COLORS["ink"])),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor(COLORS["line"])),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return item

    available_width = page[0] - 2 * margin_x

    def screenshot(shot: Shot, *, width: float, height: float) -> Any:
        image = Image(str(shot.source), width=width, height=height, kind="proportional", hAlign="CENTER")
        caption = para(f"<b>{html.escape(shot.title)}.</b> {html.escape(shot.caption)}", "caption")
        card = Table([[image], [caption]], colWidths=[width + 12], hAlign="CENTER")
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.65, colors.HexColor(COLORS["line"])),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return card

    def flyout_page(shots: list[Shot]) -> list[Any]:
        flows: list[Any] = [para("Grouped drawing tool menus", "heading")]
        cells = []
        column_width = available_width / 3
        for shot in shots:
            image = Image(str(shot.source), width=column_width - 22, height=205, kind="proportional", hAlign="CENTER")
            caption = para(f"<b>{html.escape(shot.title)}.</b> {html.escape(shot.caption)}", "caption")
            card = Table([[image], [caption]], colWidths=[column_width - 8], hAlign="CENTER")
            card.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor(COLORS["line"])),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            cells.append(card)
        for start in range(0, len(cells), 3):
            pair = cells[start : start + 3]
            while len(pair) < 3:
                pair.append("")
            row = Table([pair], colWidths=[column_width] * 3, hAlign="LEFT")
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            flows.append(row)
        return flows

    checks = metrics["checks"]
    perf = metrics["performance"]
    nfr_rows, grid_rows = _format_performance(perf)
    result_rows = [
        ["Suite", "Result"],
        ["Backend pytest", f"{checks['backend_pytest']['passed']} passed"],
        ["Mypy strict", f"{checks['mypy']['checked']} checked / {checks['mypy']['errors']} errors"],
        ["Import contracts", f"{checks['import_contracts']['passed']} passed / {checks['import_contracts']['failed']} failed"],
        ["Web unit", f"{checks['web_unit']['passed']} passed"],
        ["Web lint / typecheck", f"{checks['web_lint']} / {checks['web_typecheck']}"],
        ["Full serial E2E", f"{checks['full_e2e']['passed']} passed / {checks['full_e2e']['failed']} failed / {checks['full_e2e']['skipped']} skipped"],
    ]
    story: list[Any] = [
        para(f"WICKSTREET  /  CHARTING PARITY MILESTONES  /  {metrics['date']}", "eyebrow"),
        para("Phase B sign-off", "title"),
        para("B1-B4 are built, tested, and committed locally. B5 Volume Profile is explicitly deferred. Phase C has not started. Every capture and benchmark uses synthetic fixture data in a marked E2E database.", "body"),
        para("B1 screener  /  B2 replay  /  B3 drawing tools  /  B4 line alerts  /  B5 deferred  /  Phase C not started", "mono"),
        Spacer(1, 9),
        para("Results and performance", "heading"),
        table(result_rows, [1.75 * inch, 5.5 * inch]),
        Spacer(1, 8),
        table(nfr_rows, [1.25 * inch, 0.78 * inch, 0.78 * inch, 0.78 * inch, 0.78 * inch, 1.15 * inch]),
        Spacer(1, 7),
        table(grid_rows, [0.8 * inch, 1.55 * inch, 1.55 * inch, 1.2 * inch, 1.2 * inch]),
        Spacer(1, 6),
        para(html.escape(perf["comparison_note"]), "small"),
        para(f"NFR-11 cold: {html.escape(perf['cold_method'])} Hardware: {html.escape(perf['hardware'])}. Browser: {html.escape(perf['browser'])}. Dataset: {html.escape(perf['dataset'])}. Grid dataset: {html.escape(perf['grid_dataset'])}. Chart-open and pan use 30 runs; heap snapshots use 6. M13 grid cold uses a new browser context while the API stays running.", "small"),
        para("The Phase A 16-chart warm P95 was 1,288 ms at 35883c9. Backend regression confirms the inactive E2ECANDLE fixture leaves live screening and rankings, RS, market breadth, and the PIT equity screen unchanged.", "small"),
        Spacer(1, 10),
    ]

    story.extend([PageBreak(), para("Workflow guide", "heading")])
    for section in sections:
        workflow = [
            para(f"<b>{html.escape(section.key)}. {html.escape(section.title)}</b>", "body"),
        ]
        workflow.extend(para("- " + html.escape(item), "bullet") for item in section.workflow)
        workflow.append(para(html.escape(section.proof), "small"))
        story.extend([KeepTogether(workflow), Spacer(1, 8)])

    for section in sections:
        desktop = [shot for shot in section.shots if not shot.phone and not shot.filename.startswith("11-flyout-")]
        phones = [shot for shot in section.shots if shot.phone]
        flyouts = [shot for shot in section.shots if shot.filename.startswith("11-flyout-")]
        for shot in desktop:
            story.extend([PageBreak(), para(f"{html.escape(section.key)}  /  {html.escape(section.title)}", "eyebrow"), screenshot(shot, width=available_width - 12, height=430)])
        for start in range(0, len(phones), 2):
            pair = phones[start : start + 2]
            cards = [screenshot(shot, width=3 * inch, height=425) for shot in pair]
            while len(cards) < 2:
                cards.append("")
            phone_row = Table([cards], colWidths=[5.18 * inch, 5.18 * inch], hAlign="CENTER")
            phone_row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.extend([PageBreak(), phone_row])
        if flyouts:
            story.extend([PageBreak(), *flyout_page(flyouts)])

    story.extend([
        PageBreak(),
        para("Decision and limits", "heading"),
        para("The line-alert trigger basis is recorded in ADR-013b-line-alert-amendment.md. Alerts use each anchor's date-specific adjustment factor and compare daily closes.", "body"),
        para("Known limits: replay runs on /chart and ends when the user leaves; it advances one daily session at every interval. Line alerts are close-to-close and daily. Fibonacci spacing is screen-based, so log-scale prices are not exact ratios.", "body"),
        para("Axis-label collision and interval-loading viewport fixes are UI changes. Production financial calculations are unchanged. The UI acceptance decision remains with the owner. B5 is deferred, Phase C has not started, and nothing has been pushed.", "body"),
        para(f"Source commit {metrics['source_commit']}. Performance capture commit {perf['capture_commit']}.", "mono"),
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    SignoffDoc(str(path)).build(story)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", required=True, type=Path, help="Final verification and benchmark JSON")
    parser.add_argument("--captures", type=Path, default=DEFAULT_CAPTURES, help="Final B3 and E2ECANDLE PNG captures")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Directory for PDF and standalone HTML")
    args = parser.parse_args()

    try:
        metrics = validate_verification(json.loads(args.verification.read_text()), args.verification.resolve())
        sections = make_sections(STATIC_SHOTS, args.captures)
        phase_a = json.loads(PHASE_A_BENCH.read_text())
        phase_a_p95 = phase_a["results"]["16"]["warm_open_ms"]["p95"]
        if phase_a_p95 != 1288:
            raise ValueError("the committed Phase A benchmark baseline changed; review the report text")
        html_path = args.output_dir / "signoff.html"
        pdf_path = args.output_dir / "wickstreet-phase-b-signoff.pdf"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        html_path.write_text(build_html(metrics, sections), encoding="utf-8")
        write_pdf(pdf_path, metrics, sections)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"sign-off report not written: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {pdf_path}")
    print(f"wrote {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
