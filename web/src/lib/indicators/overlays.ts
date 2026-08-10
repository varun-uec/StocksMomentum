/**
 * Price-pane indicators, computed in the browser from the fetched OHLCV bars.
 *
 * The backend's per-bar series carries only RSI/ATR/ADX/MACD, so everything
 * here is arithmetic on bars the chart already shows — the same approach
 * `PriceChart`'s built-in moving averages already take. Pure functions, no
 * React, no I/O: same bars in, same points out.
 *
 * Every series is `null` until its warm-up window is full. Nothing is
 * extrapolated past the last bar.
 */

import type { OHLCVBarDTO } from '@/lib/types';

export interface Bar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** One drawn line: a label for the legend and a point per bar it is defined on. */
export interface OverlaySeries {
  label: string;
  color: string;
  dashed?: boolean;
  points: { date: string; price: number }[];
}

export type Params = Record<string, number | string>;

export function toBars(dtos: OHLCVBarDTO[]): Bar[] {
  return dtos.map((b) => ({
    date: b.date,
    open: parseFloat(b.open),
    high: parseFloat(b.high),
    low: parseFloat(b.low),
    close: parseFloat(b.close),
    volume: b.volume,
  }));
}

// ── Averages ───────────────────────────────────────────────────────────

/** Rolling simple mean; `null` until the window is full. */
export function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    out.push(i >= period - 1 ? sum / period : null);
  }
  return out;
}

