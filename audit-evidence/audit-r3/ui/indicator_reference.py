"""Independent reference values for the browser-side indicators.

Pure Python, no imports from the app. Written from the textbook definitions.
It writes web/src/lib/indicators/golden-fixture.json (bars + expected series).
Run: python3 indicator_reference.py <output.json>
"""
import json
import math
import sys


def make_bars(count=300):
    bars, price, seed = [], 100.0, 7
    for i in range(count):
        seed = (seed * 1103515245 + 12345) % 2147483648
        drift = (seed / 2147483648 - 0.47) * 4
        price = max(5.0, price + drift)
        high = round(price + abs(drift) + 0.6, 4)
        low = round(max(0.5, price - abs(drift) - 0.6), 4)
        close = round(price, 4)
        open_ = round((high + low) / 2 + drift * 0.1, 4)
        seed = (seed * 1103515245 + 12345) % 2147483648
        vol = 100000 + seed % 900000
        bars.append(dict(date=f"d{i:04d}", open=open_, high=high, low=low, close=close, volume=vol))
    return bars


def sma(v, p):
    return [None if i < p - 1 else sum(v[i - p + 1:i + 1]) / p for i in range(len(v))]


def ema(v, p):
    out = [None] * len(v)
    if len(v) < p:
        return out
    k = 2 / (p + 1)
    prev = sum(v[:p]) / p
    out[p - 1] = prev
    for i in range(p, len(v)):
        prev = v[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def wma(v, p):
    w = list(range(1, p + 1))
    return [None if i < p - 1 else sum(a * b for a, b in zip(v[i - p + 1:i + 1], w)) / sum(w) for i in range(len(v))]


def pstdev(v, p):
    out = []
    for i in range(len(v)):
        if i < p - 1:
            out.append(None)
            continue
        w = v[i - p + 1:i + 1]
        m = sum(w) / p
        out.append(math.sqrt(sum((x - m) ** 2 for x in w) / p))
    return out


def true_range(b):
    return [None] + [max(b[i]["high"] - b[i]["low"], abs(b[i]["high"] - b[i - 1]["close"]), abs(b[i]["low"] - b[i - 1]["close"])) for i in range(1, len(b))]


def atr(b, p):
    tr = true_range(b)
    out = [None] * len(b)
    prev = sum(tr[1:p + 1]) / p
    out[p] = prev
    for i in range(p + 1, len(b)):
        prev = (prev * (p - 1) + tr[i]) / p
        out[i] = prev
    return out


def rsi(b, p):
    c = [x["close"] for x in b]
    out = [None] * len(c)
    g = sum(max(c[i] - c[i - 1], 0) for i in range(1, p + 1)) / p
    l = sum(max(c[i - 1] - c[i], 0) for i in range(1, p + 1)) / p
    f = lambda g, l: 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    out[p] = f(g, l)
    for i in range(p + 1, len(c)):
        d = c[i] - c[i - 1]
        g = (g * (p - 1) + max(d, 0)) / p
        l = (l * (p - 1) + max(-d, 0)) / p
        out[i] = f(g, l)
    return out


def main(path):
    b = make_bars()
    c = [x["close"] for x in b]
    h = [x["high"] for x in b]
    lo = [x["low"] for x in b]
    vol = [x["volume"] for x in b]
    n = len(b)
    e = {}
    e["sma20"] = sma(c, 20)
    e["ema20"] = ema(c, 20)
    e["wma20"] = wma(c, 20)
    mid, sd = sma(c, 20), pstdev(c, 20)
    e["bb_upper"] = [None if m is None else m + 2 * s for m, s in zip(mid, sd)]
    e["bb_lower"] = [None if m is None else m - 2 * s for m, s in zip(mid, sd)]
    a14 = atr(b, 14)
    e["atr14"] = a14
    e["atr_pct14"] = [None if a is None else a / c[i] * 100 for i, a in enumerate(a14)]
    rh = lambda v, p, f: [None if i < p - 1 else f(v[i - p + 1:i + 1]) for i in range(n)]
    e["donchian_high20"] = rh(h, 20, max)
    e["donchian_low20"] = rh(lo, 20, min)
    k10, a10, e20 = None, atr(b, 10), ema(c, 20)
    e["keltner_upper"] = [None if m is None or a is None else m + 2 * a for m, a in zip(e20, a10)]
    e["rsi14"] = rsi(b, 14)
    hh, ll = rh(h, 14, max), rh(lo, 14, min)
    k = [None if hh[i] is None else (50.0 if hh[i] == ll[i] else (c[i] - ll[i]) / (hh[i] - ll[i]) * 100) for i in range(n)]
    e["stoch_k14"] = k
    e["stoch_d3"] = [None if i < 13 + 2 else sum(k[i - 2:i + 1]) / 3 for i in range(n)]
    e["williams14"] = [None if hh[i] is None else (hh[i] - c[i]) / (hh[i] - ll[i]) * -100 for i in range(n)]
    tp = [(h[i] + lo[i] + c[i]) / 3 for i in range(n)]
    m20 = sma(tp, 20)
    e["cci20"] = [None if m is None else (tp[i] - m) / (0.015 * (sum(abs(x - m) for x in tp[i - 19:i + 1]) / 20)) for i, m in enumerate(m20)]
    e["roc12"] = [None if i < 12 else (c[i] - c[i - 12]) / c[i - 12] * 100 for i in range(n)]
    obv, acc = [0], 0
    for i in range(1, n):
        acc += vol[i] if c[i] > c[i - 1] else -vol[i] if c[i] < c[i - 1] else 0
        obv.append(acc)
    e["obv"] = obv
    mfv = [0 if h[i] == lo[i] else ((c[i] - lo[i]) - (h[i] - c[i])) / (h[i] - lo[i]) * vol[i] for i in range(n)]
    e["cmf20"] = [None if i < 19 else sum(mfv[i - 19:i + 1]) / sum(vol[i - 19:i + 1]) for i in range(n)]
    mfi = [None] * n
    for i in range(14, n):
        pos = sum(tp[j] * vol[j] for j in range(i - 13, i + 1) if tp[j] > tp[j - 1])
        neg = sum(tp[j] * vol[j] for j in range(i - 13, i + 1) if tp[j] < tp[j - 1])
        mfi[i] = 100.0 if neg == 0 else 100 - 100 / (1 + pos / neg)
    e["mfi14"] = mfi
    # Wilder directional indicators
    pdm, mdm = [0.0] * n, [0.0] * n
    for i in range(1, n):
        up, dn = h[i] - h[i - 1], lo[i - 1] - lo[i]
        pdm[i] = up if up > dn and up > 0 else 0.0
        mdm[i] = dn if dn > up and dn > 0 else 0.0
    sp, sm = sum(pdm[1:15]), sum(mdm[1:15])
    pdi, mdi = [None] * n, [None] * n
    pdi[14], mdi[14] = 100 * (sp / 14) / a14[14], 100 * (sm / 14) / a14[14]
    for i in range(15, n):
        sp, sm = sp - sp / 14 + pdm[i], sm - sm / 14 + mdm[i]
        pdi[i], mdi[i] = 100 * (sp / 14) / a14[i], 100 * (sm / 14) / a14[i]
    e["plus_di14"], e["minus_di14"] = pdi, mdi
    f, s = ema(c, 12), ema(c, 26)
    line = [None if x is None or y is None else x - y for x, y in zip(f, s)]
    st = next(i for i, v in enumerate(line) if v is not None)
    sig = [None] * n
    for i, v in enumerate(ema(line[st:], 9)):
        sig[st + i] = v
    e["macd"] = line
    e["macd_signal"] = sig
    e["macd_hist"] = [None if x is None or y is None else x - y for x, y in zip(line, sig)]
    th, tl = rh(h, 9, max), rh(lo, 9, min)
    kh, kl = rh(h, 26, max), rh(lo, 26, min)
    e["ichimoku_tenkan9"] = [None if x is None else (x + y) / 2 for x, y in zip(th, tl)]
    e["ichimoku_kijun26"] = [None if x is None else (x + y) / 2 for x, y in zip(kh, kl)]
    json.dump({"bars": b, "expected": e}, open(path, "w"))


main(sys.argv[1])
