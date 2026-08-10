/**
 * Strategy presets and their signal rules.
 *
 * A preset does two things: it configures the chart in one click, and it
 * evaluates a fixed set of rules over the displayed bars. Every rule is a pure
 * function of `bars[0..i]` — nothing reads a bar later than the one it prints
 * on, so a signal never moves or vanishes when new bars arrive.
 *
 * All maths here is arithmetic on the bars the chart already shows. Nothing is
 * fetched, nothing is invented, and none of it touches the screening run, the
 * composite score or the ranking: `signalScore` is a view over the same bars.
 */

import {
  atr,
  bollinger,
  ema,
  rollingMax,
  rollingMin,
  sma,
  swingPivots,
  type Bar,
  type Params,
} from '@/lib/indicators/overlays';
import { directionalIndicators, rsi } from '@/lib/indicators/oscillators';

export type SignalDirection = 'long' | 'short' | 'exit';

export interface Signal {
  date: string;
  /** Index into the bars the signal was computed from. */
  index: number;
  direction: SignalDirection;
  ruleId: string;
  label: string;
  /** The values that made the rule fire, so a reader can check it. */
  detail: string;
}

export interface StrategyRule {
  id: string;
  label: string;
  evaluate: (bars: Bar[]) => Signal[];
}

export interface PresetIndicator {
  id: string;
  params?: Params;
}

export interface StrategyPreset {
  id: string;
  label: string;
  description: string;
  /** Catalogue entries the preset switches on, in order. */
  indicators: PresetIndicator[];
  rules: StrategyRule[];
}

const f2 = (v: number) => v.toFixed(2);

/** Emit a signal on each bar where `test` turns true, having been false. */
function onRisingEdge(
  bars: Bar[],
  test: (i: number) => boolean | null,
  make: (i: number) => Omit<Signal, 'date' | 'index'>
): Signal[] {
  const out: Signal[] = [];
  let previous = false;
  for (let i = 0; i < bars.length; i += 1) {
    const now = test(i);
    if (now === null) {
      previous = false;
      continue;
    }
    if (now && !previous) out.push({ date: bars[i].date, index: i, ...make(i) });
    previous = now;
  }
  return out;
}

const defined = (...values: (number | null | undefined)[]): boolean =>
  values.every((v) => v !== null && v !== undefined && Number.isFinite(v));

// ── Shared derived series, memoized per bars array ─────────────────────

interface Derived {
  close: number[];
  sma50: (number | null)[];
  sma150: (number | null)[];
  sma200: (number | null)[];
  ema10: (number | null)[];
  ema21: (number | null)[];
  macd: (number | null)[];
  macdSignal: (number | null)[];
  rsi14: (number | null)[];
  adx14: (number | null)[];
  plusDi: (number | null)[];
  minusDi: (number | null)[];
  volSma20: (number | null)[];
}

const derivedCache = new WeakMap<Bar[], Derived>();

function derive(bars: Bar[]): Derived {
  const cached = derivedCache.get(bars);
  if (cached) return cached;
  const close = bars.map((b) => b.close);
  const macdFast = ema(close, 12);
  const macdSlow = ema(close, 26);
  const macd = macdFast.map((v, i) => (v === null || macdSlow[i] === null ? null : v - macdSlow[i]!));
  const macdDefined = macd.filter((v): v is number => v !== null);
  const signalDefined = ema(macdDefined, 9);
  const macdSignal: (number | null)[] = new Array(bars.length).fill(null);
  let k = 0;
  for (let i = 0; i < macd.length; i += 1) {
    if (macd[i] === null) continue;
    macdSignal[i] = signalDefined[k];
    k += 1;
  }
  const { plus_di: plusDi, minus_di: minusDi } = directionalIndicators(bars, { period: 14 });
  // Wilder ADX from the same ±DI the pane draws.
  const dx = plusDi.map((p, i) => {
    const m = minusDi[i];
    if (p === null || m === null || p + m === 0) return null;
    return (100 * Math.abs(p - m)) / (p + m);
  });
  const adx14: (number | null)[] = new Array(bars.length).fill(null);
  let run: number | null = null;
  let seed: number[] = [];
  for (let i = 0; i < dx.length; i += 1) {
    if (dx[i] === null) continue;
    if (run === null) {
      seed.push(dx[i]!);
      if (seed.length === 14) {
        run = seed.reduce((a, b) => a + b, 0) / 14;
        adx14[i] = run;
        seed = [];
      }
      continue;
    }
    run = (run * 13 + dx[i]!) / 14;
    adx14[i] = run;
  }
  const value: Derived = {
    close,
    sma50: sma(close, 50),
    sma150: sma(close, 150),
    sma200: sma(close, 200),
    ema10: ema(close, 10),
    ema21: ema(close, 21),
    macd,
    macdSignal,
    rsi14: rsi(bars, 14),
    adx14,
    plusDi,
    minusDi,
    volSma20: sma(bars.map((b) => b.volume), 20),
  };
  derivedCache.set(bars, value);
  return value;
}

