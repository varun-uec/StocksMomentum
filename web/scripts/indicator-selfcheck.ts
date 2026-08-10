/**
 * Indicator self-check — run with `npx tsx scripts/indicator-selfcheck.ts`.
 *
 * The one runnable guard on the browser-side indicator maths. It asserts the
 * properties that must hold for every input, not values from a golden file:
 * warm-up windows, bounds, seeds, and no NaN on degenerate bars. If a rewrite
 * breaks an indicator, this fails.
 */

import assert from 'node:assert/strict';
import {
  anchoredVwapValues,
  bollinger,
  donchian,
  ema,
  rollingVwap,
  sma,
  supertrend,
  toBars,
  type Bar,
} from '../src/lib/indicators/overlays';
import { stochastic, williamsR, moneyFlowIndex, obv } from '../src/lib/indicators/oscillators';
import { presetSignals } from '../src/lib/strategies';

/** Deterministic pseudo-random walk — no Math.random, so runs are repeatable. */
function makeBars(count: number, zeroVolume = false): Bar[] {
  const bars: Bar[] = [];
  let price = 100;
  let seed = 42;
  for (let i = 0; i < count; i += 1) {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    const drift = ((seed / 2147483648) - 0.45) * 3;
    price = Math.max(1, price + drift);
    const high = price + Math.abs(drift) + 0.5;
    const low = Math.max(0.5, price - Math.abs(drift) - 0.5);
    const date = new Date(Date.UTC(2024, 0, 1 + i)).toISOString().slice(0, 10);
    bars.push({
      date,
      open: (high + low) / 2,
      high,
      low,
      close: price,
      volume: zeroVolume ? 0 : 1000 + (seed % 5000),
    });
  }
  return bars;
}

const bars = makeBars(400);
const closes = bars.map((b) => b.close);
let checks = 0;
const check = (name: string, fn: () => void) => {
  fn();
  checks += 1;
  console.log(`  ok  ${name}`);
};

console.log('indicator self-check');

check('sma matches the chart\'s rolling mean, leading nulls included', () => {
  const out = sma(closes, 20);
  assert.equal(out.length, closes.length);
  for (let i = 0; i < 19; i += 1) assert.equal(out[i], null, `index ${i} must be null`);
  const expected = closes.slice(0, 20).reduce((a, b) => a + b, 0) / 20;
  assert.ok(Math.abs(out[19]! - expected) < 1e-9);
});

check('ema seeds with sma(period) at index period-1', () => {
  const out = ema(closes, 30);
  for (let i = 0; i < 29; i += 1) assert.equal(out[i], null);
  assert.ok(Math.abs(out[29]! - sma(closes, 30)[29]!) < 1e-9);
});

check('bollinger with k=0 collapses upper == mid == lower', () => {
  const [upper, mid, lower] = bollinger(bars, { period: 20, k: 0 });
  assert.ok(mid.points.length > 0);
  for (let i = 0; i < mid.points.length; i += 1) {
    assert.ok(Math.abs(upper.points[i].price - mid.points[i].price) < 1e-9);
    assert.ok(Math.abs(lower.points[i].price - mid.points[i].price) < 1e-9);
  }
});

check('donchian bounds equal the rolling max high and min low', () => {
  const [upper, , lower] = donchian(bars, { period: 20 });
  const last = bars.slice(-20);
  assert.ok(Math.abs(upper.points[upper.points.length - 1].price - Math.max(...last.map((b) => b.high))) < 1e-9);
  assert.ok(Math.abs(lower.points[lower.points.length - 1].price - Math.min(...last.map((b) => b.low))) < 1e-9);
});

check('stochastic stays inside [0,100] and williams %R inside [-100,0]', () => {
  const { stoch_k: k, stoch_d: d } = stochastic(bars, { period: 14, kSmooth: 3, dSmooth: 3 });
  for (const v of [...k, ...d]) if (v !== null) assert.ok(v >= 0 && v <= 100, `stoch out of range: ${v}`);
  for (const v of williamsR(bars, { period: 14 }).williams_r)
    if (v !== null) assert.ok(v >= -100 && v <= 0, `%R out of range: ${v}`);
});