/** Exponential mean seeded with the simple mean at index `period - 1`. */
export function ema(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (values.length < period || period < 1) return out;
  const k = 2 / (period + 1);
  let prev = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out[period - 1] = prev;
  for (let i = period; i < values.length; i += 1) {
    prev = values[i] * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

/** Linearly weighted mean, newest bar weighted `period`. */
export function wma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  const denom = (period * (period + 1)) / 2;
  for (let i = period - 1; i < values.length; i += 1) {
    let acc = 0;
    for (let j = 0; j < period; j += 1) acc += values[i - j] * (period - j);
    out[i] = acc / denom;
  }
  return out;
}

/** Rolling population standard deviation. */
export function stdev(values: number[], period: number): (number | null)[] {
  const means = sma(values, period);
  return means.map((mean, i) => {
    if (mean === null) return null;
    let acc = 0;
    for (let j = i - period + 1; j <= i; j += 1) acc += (values[j] - mean) ** 2;
    return Math.sqrt(acc / period);
  });
}

/** Wilder's true range per bar (the first bar has no previous close). */
export function trueRange(bars: Bar[]): (number | null)[] {
  return bars.map((b, i) => {
    if (i === 0) return null;
    const prev = bars[i - 1].close;
    return Math.max(b.high - b.low, Math.abs(b.high - prev), Math.abs(b.low - prev));
  });
}

/** Wilder-smoothed average true range. */
export function atr(bars: Bar[], period: number): (number | null)[] {
  const tr = trueRange(bars);
  const out: (number | null)[] = new Array(bars.length).fill(null);
  if (bars.length <= period) return out;
  let acc = 0;
  for (let i = 1; i <= period; i += 1) acc += tr[i] ?? 0;
  let prev = acc / period;
  out[period] = prev;
  for (let i = period + 1; i < bars.length; i += 1) {
    prev = (prev * (period - 1) + (tr[i] ?? 0)) / period;
    out[i] = prev;
  }
  return out;
}

export function rollingMax(values: number[], period: number): (number | null)[] {
  return values.map((_, i) =>
    i < period - 1 ? null : Math.max(...values.slice(i - period + 1, i + 1))
  );
}

export function rollingMin(values: number[], period: number): (number | null)[] {
  return values.map((_, i) =>
    i < period - 1 ? null : Math.min(...values.slice(i - period + 1, i + 1))
  );
}

// ── Helpers shared by the builders ─────────────────────────────────────

function line(
  bars: Bar[],
  values: (number | null)[],
  label: string,
  color: string,
  dashed = false
): OverlaySeries {
  const points: { date: string; price: number }[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    const v = values[i];
    if (v !== null && v !== undefined && Number.isFinite(v)) {
      points.push({ date: bars[i].date, price: v });
    }
  }
  return { label, color, dashed, points };
}

/** A flat level spanning the whole loaded range. */
function level(bars: Bar[], price: number, label: string, color: string, dashed = true): OverlaySeries {
  if (bars.length === 0 || !Number.isFinite(price)) return { label, color, dashed, points: [] };
  return {
    label,
    color,
    dashed,
    points: [
      { date: bars[0].date, price },
      { date: bars[bars.length - 1].date, price },
    ],
  };
}

const n = (p: Params, key: string, fallback: number): number => {
  const v = Number(p[key]);
  return Number.isFinite(v) && v > 0 ? v : fallback;
};

const closes = (bars: Bar[]) => bars.map((b) => b.close);
const typical = (b: Bar) => (b.high + b.low + b.close) / 3;

// ── Overlay builders ───────────────────────────────────────────────────

export function smaOverlay(bars: Bar[], p: Params): OverlaySeries[] {
  const period = n(p, 'period', 20);
  return [line(bars, sma(closes(bars), period), `SMA ${period}`, '#0ea5e9')];
}

export function emaOverlay(bars: Bar[], p: Params): OverlaySeries[] {
  const period = n(p, 'period', 21);
  return [line(bars, ema(closes(bars), period), `EMA ${period}`, '#f97316')];
}

export function wmaOverlay(bars: Bar[], p: Params): OverlaySeries[] {
  const period = n(p, 'period', 20);
  return [line(bars, wma(closes(bars), period), `WMA ${period}`, '#14b8a6')];
}

export function bollinger(bars: Bar[], p: Params): OverlaySeries[] {
  const period = n(p, 'period', 20);
  const k = Number(p.k ?? 2);
  const c = closes(bars);
  const mid = sma(c, period);
  const sd = stdev(c, period);
  const band = (sign: number) => mid.map((m, i) => (m === null || sd[i] === null ? null : m + sign * k * sd[i]!));
  return [
    line(bars, band(1), `Bollinger upper (${period}, ${k}σ)`, '#8b5cf6'),
    line(bars, mid, `Bollinger mid (SMA ${period})`, '#8b5cf6', true),
    line(bars, band(-1), `Bollinger lower (${period}, ${k}σ)`, '#8b5cf6'),
  ];
}

export function keltner(bars: Bar[], p: Params): OverlaySeries[] {
  const emaPeriod = n(p, 'emaPeriod', 20);
  const atrPeriod = n(p, 'atrPeriod', 10);
  const mult = Number(p.mult ?? 2);
  const mid = ema(closes(bars), emaPeriod);
  const a = atr(bars, atrPeriod);
  const band = (sign: number) => mid.map((m, i) => (m === null || a[i] === null ? null : m + sign * mult * a[i]!));
  return [
    line(bars, band(1), `Keltner upper (EMA ${emaPeriod}, ${mult}×ATR ${atrPeriod})`, '#22c55e'),
    line(bars, mid, `Keltner mid (EMA ${emaPeriod})`, '#22c55e', true),
    line(bars, band(-1), `Keltner lower (EMA ${emaPeriod}, ${mult}×ATR ${atrPeriod})`, '#22c55e'),
  ];
}

export function donchian(bars: Bar[], p: Params): OverlaySeries[] {
  const period = n(p, 'period', 20);
  const up = rollingMax(bars.map((b) => b.high), period);
  const dn = rollingMin(bars.map((b) => b.low), period);
  const mid = up.map((u, i) => (u === null || dn[i] === null ? null : (u + dn[i]!) / 2));
  return [
    line(bars, up, `Donchian high (${period}d)`, '#ef4444'),
    line(bars, mid, `Donchian mid (${period}d)`, '#ef4444', true),
    line(bars, dn, `Donchian low (${period}d)`, '#ef4444'),
  ];
}

export function ichimoku(bars: Bar[], p: Params): OverlaySeries[] {
  const tenkanP = n(p, 'tenkan', 9);
  const kijunP = n(p, 'kijun', 26);
  const senkouP = n(p, 'senkou', 52);
  const mid = (period: number) => {
    const hi = rollingMax(bars.map((b) => b.high), period);
    const lo = rollingMin(bars.map((b) => b.low), period);
    return hi.map((h, i) => (h === null || lo[i] === null ? null : (h + lo[i]!) / 2));
  };
  const tenkan = mid(tenkanP);
  const kijun = mid(kijunP);
  const senkouA = tenkan.map((t, i) => (t === null || kijun[i] === null ? null : (t + kijun[i]!) / 2));
  const senkouB = mid(senkouP);
  // Chikou is the close plotted `kijun` bars back — a past date, so it draws.
  // Senkou A/B are drawn unshifted: their forward projection would need dates
  // the loaded series does not have, and no bar may be invented.
  const chikou: (number | null)[] = bars.map((_, i) =>
    i + kijunP < bars.length ? bars[i + kijunP].close : null
  );
  return [
    line(bars, tenkan, `Tenkan-sen (${tenkanP})`, '#0ea5e9'),
    line(bars, kijun, `Kijun-sen (${kijunP})`, '#ef4444'),
    line(bars, senkouA, `Senkou A (unshifted)`, '#22c55e', true),
    line(bars, senkouB, `Senkou B (${senkouP}, unshifted)`, '#f59e0b', true),
    line(bars, chikou, `Chikou (close ${kijunP}d back)`, '#94a3b8', true),
  ];
}

export function supertrend(bars: Bar[], p: Params): OverlaySeries[] {
  const period = n(p, 'atrPeriod', 10);
  const mult = Number(p.mult ?? 3);
  const a = atr(bars, period);
  const out: (number | null)[] = new Array(bars.length).fill(null);
  let upper = Number.POSITIVE_INFINITY;
  let lower = Number.NEGATIVE_INFINITY;
  let uptrend = true;
  for (let i = 0; i < bars.length; i += 1) {
    if (a[i] === null) continue;
    const mid = (bars[i].high + bars[i].low) / 2;
    const basicUpper = mid + mult * a[i]!;
    const basicLower = mid - mult * a[i]!;
    const prevClose = bars[i - 1]?.close ?? bars[i].close;
    upper = basicUpper < upper || prevClose > upper ? basicUpper : upper;
    lower = basicLower > lower || prevClose < lower ? basicLower : lower;
    if (out[i - 1] === null) uptrend = bars[i].close >= basicLower;
    else if (uptrend && bars[i].close < lower) uptrend = false;
    else if (!uptrend && bars[i].close > upper) uptrend = true;
    out[i] = uptrend ? lower : upper;
  }
  return [line(bars, out, `Supertrend (ATR ${period}, ${mult}×)`, '#f43f5e')];
}

export function parabolicSar(bars: Bar[], p: Params): OverlaySeries[] {
  const step = Number(p.step ?? 0.02);
  const max = Number(p.max ?? 0.2);
  const out: (number | null)[] = new Array(bars.length).fill(null);
  if (bars.length < 2) return [line(bars, out, 'Parabolic SAR', '#eab308')];
  let uptrend = bars[1].close >= bars[0].close;
  let sar = uptrend ? bars[0].low : bars[0].high;
  let extreme = uptrend ? bars[0].high : bars[0].low;
  let accel = step;
  for (let i = 1; i < bars.length; i += 1) {
    sar += accel * (extreme - sar);
    if (uptrend) {
      sar = Math.min(sar, bars[i - 1].low, bars[Math.max(0, i - 2)].low);
      if (bars[i].low < sar) {
        uptrend = false;
        sar = extreme;
        extreme = bars[i].low;
        accel = step;
      } else if (bars[i].high > extreme) {
        extreme = bars[i].high;
        accel = Math.min(max, accel + step);
      }
    } else {
      sar = Math.max(sar, bars[i - 1].high, bars[Math.max(0, i - 2)].high);
      if (bars[i].high > sar) {
        uptrend = true;
        sar = extreme;
        extreme = bars[i].high;
        accel = step;
      } else if (bars[i].low < extreme) {
        extreme = bars[i].low;
        accel = Math.min(max, accel + step);
      }
    }
    out[i] = sar;
  }
  return [line(bars, out, `Parabolic SAR (${step}, ${max})`, '#eab308')];
}

/** Cumulative volume-weighted typical price from `anchorIndex` onward. */
export function anchoredVwapValues(bars: Bar[], anchorIndex: number): (number | null)[] {
  const out: (number | null)[] = new Array(bars.length).fill(null);
  let pv = 0;
  let vol = 0;
  let count = 0;
  let tpSum = 0;
  for (let i = Math.max(0, anchorIndex); i < bars.length; i += 1) {
    const tp = typical(bars[i]);
    pv += tp * bars[i].volume;
    vol += bars[i].volume;
    tpSum += tp;
    count += 1;
    // A stretch of zero-volume bars must not produce NaN: fall back to the
    // unweighted mean typical price, which is what VWAP degenerates to.
    out[i] = vol > 0 ? pv / vol : tpSum / count;
  }
  return out;
}

function anchorIndexFor(bars: Bar[], anchor: unknown): number {
  if (typeof anchor === 'string' && anchor) {
    const i = bars.findIndex((b) => b.date >= anchor);
    if (i >= 0) return i;
  }
  return 0;
}

export function anchoredVwap(bars: Bar[], p: Params): OverlaySeries[] {
  const i = anchorIndexFor(bars, p.anchor);
  const from = bars[i]?.date ?? '—';
  return [line(bars, anchoredVwapValues(bars, i), `Anchored VWAP (from ${from})`, '#06b6d4')];
}

export function anchoredVwapBands(bars: Bar[], p: Params): OverlaySeries[] {
  const i0 = anchorIndexFor(bars, p.anchor);
  const k = Number(p.k ?? 1);
  const vwap = anchoredVwapValues(bars, i0);
  const from = bars[i0]?.date ?? '—';
  const upper: (number | null)[] = new Array(bars.length).fill(null);
  const lower: (number | null)[] = new Array(bars.length).fill(null);
  let acc = 0;
  let count = 0;
  for (let i = i0; i < bars.length; i += 1) {
    const v = vwap[i];
    if (v === null) continue;
    acc += (typical(bars[i]) - v) ** 2;
    count += 1;
    const sd = Math.sqrt(acc / count);
    upper[i] = v + k * sd;
    lower[i] = v - k * sd;
  }
  return [
    line(bars, upper, `Anchored VWAP +${k}σ (from ${from})`, '#06b6d4', true),
    line(bars, lower, `Anchored VWAP −${k}σ (from ${from})`, '#06b6d4', true),
  ];
}

export function rollingVwap(bars: Bar[], p: Params): OverlaySeries[] {
  const period = n(p, 'period', 20);
  const out: (number | null)[] = new Array(bars.length).fill(null);
  for (let i = period - 1; i < bars.length; i += 1) {
    let pv = 0;
    let vol = 0;
    let tp = 0;
    for (let j = i - period + 1; j <= i; j += 1) {
      pv += typical(bars[j]) * bars[j].volume;
      vol += bars[j].volume;
      tp += typical(bars[j]);
    }
    out[i] = vol > 0 ? pv / vol : tp / period;
  }
  return [line(bars, out, `Rolling VWAP (${period}d)`, '#3b82f6')];
}

/** Classic floor-trader pivots over the prior calendar week or month. */
export function pivotPoints(bars: Bar[], p: Params): OverlaySeries[] {
  const scale = String(p.scale ?? 'weekly');
  const key = (date: string) => {
    const d = new Date(`${date}T00:00:00Z`);
    if (scale === 'monthly') return date.slice(0, 7);
    const day = d.getUTCDay();
    const monday = new Date(d);
    monday.setUTCDate(d.getUTCDate() - ((day + 6) % 7));
    return monday.toISOString().slice(0, 10);
  };
  // The prior completed period, so nothing uses a bar from the current one.
  const groups = new Map<string, Bar[]>();
  for (const b of bars) {
    const k = key(b.date);
    const list = groups.get(k) ?? [];
    list.push(b);
    groups.set(k, list);
  }
  const keys = Array.from(groups.keys()).sort();
  if (keys.length < 2) return [];
  const prior = groups.get(keys[keys.length - 2])!;
  const high = Math.max(...prior.map((b) => b.high));
  const low = Math.min(...prior.map((b) => b.low));
  const close = prior[prior.length - 1].close;
  const pivot = (high + low + close) / 3;
  const label = scale === 'monthly' ? 'monthly' : 'weekly';
  const suffix = `prior ${label} H/L/C`;
  return [
    level(bars, pivot + (high - low), `R2 (${suffix})`, '#f472b6'),
    level(bars, 2 * pivot - low, `R1 (${suffix})`, '#f472b6'),
    level(bars, pivot, `Pivot (${suffix})`, '#f472b6', false),
    level(bars, 2 * pivot - high, `S1 (${suffix})`, '#f472b6'),
    level(bars, pivot - (high - low), `S2 (${suffix})`, '#f472b6'),
  ];
}

export function highLow52w(bars: Bar[], p: Params): OverlaySeries[] {
  const sessions = n(p, 'sessions', 252);
  const window = bars.slice(-sessions);
  if (window.length === 0) return [];
  const high = Math.max(...window.map((b) => b.high));
  const low = Math.min(...window.map((b) => b.low));
  return [
    level(bars, high, `${window.length}-session high`, '#10b981'),
    level(bars, low, `${window.length}-session low`, '#ef4444'),
  ];
}

/** Least-squares fit over the last `lookback` closes, with ±k σ of residuals. */
export function linearRegressionChannel(bars: Bar[], p: Params): OverlaySeries[] {
  const lookback = Math.min(n(p, 'lookback', 100), bars.length);
  const k = Number(p.k ?? 2);
  if (lookback < 2) return [];
  const start = bars.length - lookback;
  const window = bars.slice(start);
  const meanX = (lookback - 1) / 2;
  const meanY = window.reduce((a, b) => a + b.close, 0) / lookback;
  let num = 0;
  let den = 0;
  window.forEach((b, i) => {
    num += (i - meanX) * (b.close - meanY);
    den += (i - meanX) ** 2;
  });
  const slope = den === 0 ? 0 : num / den;
  const fit = (i: number) => meanY + slope * (i - meanX);
  const sd = Math.sqrt(window.reduce((a, b, i) => a + (b.close - fit(i)) ** 2, 0) / lookback);
  const project = (offset: number, label: string, dashed: boolean, color: string): OverlaySeries => ({
    label,
    color,
    dashed,
    points: [
      { date: window[0].date, price: fit(0) + offset },
      { date: window[lookback - 1].date, price: fit(lookback - 1) + offset },
    ],
  });
  return [
    project(k * sd, `Regression +${k}σ (${lookback}d)`, true, '#a78bfa'),
    project(0, `Regression mid (${lookback}d)`, false, '#a78bfa'),
    project(-k * sd, `Regression −${k}σ (${lookback}d)`, true, '#a78bfa'),
  ];
}

/** Fractal swing pivots: a bar whose high (low) tops `strength` bars each side. */
export function swingPivots(
  bars: Bar[],
  strength: number
): { index: number; date: string; price: number; kind: 'H' | 'L' }[] {
  const out: { index: number; date: string; price: number; kind: 'H' | 'L' }[] = [];
  for (let i = strength; i < bars.length - strength; i += 1) {
    const window = bars.slice(i - strength, i + strength + 1);
    if (bars[i].high === Math.max(...window.map((b) => b.high))) {
      out.push({ index: i, date: bars[i].date, price: bars[i].high, kind: 'H' });
    }
    if (bars[i].low === Math.min(...window.map((b) => b.low))) {
      out.push({ index: i, date: bars[i].date, price: bars[i].low, kind: 'L' });
    }
  }
  return out;
}

export function priorSwingLevels(bars: Bar[], p: Params): OverlaySeries[] {
  const strength = n(p, 'strength', 5);
  const pivots = swingPivots(bars, strength);
  const lastHigh = [...pivots].reverse().find((x) => x.kind === 'H');
  const lastLow = [...pivots].reverse().find((x) => x.kind === 'L');
  const out: OverlaySeries[] = [];
  if (lastHigh) out.push(level(bars, lastHigh.price, `Prior swing high (${lastHigh.date})`, '#10b981'));
  if (lastLow) out.push(level(bars, lastLow.price, `Prior swing low (${lastLow.date})`, '#ef4444'));
  return out;
}