// ── Rules ──────────────────────────────────────────────────────────────

const stage2Alignment: StrategyRule = {
  id: 'stage2_alignment',
  label: 'Stage 2 alignment: close > SMA50 > SMA150 > SMA200',
  evaluate: (bars) => {
    const d = derive(bars);
    return onRisingEdge(
      bars,
      (i) =>
        defined(d.sma50[i], d.sma150[i], d.sma200[i])
          ? d.close[i] > d.sma50[i]! && d.sma50[i]! > d.sma150[i]! && d.sma150[i]! > d.sma200[i]!
          : null,
      (i) => ({
        direction: 'long',
        ruleId: 'stage2_alignment',
        label: 'Stage 2 alignment turned true',
        detail: `close ${f2(d.close[i])} > SMA50 ${f2(d.sma50[i]!)} > SMA150 ${f2(d.sma150[i]!)} > SMA200 ${f2(d.sma200[i]!)}`,
      })
    );
  },
};

const sma200Rising: StrategyRule = {
  id: 'sma200_rising',
  label: 'SMA 200 turned up over 20 sessions',
  evaluate: (bars) => {
    const d = derive(bars);
    return onRisingEdge(
      bars,
      (i) => (i >= 20 && defined(d.sma200[i], d.sma200[i - 20]) ? d.sma200[i]! > d.sma200[i - 20]! : null),
      (i) => ({
        direction: 'long',
        ruleId: 'sma200_rising',
        label: 'SMA 200 slope turned positive',
        detail: `SMA200 ${f2(d.sma200[i]!)} vs ${f2(d.sma200[i - 20]!)} twenty sessions back`,
      })
    );
  },
};

const new52wHigh: StrategyRule = {
  id: 'new_52w_high',
  label: 'Close at a new 252-session high',
  evaluate: (bars) => {
    const priorHigh = rollingMax(bars.map((b) => b.high), 252);
    return onRisingEdge(
      bars,
      (i) => (i >= 252 && priorHigh[i - 1] !== null ? bars[i].close > priorHigh[i - 1]! : null),
      (i) => ({
        direction: 'long',
        ruleId: 'new_52w_high',
        label: 'New 252-session high',
        detail: `close ${f2(bars[i].close)} above the prior 252-session high ${f2(priorHigh[i - 1]!)}`,
      })
    );
  },
};

const lostSma50: StrategyRule = {
  id: 'lost_sma50',
  label: 'Close lost the SMA 50',
  evaluate: (bars) => {
    const d = derive(bars);
    return onRisingEdge(
      bars,
      (i) => (defined(d.sma50[i]) ? d.close[i] < d.sma50[i]! : null),
      (i) => ({
        direction: 'exit',
        ruleId: 'lost_sma50',
        label: 'Close fell below SMA 50',
        detail: `close ${f2(d.close[i])} below SMA50 ${f2(d.sma50[i]!)}`,
      })
    );
  },
};

const donchianBreakout: StrategyRule = {
  id: 'donchian20_breakout',
  label: 'Close above the prior 20-session high',
  evaluate: (bars) => {
    const upper = rollingMax(bars.map((b) => b.high), 20);
    return onRisingEdge(
      bars,
      (i) => (i > 0 && upper[i - 1] !== null ? bars[i].close > upper[i - 1]! : null),
      (i) => ({
        direction: 'long',
        ruleId: 'donchian20_breakout',
        label: 'Donchian 20 breakout',
        detail: `close ${f2(bars[i].close)} above the prior 20-session high ${f2(upper[i - 1]!)}`,
      })
    );
  },
};

