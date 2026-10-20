/**
 * Compare symbols (M13): other symbols drawn on the chart as lines, rebased to
 * the chart symbol's close at the first bar both have. A compare line therefore
 * starts on the price bars and shows relative performance from there; on the
 * percent scale both read as % change. Both series are adjusted (ADR-013 §4).
 */

import { useMemo } from 'react';
import { keepPreviousData, useQueries } from '@tanstack/react-query';
import { getOhlcv } from '@/lib/api-client';
import type { ChartOverlayLine } from '@/components/stock/PriceChart';
import type { ChartInterval } from '@/lib/types';

export const MAX_COMPARE = 4;
const COLORS = ['#f59e0b', '#0ea5e9', '#ec4899', '#22c55e'];

type Close = { date: string; close: number };

export interface CompareLine {
  symbol: string;
  color: string;
  /** Null while loading, or when the two series share no bar. */
  line: ChartOverlayLine | null;
  /** Change from the first shared bar to the last, in %. */
  change: number | null;
  /** The first shared bar: where the line meets the price bars. */
  from: string | null;
}

/** The other series rebased to `main`'s close at their first shared date. */
export function rebase(main: Close[], other: Close[], anchorDate?: string): { points: { date: string; price: number }[]; from: string } | null {
  const mainClose = new Map(main.map((b) => [b.date, b.close]));
  const start = other.findIndex((b) => mainClose.has(b.date) && b.close > 0 && (!anchorDate || b.date >= anchorDate));
  if (start < 0) return null;
  const anchor = other[start];
  const factor = mainClose.get(anchor.date)! / anchor.close;
  return { points: other.filter((b) => mainClose.has(b.date)).map((b) => ({ date: b.date, price: b.close * factor })), from: anchor.date };
}

export function useCompare(
  symbols: string[],
  main: Close[],
  interval: ChartInterval,
  anchorDate?: string,
  /** Bar replay: each compared series as of this date, like the chart's own. */
  asOf?: string,
): CompareLine[] {
  const data = useQueries({
    queries: symbols.map((symbol) => ({
      // The chart shell's key, so a symbol opened on the chart and compared shares one fetch.
      // The whole history: `rebase` starts the line at the first bar `main` shows.
      queryKey: ['stock-ohlcv', symbol, interval, ...(asOf ? [asOf] : [])],
      queryFn: () => getOhlcv(symbol, undefined, undefined, interval, asOf),
      // A replay step keeps the line until the next date's series arrives.
      placeholderData: asOf ? keepPreviousData : undefined,
      retry: false,
    })),
    // `combine` keeps one array identity until a result changes.
    combine: (results) => results.map((r) => r.data),
  });

  return useMemo(
    () =>
      symbols.map((symbol, i) => {
        const color = COLORS[i % COLORS.length];
        const bars = data[i]?.bars.map((b) => ({ date: b.date, close: parseFloat(b.close) })) ?? [];
        const rebased = main.length ? rebase(main, bars, anchorDate) : null;
        if (!rebased) return { symbol, color, line: null, change: null, from: null };
        const first = rebased.points.find((p) => p.date === rebased.from)!.price;
        const last = rebased.points[rebased.points.length - 1].price;
        return {
          symbol,
          color,
          line: { points: rebased.points, color, lineWidth: 2, percentSafe: true },
          change: (last / first - 1) * 100,
          from: rebased.from,
        };
      }),
    [symbols, main, data, anchorDate],
  );
}
