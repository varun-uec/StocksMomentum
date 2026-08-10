/**
 * Sub-pane indicators, computed in the browser from the fetched OHLCV bars.
 *
 * Each function returns one value array per pane field, aligned bar-for-bar
 * with the input. The analysis screen merges them into the same
 * `IndicatorSeriesBar[]` the backend fills, so a pane never cares where its
 * numbers came from.
 *
 * RSI, MACD, ADX and ATR are NOT here: those come from the backend series.
 * Stochastic, Williams %R, CCI, ROC and ±DI duplicate maths the backend also
 * does as a latest-value snapshot; `scripts/indicator-selfcheck.ts` and the
 * live-endpoint cross-check are the guard on that duplication.
 */

import { atr, ema, sma, type Bar, type CloseBar, type Params } from '@/lib/indicators/overlays';

export type PaneValues = Record<string, (number | null)[]>;

const n = (p: Params, key: string, fallback: number): number => {
  const v = Number(p[key]);
  return Number.isFinite(v) && v > 0 ? v : fallback;
};

const nulls = (len: number): (number | null)[] => new Array(len).fill(null);

/** Rolling extreme over `period`, `null` until the window is full. */
function extremes(bars: Bar[], period: number) {
  const hi = nulls(bars.length);
  const lo = nulls(bars.length);
  for (let i = period - 1; i < bars.length; i += 1) {
    const w = bars.slice(i - period + 1, i + 1);
    hi[i] = Math.max(...w.map((b) => b.high));
    lo[i] = Math.min(...w.map((b) => b.low));
  }
  return { hi, lo };
}

/** Simple mean of a series that may contain nulls, over `period` defined values. */
function smaOfNullable(values: (number | null)[], period: number): (number | null)[] {
  const out = nulls(values.length);
  for (let i = period - 1; i < values.length; i += 1) {
    const w = values.slice(i - period + 1, i + 1);
    if (w.some((v) => v === null)) continue;
    out[i] = (w as number[]).reduce((a, b) => a + b, 0) / period;
  }
  return out;
}

export function volumePane(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 20);
  return {
    volume: bars.map((b) => b.volume),
    // Sign key for the histogram's up/down colouring: an up-close day is green.
    volume_dir: bars.map((b) => (b.close >= b.open ? 1 : -1)),
    volume_sma: sma(bars.map((b) => b.volume), period),
  };
}

export function stochastic(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 14);
  // kSmooth defaults to 1 (no smoothing) so stoch_k is the FAST %K the backend
  // reports as stoch_k14, and stoch_d is its SMA(3) — backend's stoch_d14.
  // Raising kSmooth gives the slow stochastic, one smoothing pass deeper.
  const kSmooth = n(p, 'kSmooth', 1);
  const dSmooth = n(p, 'dSmooth', 3);
  const { hi, lo } = extremes(bars, period);
  const raw = bars.map((b, i) => {
    if (hi[i] === null || lo[i] === null) return null;
    const range = hi[i]! - lo[i]!;
    // A flat window has no position within its range; 50 is the neutral
    // convention and keeps the series inside [0, 100] instead of NaN.
    return range === 0 ? 50 : ((b.close - lo[i]!) / range) * 100;
  });
  const k = smaOfNullable(raw, kSmooth);
  return { stoch_k: k, stoch_d: smaOfNullable(k, dSmooth) };
}

/** Wilder RSI over closes — the input to Stochastic RSI. */
export function rsi(bars: Bar[], period: number): (number | null)[] {
  const out = nulls(bars.length);
  if (bars.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i += 1) {
    const diff = bars[i].close - bars[i - 1].close;
    if (diff >= 0) gain += diff;
    else loss -= diff;
  }
  gain /= period;
  loss /= period;
  out[period] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = period + 1; i < bars.length; i += 1) {
    const diff = bars[i].close - bars[i - 1].close;
    gain = (gain * (period - 1) + Math.max(0, diff)) / period;
    loss = (loss * (period - 1) + Math.max(0, -diff)) / period;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

export function stochRsi(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 14);
  const r = rsi(bars, period);
  const out = nulls(bars.length);
  for (let i = 0; i < bars.length; i += 1) {
    const w = r.slice(Math.max(0, i - period + 1), i + 1).filter((v): v is number => v !== null);
    if (w.length < period) continue;
    const hi = Math.max(...w);
    const lo = Math.min(...w);
    out[i] = hi === lo ? 50 : ((r[i]! - lo) / (hi - lo)) * 100;
  }
  return { stochrsi: out };
}

export function williamsR(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 14);
  const { hi, lo } = extremes(bars, period);
  return {
    williams_r: bars.map((b, i) => {
      if (hi[i] === null || lo[i] === null) return null;
      const range = hi[i]! - lo[i]!;
      return range === 0 ? -50 : ((hi[i]! - b.close) / range) * -100;
    }),
  };
}

