'use client';

/**
 * Phase 6.1 — overview header.
 *
 * Price and change are derived from the last two bars of
 * `GET /securities/{symbol}/ohlcv` (the `/live` payload has no top-level
 * price field). The 52-week range and distances come from
 * `/stocks/{symbol}/live` → `indicators.{high_52w,low_52w,pct_above_low_52w,
 * pct_below_high_52w}`. Scores come from `explanation.momentum_score` /
 * `explanation.composite_score`.
 */

import { MetricCard } from '@/components/shared/Card';
import type { LiveStockAnalysis, OHLCVBarDTO } from '@/lib/types';

function fmt(value: string | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—';
  const n = parseFloat(value);
  return Number.isFinite(n) ? n.toFixed(digits) : '—';
}

export function MomentumOverview({
  live,
  bars,
}: {
  live: LiveStockAnalysis;
  bars: OHLCVBarDTO[];
}) {
  const last = bars.at(-1);
  const prev = bars.at(-2);
  const close = last ? parseFloat(last.close) : null;
  const prevClose = prev ? parseFloat(prev.close) : null;
  const change = close !== null && prevClose !== null ? close - prevClose : null;
  const changePct = change !== null && prevClose ? (change / prevClose) * 100 : null;
  const ind = live.indicators;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <MetricCard
        label={`Close${last ? ` · ${last.date}` : ''}`}
        value={close !== null ? close.toFixed(2) : '—'}
        change={change !== null ? change.toFixed(2) : undefined}
        changeLabel={changePct !== null ? `(${changePct.toFixed(2)}%)` : undefined}
        color={
          change === null
            ? undefined
            : change >= 0
              ? 'text-emerald-600 dark:text-emerald-400'
              : 'text-rose-600 dark:text-rose-400'
        }
      />
      <MetricCard label="52-week high" value={fmt(ind.high_52w)} />
      <MetricCard label="52-week low" value={fmt(ind.low_52w)} />
      <MetricCard
        label="Below 52w high"
        value={ind.pct_below_high_52w !== null ? `${fmt(ind.pct_below_high_52w)}%` : '—'}
      />
      <MetricCard
        label="Above 52w low"
        value={ind.pct_above_low_52w !== null ? `${fmt(ind.pct_above_low_52w)}%` : '—'}
      />
      <MetricCard
        label="Momentum / Composite"
        value={
          live.explanation
            ? `${fmt(live.explanation.momentum_score)} / ${fmt(live.explanation.composite_score)}`
            : '—'
        }
      />
    </div>
  );
}
