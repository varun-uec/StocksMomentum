/**
 * Chart types and price scales (M13). Every type draws the same adjusted bars;
 * Heikin-Ashi is a display transform only and never feeds a score (NFR-1a).
 */

export type ChartType = 'candles' | 'bars' | 'line' | 'area' | 'heikin_ashi';
export type PriceScale = 'normal' | 'log' | 'percent';

export const CHART_TYPES: { id: ChartType; label: string }[] = [
  { id: 'candles', label: 'Candles' },
  { id: 'bars', label: 'Bars' },
  { id: 'line', label: 'Line' },
  { id: 'area', label: 'Area' },
  { id: 'heikin_ashi', label: 'Heikin-Ashi' },
];

export interface OhlcPoint<T> {
  time: T;
  open: number;
  high: number;
  low: number;
  close: number;
}

/**
 * Heikin-Ashi bars: close is the bar's OHLC mean, open the midpoint of the
 * previous Heikin-Ashi body (the first bar's own body), high and low widened
 * to include both. Display only.
 */
export function heikinAshi<T>(bars: OhlcPoint<T>[]): OhlcPoint<T>[] {
  const out: OhlcPoint<T>[] = [];
  for (const b of bars) {
    const prev = out.at(-1);
    const close = (b.open + b.high + b.low + b.close) / 4;
    const open = prev ? (prev.open + prev.close) / 2 : (b.open + b.close) / 2;
    out.push({ time: b.time, open, close, high: Math.max(b.high, open, close), low: Math.min(b.low, open, close) });
  }
  return out;
}