const squeezeExpansion: StrategyRule = {
  id: 'bb_squeeze_expansion',
  label: 'Bollinger squeeze then expansion',
  evaluate: (bars) => {
    const [upper, mid, lower] = bollinger(bars, { period: 20, k: 2 });
    const byDate = new Map<string, { u: number; m: number; l: number }>();
    for (const point of mid.points) byDate.set(point.date, { u: NaN, m: point.price, l: NaN });
    for (const point of upper.points) {
      const e = byDate.get(point.date);
      if (e) e.u = point.price;
    }
    for (const point of lower.points) {
      const e = byDate.get(point.date);
      if (e) e.l = point.price;
    }
    const width = bars.map((b) => {
      const e = byDate.get(b.date);
      return e && Number.isFinite(e.u) && e.m !== 0 ? (e.u - e.l) / e.m : null;
    });
    const minWidth = rollingMin(width.map((w) => w ?? Number.POSITIVE_INFINITY), 60);
    return onRisingEdge(
      bars,
      (i) => {
        if (i === 0 || width[i] === null || width[i - 1] === null || minWidth[i - 1] === null) return null;
        const wasSqueezed = width[i - 1]! <= minWidth[i - 1]! * 1.05;
        const e = byDate.get(bars[i].date)!;
        return wasSqueezed && width[i]! > width[i - 1]! && bars[i].close > e.m;
      },
      (i) => ({
        direction: 'long',
        ruleId: 'bb_squeeze_expansion',
        label: 'Bollinger bands expanded out of a 60-session squeeze',
        detail: `band width ${(width[i]! * 100).toFixed(2)}% of the mid, up from ${(width[i - 1]! * 100).toFixed(2)}%, close above the 20-session mid`,
      })
    );
  },
};

const volumeSurge: StrategyRule = {
  id: 'volume_surge',
  label: 'Up day on 1.5× average volume',
  evaluate: (bars) => {
    const d = derive(bars);
    return onRisingEdge(
      bars,
      (i) =>
        defined(d.volSma20[i]) && d.volSma20[i]! > 0
          ? bars[i].volume > 1.5 * d.volSma20[i]! && bars[i].close > bars[i].open
          : null,
      (i) => ({
        direction: 'long',
        ruleId: 'volume_surge',
        label: 'Volume surge on an up day',
        detail: `${bars[i].volume.toLocaleString('en-IN')} shares vs a 20-session mean of ${Math.round(d.volSma20[i]!).toLocaleString('en-IN')}`,
      })
    );
  },
};

const lowerBandTouch: StrategyRule = {
  id: 'bb_lower_touch',
  label: 'Low touched the lower Bollinger band',
  evaluate: (bars) => {
    const lower = bollinger(bars, { period: 20, k: 2 })[2];
    const byDate = new Map(lower.points.map((p) => [p.date, p.price]));
    return onRisingEdge(
      bars,
      (i) => {
        const l = byDate.get(bars[i].date);
        return l === undefined ? null : bars[i].low <= l;
      },
      (i) => ({
        direction: 'long',
        ruleId: 'bb_lower_touch',
        label: 'Touch of the lower Bollinger band',
        detail: `low ${f2(bars[i].low)} at or below the lower band ${f2(byDate.get(bars[i].date)!)}`,
      })
    );
  },
};

const stochCrossOutOfOversold: StrategyRule = {
  id: 'stoch_cross_oversold',
  label: 'Stochastic %K crossed above %D from oversold',
  evaluate: (bars) => {
    const { stoch_k: k, stoch_d: dLine } = stochKD(bars);
    return onRisingEdge(
      bars,
      (i) =>
        i > 0 && defined(k[i], dLine[i], k[i - 1], dLine[i - 1])
          ? k[i]! > dLine[i]! && k[i - 1]! <= dLine[i - 1]! && k[i - 1]! < 30
          : null,
      (i) => ({
        direction: 'long',
        ruleId: 'stoch_cross_oversold',
        label: 'Stochastic crossed up out of oversold',
        detail: `%K ${k[i]!.toFixed(1)} crossed above %D ${dLine[i]!.toFixed(1)} from ${k[i - 1]!.toFixed(1)}`,
      })
    );
  },
};

