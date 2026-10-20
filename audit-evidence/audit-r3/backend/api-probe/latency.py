"""Repeated API latency percentiles on the restored real-data copy (R2-LIMIT-04, backend side)."""
import http.client
import json
import statistics
import sys
import time
from urllib.parse import urlsplit

HOST = urlsplit(sys.argv[1]).netloc


def call(method, path, body=None, headers=None):
    c = http.client.HTTPConnection(HOST, timeout=600)
    h = {"Host": HOST, **(headers or {})}
    raw = None
    if body is not None:
        raw = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    t = time.perf_counter()
    c.request(method, path, body=raw, headers=h)
    r = c.getresponse()
    data = r.read()
    return (time.perf_counter() - t) * 1000, r.status, r.getheader("ETag"), data


def pct(xs, p):
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))
    return round(xs[k], 1)


def bench(name, n, fn):
    times, codes = [], set()
    for i in range(n):
        ms, code = fn(i)
        times.append(ms)
        codes.add(code)
    out = {"case": name, "n": n, "p50_ms": pct(times, 50), "p95_ms": pct(times, 95), "max_ms": round(max(times), 1), "status": sorted(codes)}
    print(json.dumps(out))


bench("search securities q=REL", 30, lambda i: call("GET", "/api/v1/securities?q=REL&limit=20")[:2])
bench("ohlcv RELIANCE 1D", 30, lambda i: call("GET", "/api/v1/securities/RELIANCE/ohlcv?interval=1D")[:2])
bench("ohlcv RELIANCE 1W", 30, lambda i: call("GET", "/api/v1/securities/RELIANCE/ohlcv?interval=1W")[:2])
bench("indicator series RELIANCE", 30, lambda i: call("GET", "/api/v1/stocks/RELIANCE/indicators/series")[:2])
bench("rankings latest completed run", 30, lambda i: call("GET", "/api/v1/runs/latest")[:2])
bench("rankings run 149", 30, lambda i: call("GET", "/api/v1/rankings/runs/149")[:2])
bench("workspace GET", 30, lambda i: call("GET", "/api/v1/workspaces/r3probe")[:2])
etag = {"v": call("GET", "/api/v1/workspaces/r3probe")[2]}


def put(i):
    ms, code, tag, _ = call("PUT", "/api/v1/workspaces/r3probe", {"charts": {}}, {"If-Match": etag["v"]})
    etag["v"] = tag or etag["v"]
    return ms, code


bench("workspace PUT (If-Match chain)", 30, put)
bench("stocks RELIANCE live (universe RS)", 10, lambda i: call("GET", "/api/v1/stocks/RELIANCE/live")[:2])
bench("alerts evaluate", 10, lambda i: call("POST", "/api/v1/alerts/evaluate", {})[:2])
