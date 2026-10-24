"""Live tax classification check (acceptance review R-01) against the served API.

Each case is a ₹10 lakh lump sum on real NAVs. The expected tax is derived here from
the gain the API reports and the dated rules, not from the service's tax code.
Usage: python3 tax-live.py [base URL] [output JSON]
"""

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CESS = 1.04
SLAB = 0.30
# (code, what it is, end date, explicit class or None, expected class)
CASES = [
    ("119517", "ABSL International Equity (overseas, filed as thematic)", "2024-07-25", None, None),
    ("119517", "ABSL International Equity, class chosen", "2024-07-25", "other", "other"),
    ("120186", "ICICI Pru US Bluechip (overseas, filed as thematic)", "2024-07-25", None, None),
    ("145552", "Motilal Oswal Nasdaq 100 FoF (filed as FoF Domestic)", "2024-07-25", None, None),
    ("120244", "ICICI Pru Banking & Financial Services (domestic thematic)", "2024-07-25", None, None),
    ("120716", "UTI Nifty 50 Index", "2024-07-25", None, None),
    ("122639", "Parag Parikh Flexi Cap, on the anniversary (A-03)", "2024-07-24", None, "equity"),
    ("122639", "Parag Parikh Flexi Cap, a day after", "2024-07-25", None, "equity"),
    ("118632", "Nippon India Large Cap", "2024-07-25", None, "equity"),
    ("120503", "Axis ELSS Tax Saver", "2024-07-25", None, "equity"),
    ("118987", "Debt fund (A-04 case)", "2024-07-25", None, "debt"),
]


def expected(cls: str | None, gain: float, end: str) -> float | None:
    """Tax on one lot bought 2023-07-24 and sold on ``end`` (FY2024-25, after 23 Jul 2024)."""
    if cls is None:
        return None
    if cls == "equity":
        if end <= "2024-07-24":  # not over 12 months: short term at 20%
            return gain * 0.20 * CESS
        return max(0.0, gain - 125_000) * 0.125 * CESS
    # Debt bought from April 2023 and overseas/other units under section 50AA: slab.
    return gain * SLAB * CESS


def run(code: str, end: str, cls: str | None) -> dict:
    body = {"code": code, "amount": 1_000_000, "start": "2023-07-24", "end": end, "slab_rate": SLAB}
    if cls:
        body["tax_class"] = cls
    req = urllib.request.Request(
        f"{BASE}/api/v1/mf/calculators/lumpsum",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "Origin": BASE},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


results = []
for code, name, end, cls, want_cls in CASES:
    d = run(code, end, cls)
    gain = d["summary"]["gain"]
    want = expected(want_cls, gain, end)
    got = d["tax"]["total"]
    ok = d["tax"]["tax_class"] == want_cls and (
        (want is None and got is None and d["tax"]["reason"] == "tax_class_needed")
        or (want is not None and got is not None and abs(got - want) < 0.01)
    )
    results.append(
        {"code": code, "fund": name, "end": end, "class_sent": cls, "gain": gain,
         "class": d["tax"]["tax_class"], "reason": d["tax"]["reason"], "tax": got,
         "expected_class": want_cls, "expected_tax": want, "pass": ok}
    )
    shown = "class needed" if got is None else f"₹{got:,.2f}"
    print(f"{'PASS' if ok else 'FAIL'} {code} {end} {cls or 'auto':6} {shown:>14}  {name}")
if len(sys.argv) > 2:
    with open(sys.argv[2], "w") as f:
        json.dump({"base": BASE, "slab_rate": SLAB, "results": results}, f, indent=2)
sys.exit(0 if all(r["pass"] for r in results) else 1)