const holdAboveEma21: StrategyRule = {
  id: 'reclaim_ema21',
  label: 'Close reclaimed the EMA 21',
  evaluate: (bars) => {
    const d = derive(bars);
    return onRisingEdge(
      bars,
      (i) => (defined(d.ema21[i]) ? d.close[i] > d.ema21[i]! : null),
      (i) => ({
        direction: 'long',
        ruleId: 'reclaim_ema21',
        label: 'Close back above the EMA 21',
        detail: `close ${f2(d.close[i])} above EMA21 ${f2(d.ema21[i]!)}`,
      })
    );
  },
};

const cloudBreak: StrategyRule = {
  id: 'ichimoku_cloud',
  label: 'Close crossed the Ichimoku cloud',
  evaluate: (bars) => {
    const hi = rollingMax(bars.map((b) => b.high), 52);
    const lo = rollingMin(bars.map((b) => b.low), 52);
    const senkouB = hi.map((h, i) => (h === null || lo[i] === null ? null : (h + lo[i]!) / 2));
    return onRisingEdge(
      bars,
      (i) => (defined(senkouB[i]) ? bars[i].close > senkouB[i]! : null),
      (i) => ({
        direction: 'long',
        ruleId: 'ichimoku_cloud',
        label: 'Close moved above Senkou B',
        detail: `close ${f2(bars[i].close)} above Senkou B ${f2(senkouB[i]!)}`,
      })
    );
  },
};

const tenkanKijunCross: StrategyRule = {
  id: 'tenkan_kijun_cross',
  label: 'Tenkan crossed the Kijun',
  evaluate: (bars) => {
    const mid = (period: number) => {
      const hi = rollingMax(bars.map((b) => b.high), period);
      const lo = rollingMin(bars.map((b) => b.low), period);
      return hi.map((h, i) => (h === null || lo[i] === null ? null : (h + lo[i]!) / 2));
    };
    const tenkan = mid(9);
    const kijun = mid(26);
    return onRisingEdge(
      bars,
      (i) => (defined(tenkan[i], kijun[i]) ? tenkan[i]! > kijun[i]! : null),
      (i) => ({
        direction: 'long',
        ruleId: 'tenkan_kijun_cross',
        label: 'Tenkan crossed above Kijun',
        detail: `Tenkan ${f2(tenkan[i]!)} above Kijun ${f2(kijun[i]!)}`,
      })
    );
  },
};

const supertrendFlip: StrategyRule = {
  id: 'supertrend_flip',
  label: 'Supertrend flipped up',
  evaluate: (bars) => {
    const a = atr(bars, 10);
    const flags: (boolean | null)[] = bars.map(() => null);
    let uptrend = true;
    for (let i = 0; i < bars.length; i += 1) {
      if (a[i] === null) continue;
      const mid = (bars[i].high + bars[i].low) / 2;
      if (bars[i].close > mid + 3 * a[i]!) uptrend = true;
      else if (bars[i].close < mid - 3 * a[i]!) uptrend = false;
      else uptrend = bars[i].close >= mid ? uptrend : uptrend && bars[i].close >= mid - 3 * a[i]!;
      flags[i] = uptrend;
    }
    return onRisingEdge(
      bars,
      (i) => flags[i],
      (i) => ({
        direction: 'long',
        ruleId: 'supertrend_flip',
        label: 'Supertrend flipped to up',
        detail: `close ${f2(bars[i].close)} with ATR(10) ${f2(a[i]!)} at a 3× band`,
      })
    );
  },
};

const adxStrong: StrategyRule = {
  id: 'adx_strong',
  label: 'ADX above 25 with +DI over −DI',
  evaluate: (bars) => {
    const d = derive(bars);
    return onRisingEdge(
      bars,
      (i) =>
        defined(d.adx14[i], d.plusDi[i], d.minusDi[i])
          ? d.adx14[i]! > 25 && d.plusDi[i]! > d.minusDi[i]!
          : null,
      (i) => ({
        direction: 'long',
        ruleId: 'adx_strong',
        label: 'Trend strength confirmed',
        detail: `ADX ${d.adx14[i]!.toFixed(1)} with +DI ${d.plusDi[i]!.toFixed(1)} over −DI ${d.minusDi[i]!.toFixed(1)}`,
      })
    );
  },
};

