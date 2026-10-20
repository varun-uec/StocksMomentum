"""Black-box API probe: concurrency, validation, Host/Origin/CORS, traversal, injection.

Runs against the round3 audit API only (loopback, restored copy). Stdlib only.
Usage: python probe.py http://127.0.0.1:65481
"""
import concurrent.futures as cf
import http.client
import json
import sys
import time
from urllib.parse import urlsplit

BASE = sys.argv[1]
HOST = urlsplit(BASE).netloc
results = []


def req(method, path, body=None, headers=None, raw=None):
    c = http.client.HTTPConnection(HOST, timeout=300)
    h = {"Host": HOST}
    if body is not None:
        raw = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    for k, v in h.items():
        c.putheader(k, v)
    c.putheader("Content-Length", str(len(raw or b"")))
    c.endheaders()
    if raw:
        c.send(raw)
    r = c.getresponse()
    data = r.read()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, data.decode(errors="replace")


def check(name, ok, detail):
    results.append({"check": name, "pass": bool(ok), "detail": str(detail)[:300]})


DOCS = {
    "workspaces/r3probe": {"charts": {}},
    "drawings/R3PROBE": {"drawings": []},
    "screens/r3probe": {"screens": []},
}

# ---- optimistic concurrency ----
for path, body in DOCS.items():
    url = f"/api/v1/{path}"
    s, h, b = req("PUT", url, body=body)
    check(f"{path}: PUT without precondition -> 428", s == 428, s)
    s, h, b = req("PUT", url, body=body, headers={"If-None-Match": "*"})
    check(f"{path}: create with If-None-Match:* -> 201", s == 201, (s, h.get("etag"), b))
    s, h, b = req("PUT", url, body=body, headers={"If-None-Match": "*"})
    check(f"{path}: second create -> 412", s == 412, s)
    s, h, b = req("PUT", url, body=body, headers={"If-Match": "garbage"})
    check(f"{path}: malformed If-Match -> 412", s == 412, s)
    with cf.ThreadPoolExecutor(10) as ex:
        codes = list(ex.map(lambda _: req("PUT", url, body=body, headers={"If-Match": '"1"'})[0], range(10)))
    check(f"{path}: 10 concurrent PUT If-Match 1 -> one 200, nine 412",
          codes.count(200) == 1 and codes.count(412) == 9, sorted(codes))
    s, h, b = req("GET", url)
    check(f"{path}: final revision 2", s == 200 and json.loads(b)["revision"] == 2, (s, h.get("etag")))
    s, h, b = req("PUT", url, body={**body, "unknown_field": 1}, headers={"If-Match": '"2"'})
    check(f"{path}: unknown field -> 422 (strict schema)", s == 422, s)

# ---- oversized / malformed bodies ----
big = b'{"drawings":[' + b",".join([b'{"tool":"text","points":[{"t":"2026-01-01","p":1}],"text":"' + b"x" * 190 + b'"}'] * 60000) + b"]}"
t = time.time()
s, h, b = req("PUT", "/api/v1/drawings/R3PROBE", raw=big, headers={"Content-Type": "application/json", "If-Match": '"2"'})
check(f"{len(big)//1_000_000} MB drawings body -> 4xx, not 5xx", 400 <= s < 500, (s, round(time.time() - t, 2), b[:100]))
s, h, b = req("PUT", "/api/v1/workspaces/r3probe", raw=b"{not json", headers={"Content-Type": "application/json", "If-Match": '"2"'})
check("malformed JSON -> 422", s == 422, s)
s, h, b = req("POST", "/api/v1/alerts", raw=b'{"symbol": 1e999}', headers={"Content-Type": "application/json"})
check("non-finite number in alert body -> 4xx", 400 <= s < 500, (s, b[:160]))

