import { expect, test } from 'vitest';
import { displayMacd, displayRsi } from './oscillators';
const bars = Array.from({ length: 100 }, (_, i) => ({ date: `2026-${i}`, open: 100, high: 100, low: 100, close: 100, volume: 1 }));
test('display MACD has an explicit warm-up and a zero spread on a constant series', () => {
  const values = displayMacd(bars, { fast: 5, slow: 10, signal: 3 });
  expect(values.display_macd.slice(0, 9)).toEqual(Array(9).fill(null));
  expect(values.display_macd_hist.slice(0, 11)).toEqual(Array(11).fill(null));
  expect(values.display_macd_hist.slice(11)).toEqual(Array(89).fill(0));
});
test('configurable RSI changes warm-up without changing authoritative field names', () => {
  const result = displayRsi(bars.map((b, i) => ({ ...b, close: i + 100 })), { period: 21 });
  expect(Object.keys(result)).toEqual(['display_rsi']);
  expect(result.display_rsi.slice(0, 21)).toEqual(Array(21).fill(null));
  expect(result.display_rsi.slice(21)).toEqual(Array(79).fill(100));
});