const goldenCross: StrategyRule = {
  id: 'golden_cross',
  label: 'SMA 50 crossed the SMA 200',
  evaluate: (bars) => {
    const d = derive(bars);
    const up = onRisingEdge(
      bars,
      (i) => (defined(d.sma50[i], d.sma200[i]) ? d.sma50[i]! > d.sma200[i]! : null),
      (i) => ({
        direction: 'long',
        ruleId: 'golden_cross',
        label: 'Golden cross',
        detail: `SMA50 ${f2(d.sma50[i]!)} crossed above SMA200 ${f2(d.sma200[i]!)}`,
      })
    );
    const down = onRisingEdge(
      bars,
      (i) => (defined(d.sma50[i], d.sma200[i]) ? d.sma50[i]! < d.sma200[i]! : null),
      (i) => ({
        direction: 'short',
        ruleId: 'golden_cross',
        label: 'Death cross',
        detail: `SMA50 ${f2(d.sma50[i]!)} crossed below SMA200 ${f2(d.sma200[i]!)}`,
      })
    );
    return [...up, ...down].sort((a, b) => a.index - b.index);
  },
};

const macdSignalCross: StrategyRule = {
  id: 'macd_signal_cross',
  label: 'MACD line crossed its signal',
  evaluate: (bars) => {
    const d = derive(bars);
    const test = (i: number) => (defined(d.macd[i], d.macdSignal[i]) ? d.macd[i]! > d.macdSignal[i]! : null);
    const up = onRisingEdge(bars, test, (i) => ({
      direction: 'long',
      ruleId: 'macd_signal_cross',
      label: 'MACD line crossed above signal',
      detail: `MACD ${d.macd[i]!.toFixed(3)} above signal ${d.macdSignal[i]!.toFixed(3)}`,
    }));
    const down = onRisingEdge(
      bars,
      (i) => {
        const v = test(i);
        return v === null ? null : !v;
      },
      (i) => ({
        direction: 'short',
        ruleId: 'macd_signal_cross',
        label: 'MACD line crossed below signal',
        detail: `MACD ${d.macd[i]!.toFixed(3)} below signal ${d.macdSignal[i]!.toFixed(3)}`,
      })
    );
    return [...up, ...down].sort((a, b) => a.index - b.index);
  },
};

const rsiCrossings: StrategyRule = {
  id: 'rsi_30_70',
  label: 'RSI crossed 30 or 70',
  evaluate: (bars) => {
    const d = derive(bars);
    const up = onRisingEdge(
      bars,
      (i) => (defined(d.rsi14[i]) ? d.rsi14[i]! > 70 : null),
      (i) => ({
        direction: 'long',
        ruleId: 'rsi_30_70',
        label: 'RSI crossed above 70',
        detail: `RSI(14) ${d.rsi14[i]!.toFixed(1)}`,
      })
    );
    const down = onRisingEdge(
      bars,
      (i) => (defined(d.rsi14[i]) ? d.rsi14[i]! < 30 : null),
      (i) => ({
        direction: 'short',
        ruleId: 'rsi_30_70',
        label: 'RSI crossed below 30',
        detail: `RSI(14) ${d.rsi14[i]!.toFixed(1)}`,
      })
    );
    return [...up, ...down].sort((a, b) => a.index - b.index);
  },
};

const obvNewHigh: StrategyRule = {
  id: 'obv_new_high',
  label: 'OBV and price at a joint 60-session high',
  evaluate: (bars) => {
    let acc = 0;
    const obv = bars.map((b, i) => {
      if (i === 0) return 0;
      const diff = b.close - bars[i - 1].close;
      acc += diff > 0 ? b.volume : diff < 0 ? -b.volume : 0;
      return acc;
    });
    const obvMax = rollingMax(obv, 60);
    const priceMax = rollingMax(bars.map((b) => b.close), 60);
    return onRisingEdge(
      bars,
      (i) =>
        i >= 60 && obvMax[i] !== null && priceMax[i] !== null
          ? obv[i] >= obvMax[i]! && bars[i].close >= priceMax[i]!
          : null,
      (i) => ({
        direction: 'long',
        ruleId: 'obv_new_high',
        label: 'OBV confirmed a new price high',
        detail: `OBV ${Math.round(obv[i]).toLocaleString('en-IN')} and close ${f2(bars[i].close)} both at 60-session highs`,
      })
    );
  },
};