export function cci(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 20);
  const tp = bars.map((b) => (b.high + b.low + b.close) / 3);
  const mean = sma(tp, period);
  return {
    cci: mean.map((m, i) => {
      if (m === null) return null;
      let dev = 0;
      for (let j = i - period + 1; j <= i; j += 1) dev += Math.abs(tp[j] - m);
      const mad = dev / period;
      return mad === 0 ? 0 : (tp[i] - m) / (0.015 * mad);
    }),
  };
}

export function roc(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 12);
  return {
    roc: bars.map((b, i) => {
      if (i < period) return null;
      const base = bars[i - period].close;
      return base === 0 ? null : ((b.close - base) / base) * 100;
    }),
  };
}

export function obv(bars: Bar[]): PaneValues {
  let acc = 0;
  return {
    obv: bars.map((b, i) => {
      if (i === 0) return 0;
      const diff = b.close - bars[i - 1].close;
      acc += diff > 0 ? b.volume : diff < 0 ? -b.volume : 0;
      return acc;
    }),
  };
}

export function chaikinMoneyFlow(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 20);
  const mfv = bars.map((b) => {
    const range = b.high - b.low;
    return range === 0 ? 0 : (((b.close - b.low) - (b.high - b.close)) / range) * b.volume;
  });
  const out = nulls(bars.length);
  for (let i = period - 1; i < bars.length; i += 1) {
    let flow = 0;
    let vol = 0;
    for (let j = i - period + 1; j <= i; j += 1) {
      flow += mfv[j];
      vol += bars[j].volume;
    }
    out[i] = vol === 0 ? 0 : flow / vol;
  }
  return { cmf: out };
}

export function moneyFlowIndex(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 14);
  const tp = bars.map((b) => (b.high + b.low + b.close) / 3);
  const out = nulls(bars.length);
  for (let i = period; i < bars.length; i += 1) {
    let pos = 0;
    let neg = 0;
    for (let j = i - period + 1; j <= i; j += 1) {
      const flow = tp[j] * bars[j].volume;
      if (tp[j] > tp[j - 1]) pos += flow;
      else if (tp[j] < tp[j - 1]) neg += flow;
    }
    out[i] = neg === 0 ? 100 : 100 - 100 / (1 + pos / neg);
  }
  return { mfi: out };
}

/** Wilder's directional indicators; ADX itself comes from the backend series. */
export function directionalIndicators(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 14);
  const a = atr(bars, period);
  const plusRaw = nulls(bars.length);
  const minusRaw = nulls(bars.length);
  let plusSum = 0;
  let minusSum = 0;
  for (let i = 1; i < bars.length; i += 1) {
    const up = bars[i].high - bars[i - 1].high;
    const down = bars[i - 1].low - bars[i].low;
    const plusDm = up > down && up > 0 ? up : 0;
    const minusDm = down > up && down > 0 ? down : 0;
    if (i <= period) {
      plusSum += plusDm;
      minusSum += minusDm;
    } else {
      plusSum = plusSum - plusSum / period + plusDm;
      minusSum = minusSum - minusSum / period + minusDm;
    }
    if (i >= period && a[i] !== null && a[i]! > 0) {
      plusRaw[i] = (100 * (plusSum / period)) / a[i]!;
      minusRaw[i] = (100 * (minusSum / period)) / a[i]!;
    }
  }
  return { plus_di: plusRaw, minus_di: minusRaw };
}

export function atrPane(bars: Bar[], p: Params): PaneValues {
  const period = n(p, 'period', 14);
  const a = atr(bars, period);
  return {
    atr_browser: a,
    atr_pct: a.map((v, i) => (v === null || bars[i].close === 0 ? null : (v / bars[i].close) * 100)),
  };
}

/**
 * Stock / benchmark close ratio, rebased to 100 at the first shared bar, plus
 * its 50-day mean. Bars are matched by date, so a holiday on either side is
 * skipped rather than mis-aligned.
 */
export function relativeStrength(
  bars: Bar[],
  benchmark: CloseBar[],
  p: Params
): PaneValues {
  const period = n(p, 'period', 50);
  const byDate = new Map(benchmark.map((b) => [b.date, b.close]));
  const ratio = nulls(bars.length);
  let base: number | null = null;
  for (let i = 0; i < bars.length; i += 1) {
    const index = byDate.get(bars[i].date);
    if (index === undefined || index === 0) continue;
    const r = bars[i].close / index;
    if (base === null) base = r;
    ratio[i] = (r / base) * 100;
  }
  const defined = ratio.filter((v): v is number => v !== null);
  const meansOfDefined = sma(defined, period);
  const mean = nulls(bars.length);
  let k = 0;
  for (let i = 0; i < ratio.length; i += 1) {
    if (ratio[i] === null) continue;
    mean[i] = meansOfDefined[k];
    k += 1;
  }
  return { rs_ratio: ratio, rs_ratio_sma: mean };
}

/** Re-exported so the catalogue and the strategies share one implementation. */
export { ema, sma };