# ---- parameter validation ----
for path, want in [
    ("/api/v1/runs?limit=0", 422), ("/api/v1/runs?limit=100000", 422), ("/api/v1/runs?offset=-1", 422),
    ("/api/v1/runs/abc", 422), ("/api/v1/runs/999999999", 404), ("/api/v1/runs/99999999999999999999999", 422),
    ("/api/v1/stocks/NOPE_X/live", 404), ("/api/v1/securities/RELIANCE/ohlcv?interval=7X", 422),
    ("/api/v1/stocks/RELIANCE/indicators/series?as_of=2026-13-45", 422),
    ("/api/v1/stocks/RELIANCE/indicators/series?as_of=2031-01-01", None),
    ("/api/v1/strategies/does_not_exist", 404), ("/api/v1/rankings/runs/149/stocks/abc/explanation", 422),
    ("/api/v1/validation/historical/minervini_trend_template?start=2026-01-01&end=2025-01-01", None),
    ("/api/v1/indices/NIFTY500/closes?start=2026-12-01&end=2026-01-01", None),
]:
    s, h, b = req("GET", path)
    ok = (s == want) if want else (s < 500)
    check(f"GET {path} -> {want or '<500'}", ok, (s, b[:160]))

# ---- SQL injection / XSS reflection ----
for sym in ["RELIANCE'%20OR%20'1'='1", "RELIANCE%3B%20DROP%20TABLE%20securities%3B--", "%3Cscript%3Ealert(1)%3C%2Fscript%3E"]:
    s, h, b = req("GET", f"/api/v1/stocks/{sym}/live")
    check(f"symbol injection {sym[:30]} -> 4xx JSON, no reflection as HTML",
          400 <= s < 500 and "html" not in h.get("content-type", ""), (s, h.get("content-type"), b[:160]))
s, h, b = req("GET", "/api/v1/securities?q=%27%20OR%201%3D1--&limit=5")
check("search q with SQL metachars -> <500", s < 500, (s, b[:160]))
s, h, b = req("GET", "/api/v1/strategies/x%27%20OR%20%271%27%3D%271")
check("strategy name injection -> 404", s == 404, s)

# ---- path traversal on SPA/static and API ----
for p in ["/..%2f..%2f.env", "/%2e%2e/%2e%2e/.env", "/static/../../.env", "/.env", "/../backend/.env",
          "/assets/..%2f..%2f..%2fetc%2fpasswd", "/api/v1/stocks/..%2f..%2fetc%2fpasswd/live", "/alembic.ini"]:
    s, h, b = req("GET", p)
    leak = "POSTGRES" in b or "root:" in b or "sqlalchemy.url" in b
    check(f"traversal {p} -> no file leak", not leak, (s, h.get("content-type"), b[:80]))

# ---- Host / Origin / CORS ----
s, h, b = req("GET", "/api/v1/health", headers={"Host": "evil.example"})
check("hostile Host -> rejected (4xx)", 400 <= s < 500, s)
s, h, b = req("PUT", "/api/v1/workspaces/r3probe", body={"charts": {}}, headers={"Origin": "http://evil.example", "If-Match": '"2"'})
check("cross-origin PUT -> 403", s == 403, s)
s, h, b = req("POST", "/api/v1/alerts", raw=b'{"symbol":"RELIANCE"}', headers={"Origin": "null", "Content-Type": "text/plain"})
check("Origin null + text/plain POST (form CSRF) -> 403", s == 403, s)
s, h, b = req("POST", "/api/v1/alerts", raw=b'{"symbol":"RELIANCE"}', headers={"Content-Type": "text/plain"})
check("no Origin + text/plain POST -> not 2xx (JSON content type required)", not (200 <= s < 300), (s, b[:160]))
s, h, b = req("OPTIONS", "/api/v1/workspaces/r3probe", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "PUT"})
check("CORS preflight from evil origin -> no ACAO", "access-control-allow-origin" not in h, (s, h.get("access-control-allow-origin")))
s, h, b = req("GET", "/api/v1/health")
sec = {k: h.get(k) for k in ("x-content-type-options", "x-frame-options", "content-security-policy", "referrer-policy")}
check("security headers present", all(sec.values()), sec)
s, h, b = req("GET", "/api/v1/nonexistent")
check("unknown API path -> JSON 404", s == 404 and "json" in h.get("content-type", ""), (s, h.get("content-type")))
s, h, b = req("DELETE", "/api/v1/health")
check("wrong method -> 405", s == 405, s)
s, h, b = req("GET", "/openapi.json")
check("openapi exposed on loopback (informational)", True, s)

print(json.dumps(results, indent=1))
print("FAILED:", [r["check"] for r in results if r["pass"] is False])