const cmfPositive: StrategyRule = {
  id: 'cmf_positive',
  label: 'Chaikin Money Flow turned positive',
  evaluate: (bars) => {
    const mfv = bars.map((b) => {
      const range = b.high - b.low;
      return range === 0 ? 0 : (((b.close - b.low) - (b.high - b.close)) / range) * b.volume;
    });
    const cmf = bars.map((_, i) => {
      if (i < 19) return null;
      let flow = 0;
      let vol = 0;
      for (let j = i - 19; j <= i; j += 1) {
        flow += mfv[j];
        vol += bars[j].volume;
      }
      return vol === 0 ? 0 : flow / vol;
    });
    return onRisingEdge(
      bars,
      (i) => (cmf[i] === null ? null : cmf[i]! > 0),
      (i) => ({
        direction: 'long',
        ruleId: 'cmf_positive',
        label: 'CMF(20) turned positive',
        detail: `CMF ${cmf[i]!.toFixed(3)}`,
      })
    );
  },
};

const pocketPivot: StrategyRule = {
  id: 'pocket_pivot',
  label: 'Up day on more volume than any of the last 10 down days',
  evaluate: (bars) =>
    onRisingEdge(
      bars,
      (i) => {
        if (i < 11) return null;
        const downVolumes: number[] = [];
        for (let j = i - 10; j < i; j += 1) {
          if (bars[j].close < bars[j - 1].close) downVolumes.push(bars[j].volume);
        }
        if (downVolumes.length === 0) return false;
        return bars[i].close > bars[i - 1].close && bars[i].volume > Math.max(...downVolumes);
      },
      (i) => ({
        direction: 'long',
        ruleId: 'pocket_pivot',
        label: 'Pocket-pivot volume day',
        detail: `up day on ${bars[i].volume.toLocaleString('en-IN')} shares, above every down day in the last ten sessions`,
      })
    ),
};

/** Stochastic %K/%D reused by the pullback preset without a catalogue round-trip. */
function stochKD(bars: Bar[]): { stoch_k: (number | null)[]; stoch_d: (number | null)[] } {
  const hi = rollingMax(bars.map((b) => b.high), 14);
  const lo = rollingMin(bars.map((b) => b.low), 14);
  const raw = bars.map((b, i) => {
    if (hi[i] === null || lo[i] === null) return null;
    const range = hi[i]! - lo[i]!;
    return range === 0 ? 50 : ((b.close - lo[i]!) / range) * 100;
  });
  const smooth = (values: (number | null)[], period: number) =>
    values.map((_, i) => {
      const w = values.slice(Math.max(0, i - period + 1), i + 1);
      if (w.length < period || w.some((v) => v === null)) return null;
      return (w as number[]).reduce((a, b) => a + b, 0) / period;
    });
  const k = smooth(raw, 3);
  return { stoch_k: k, stoch_d: smooth(k, 3) };
}

// ── Presets ────────────────────────────────────────────────────────────

