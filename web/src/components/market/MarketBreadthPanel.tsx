'use client';

/**
 * Phase 6.6 — market breadth, bound to `/market/context` → `breadth`.
 *
 * Counts and percentages over the tracked universe. Index-level only: nothing
 * here is attached to an individual stock, and none of it feeds the ranking.
 * There is deliberately no "bullish/bearish market" label — that would be a
 * verdict, which this platform does not publish.
 */

import { Card, MetricCard } from '@/components/shared/Card';
import type { MarketBreadth } from '@/lib/types';

function pct(value: string | null): string {
  if (value === null) return '—';
  const n = parseFloat(value);
  return Number.isFinite(n) ? `${n.toFixed(1)}%` : '—';
}

function Bar({ value }: { value: string | null }) {
  const n = value === null ? null : parseFloat(value);
  const width = n !== null && Number.isFinite(n) ? Math.max(0, Math.min(100, n)) : 0;
  return (
    <div className="h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden mt-2">
      <div
        className="h-full rounded-full bg-indigo-500 dark:bg-indigo-400"
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

export function MarketBreadthPanel({ breadth }: { breadth: MarketBreadth }) {
  return (
    <Card
      title="Market breadth"
      subtitle={`${breadth.evaluated} securities with price history as of ${breadth.as_of}`}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/40">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-slate-600 dark:text-slate-400">Above 50-day average</span>
            <span className="text-xl font-bold tabular-nums text-slate-800 dark:text-slate-200">
              {pct(breadth.pct_above_sma50)}
            </span>
          </div>
          <Bar value={breadth.pct_above_sma50} />
          <div className="text-xs text-slate-500 mt-1.5 tabular-nums">
            {breadth.above_sma50} of {breadth.above_sma50_of} measurable
          </div>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/40">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-slate-600 dark:text-slate-400">Above 200-day average</span>
            <span className="text-xl font-bold tabular-nums text-slate-800 dark:text-slate-200">
              {pct(breadth.pct_above_sma200)}
            </span>
          </div>
          <Bar value={breadth.pct_above_sma200} />
          <div className="text-xs text-slate-500 mt-1.5 tabular-nums">
            {breadth.above_sma200} of {breadth.above_sma200_of} measurable
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <MetricCard
          label="New 52-week highs"
          value={String(breadth.new_52w_highs)}
          color="text-emerald-600 dark:text-emerald-400"
        />
        <MetricCard
          label="New 52-week lows"
          value={String(breadth.new_52w_lows)}
          color="text-rose-600 dark:text-rose-400"
        />
        <MetricCard label="Measured for extremes" value={String(breadth.high_low_of)} />
      </div>

      <p className="text-xs text-slate-500 mt-4">
        A new 52-week high/low means the latest <em>close</em> is the highest/lowest of the trailing
        252 sessions. Securities without enough history are excluded from a figure rather than
        counted against it, which is why the denominators differ. Descriptive context for the market
        as a whole — not a signal for any individual stock, and not an input to the ranking.
      </p>
    </Card>
  );
}
