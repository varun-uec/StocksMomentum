import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { getOhlcv } from '@/lib/api-client';
import { PriceChart, type TimeframeId } from '@/components/stock/PriceChart';

/**
 * Engineering diagnostic: mounts `n` real charts on one symbol's bars, so the
 * multi-chart smoke check (ADR-013 S7) and the M13 benchmark exercise the
 * production chart component. `?n=16&symbol=RELIANCE`. Not in the navigation.
 */
export default function ChartGridPage() {
  const [searchParams] = useSearchParams();
  const n = Math.min(Math.max(Number(searchParams.get('n')) || 4, 1), 16);
  const symbol = (searchParams.get('symbol') || 'RELIANCE').toUpperCase();
  const [timeframe, setTimeframe] = useState<TimeframeId>('MAX');
  const { data, error } = useQuery({ queryKey: ['ohlcv', symbol, 'all'], queryFn: () => getOhlcv(symbol) });
  const columns = Math.ceil(Math.sqrt(n));

  if (error) return <p className="p-4 text-sm text-rose-600">Could not load {symbol}: {String(error)}</p>;
  if (!data) return <p className="p-4 text-sm">Loading {symbol}…</p>;

  return (
    <div
      data-testid="chart-grid"
      data-ready="true"
      className="grid max-w-full gap-1 overflow-x-auto p-1"
      style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
    >
      {Array.from({ length: n }, (_, i) => (
        <div key={i} data-testid="chart-cell" className="min-w-0 border border-slate-200 dark:border-slate-800">
          <PriceChart bars={data.bars} timeframe={timeframe} onTimeframeChange={setTimeframe} height={200} />
        </div>
      ))}
    </div>
  );
}