export const PRESETS: StrategyPreset[] = [
  {
    id: 'momentum',
    label: 'Momentum / Stage 2',
    description: 'The trend case: stacked averages, a rising SMA 200 and position in the 52-week range.',
    indicators: [
      { id: 'sma', params: { period: 150 } },
      { id: 'hilo52w', params: { sessions: 252 } },
      { id: 'rsi' },
    ],
    rules: [stage2Alignment, sma200Rising, new52wHigh, lostSma50],
  },
  {
    id: 'breakout',
    label: 'Breakout structure',
    description: 'Range edges, band compression and the volume that confirms a break.',
    indicators: [
      { id: 'donchian', params: { period: 20 } },
      { id: 'donchian', params: { period: 55 } },
      { id: 'bollinger', params: { period: 20, k: 2 } },
      { id: 'volume', params: { period: 20 } },
    ],
    rules: [donchianBreakout, squeezeExpansion, volumeSurge],
  },
  {
    id: 'pullback',
    label: 'Pullback / mean reversion',
    description: 'Where a trending name is stretched down to support rather than extended up.',
    indicators: [
      { id: 'ema', params: { period: 10 } },
      { id: 'ema', params: { period: 21 } },
      { id: 'bollinger', params: { period: 20, k: 2 } },
      { id: 'avwap', params: { anchor: '' } },
      { id: 'stoch', params: { period: 14, kSmooth: 3, dSmooth: 3 } },
    ],
    rules: [lowerBandTouch, stochCrossOutOfOversold, holdAboveEma21],
  },
  {
    id: 'trend_quality',
    label: 'Trend quality',
    description: 'Whether the trend is orderly: cloud, Supertrend and directional strength.',
    indicators: [{ id: 'ichimoku' }, { id: 'supertrend' }, { id: 'adx' }, { id: 'di' }],
    rules: [cloudBreak, tenkanKijunCross, supertrendFlip, adxStrong],
  },
  {
    id: 'crossovers',
    label: 'Classic crossovers',
    description: 'The textbook signals, shown with the values that produced them.',
    indicators: [{ id: 'sma', params: { period: 50 } }, { id: 'sma', params: { period: 200 } }, { id: 'macd' }],
    rules: [goldenCross, macdSignalCross, rsiCrossings],
  },
  {
    id: 'volume',
    label: 'Volume / accumulation',
    description: 'Whether buying is showing up in the volume, not only in the price.',
    indicators: [{ id: 'volume', params: { period: 20 } }, { id: 'obv' }, { id: 'cmf', params: { period: 20 } }, { id: 'mfi', params: { period: 14 } }],
    rules: [obvNewHigh, cmfPositive, pocketPivot],
  },
];

export const DEFAULT_PRESET_ID = 'momentum';
export const PRESET_BY_ID = new Map(PRESETS.map((p) => [p.id, p]));

/** Every signal the preset's rules print, oldest first. */
export function presetSignals(bars: Bar[], presetId: string): Signal[] {
  const preset = PRESET_BY_ID.get(presetId);
  if (!preset || bars.length === 0) return [];
  return preset.rules
    .flatMap((rule) => rule.evaluate(bars))
    .sort((a, b) => a.index - b.index || a.ruleId.localeCompare(b.ruleId));
}

export interface RuleState {
  ruleId: string;
  label: string;
  latest: Signal | null;
  /** Sessions since the latest signal, or null when the rule never fired. */
  ageBars: number | null;
  /** This rule's signed contribution to `signalScore`, in points. */
  contribution: number;
}

/** How far back a signal still counts toward the score. */
const SCORE_WINDOW = 60;

const WEIGHT: Record<SignalDirection, number> = { long: 1, short: -1, exit: -0.5 };

/**
 * A 0–100 roll-up of the preset's rules: how many fired, how recently, and in
 * which direction. 50 is neutral — no rule has fired inside the window.
 *
 * View-layer only. Nothing here reaches the screening run, the composite score
 * or the ranking.
 */
export function ruleStates(bars: Bar[], presetId: string): RuleState[] {
  const preset = PRESET_BY_ID.get(presetId);
  if (!preset) return [];
  const last = bars.length - 1;
  const per = preset.rules.length === 0 ? 0 : 50 / preset.rules.length;
  return preset.rules.map((rule) => {
    const signals = rule.evaluate(bars);
    const latest = signals.length ? signals[signals.length - 1] : null;
    const ageBars = latest ? last - latest.index : null;
    const recency = ageBars === null ? 0 : Math.max(0, 1 - ageBars / SCORE_WINDOW);
    const contribution = latest ? WEIGHT[latest.direction] * per * recency : 0;
    return { ruleId: rule.id, label: rule.label, latest, ageBars, contribution };
  });
}

export function signalScore(bars: Bar[], presetId: string): number {
  if (bars.length === 0) return 50;
  const total = ruleStates(bars, presetId).reduce((a, s) => a + s.contribution, 0);
  return Math.round(Math.min(100, Math.max(0, 50 + total)));
}

/** Last swing low date, used as the pullback preset's default VWAP anchor. */
export function lastSwingLowDate(bars: Bar[]): string | null {
  const pivots = swingPivots(bars, 5).filter((x) => x.kind === 'L');
  return pivots.length ? pivots[pivots.length - 1].date : null;
}