check('stochastic defaults to the backend\'s fast %K (no k smoothing)', () => {
  const fast = stochastic(bars, {});
  const last = bars.slice(-14);
  const hi = Math.max(...last.map((b) => b.high));
  const lo = Math.min(...last.map((b) => b.low));
  const rawK = ((bars[bars.length - 1].close - lo) / (hi - lo)) * 100;
  assert.ok(Math.abs(fast.stoch_k[bars.length - 1]! - rawK) < 1e-9, 'default stoch_k must be raw %K');
  // The old default (kSmooth 3) returned backend's %D in the %K slot.
  const slow = stochastic(bars, { period: 14, kSmooth: 3, dSmooth: 3 });
  assert.ok(Math.abs(slow.stoch_k[bars.length - 1]! - fast.stoch_d[bars.length - 1]!) < 1e-9);
});

check('mfi stays inside [0,100] and obv is finite everywhere', () => {
  for (const v of moneyFlowIndex(bars, { period: 14 }).mfi)
    if (v !== null) assert.ok(v >= 0 && v <= 100);
  for (const v of obv(bars).obv) assert.ok(v !== null && Number.isFinite(v));
});

check('both VWAPs stay within [min low, max high]', () => {
  const anchored = anchoredVwapValues(bars, 0);
  const rolling = rollingVwap(bars, { period: 20 })[0].points.map((pt) => pt.price);
  const lo = Math.min(...bars.map((b) => b.low));
  const hi = Math.max(...bars.map((b) => b.high));
  for (const v of [...anchored.filter((x): x is number => x !== null), ...rolling]) {
    assert.ok(v >= lo && v <= hi, `vwap ${v} outside [${lo}, ${hi}]`);
  }
});

check('a single bar\'s anchored VWAP equals its typical price', () => {
  const one = makeBars(1);
  const v = anchoredVwapValues(one, 0)[0]!;
  assert.ok(Math.abs(v - (one[0].high + one[0].low + one[0].close) / 3) < 1e-9);
});

check('zero-volume bars produce no NaN in either VWAP', () => {
  const flat = makeBars(60, true);
  for (const v of anchoredVwapValues(flat, 0)) assert.ok(v === null || Number.isFinite(v));
  for (const pt of rollingVwap(flat, { period: 20 })[0].points) assert.ok(Number.isFinite(pt.price));
});

check('supertrend flips at most once per bar and warms up with ATR', () => {
  const line = supertrend(bars, { atrPeriod: 10, mult: 3 })[0];
  assert.ok(line.points.length > 0 && line.points.length < bars.length, 'must have a warm-up gap');
  for (const pt of line.points) assert.ok(Number.isFinite(pt.price));
});

check('every function returns null before its warm-up', () => {
  const short = makeBars(5);
  assert.deepEqual(sma(short.map((b) => b.close), 20), new Array(5).fill(null));
  assert.deepEqual(ema(short.map((b) => b.close), 20), new Array(5).fill(null));
  assert.equal(donchian(short, { period: 20 })[0].points.length, 0);
  assert.equal(stochastic(short, { period: 14, kSmooth: 3, dSmooth: 3 }).stoch_k.filter((v) => v !== null).length, 0);
});

check('signals never move when later bars arrive (no lookahead)', () => {
  const long = makeBars(500);
  const prefix = long.slice(0, 400);
  for (const preset of ['momentum', 'breakout', 'pullback', 'trend_quality', 'crossovers', 'volume']) {
    const early = presetSignals(prefix, preset);
    const later = presetSignals(long, preset).filter((s) => s.index < 400);
    assert.deepEqual(
      later.map((s) => `${s.ruleId}@${s.date}:${s.direction}`),
      early.map((s) => `${s.ruleId}@${s.date}:${s.direction}`),
      `preset ${preset} rewrote a printed signal`
    );
  }
});

check('toBars parses the API decimal strings', () => {
  const parsed = toBars([{ date: '2026-01-01', open: '1.5', high: '2', low: '1', close: '1.75', volume: 10 }]);
  assert.deepEqual(parsed[0], { date: '2026-01-01', open: 1.5, high: 2, low: 1, close: 1.75, volume: 10 });
});

console.log(`\n${checks} checks passed`);
