'use client';

/**
 * Phase 6.4 — technical workbench.
 *
 * Raw indicator values from `/stocks/{symbol}/live` → `indicators`. Values
 * only: this table deliberately has no signal/verdict column, because the
 * platform does not produce a per-indicator interpretation and inventing one
 * here would be a fabricated number.
 */

import { Card } from '@/components/shared/Card';
import type { IndicatorSnapshot } from '@/lib/types';

const GROUPS: { title: string; rows: { key: keyof IndicatorSnapshot; label: string }[] }[] = [
  {
    title: 'Oscillators & volatility',
    rows: [
      { key: 'rsi14', label: 'RSI (14)' },
      { key: 'atr14', label: 'ATR (14)' },
      { key: 'adr_pct', label: 'Average daily range %' },
    ],
  },
  {
    title: 'Trend strength (ADX)',
    rows: [
      { key: 'adx14', label: 'ADX (14)' },
      { key: 'plus_di14', label: '+DI (14)' },
      { key: 'minus_di14', label: '−DI (14)' },
    ],
  },
  {
    title: 'MACD (12, 26, 9)',
    rows: [
      { key: 'macd_line', label: 'MACD line' },
      { key: 'macd_signal', label: 'Signal line' },
      { key: 'macd_histogram', label: 'Histogram' },
    ],
  },
  {
    title: 'Moving averages',
    rows: [
      { key: 'ema10', label: 'EMA 10' },
      { key: 'ema21', label: 'EMA 21' },
      { key: 'sma50', label: 'SMA 50' },
      { key: 'sma150', label: 'SMA 150' },
      { key: 'sma200', label: 'SMA 200' },
    ],
  },
  {
    // Phase 6.4 — additional raw oscillators, same values-only rule as above.
    title: 'Stochastic & momentum',
    rows: [
      { key: 'stoch_k14', label: 'Stochastic %K (14)' },
      { key: 'stoch_d14', label: 'Stochastic %D (3)' },
      { key: 'williams_r14', label: 'Williams %R (14)' },
      { key: 'cci20', label: 'CCI (20)' },
      { key: 'roc12', label: 'ROC (12) %' },
    ],
  },
  {
    // Phase 6.1 / 6.3 — distance from key reference levels, signed.
    title: 'Distance from levels',
    rows: [
      { key: 'pct_from_sma50', label: 'From SMA 50 %' },
      { key: 'pct_from_sma200', label: 'From SMA 200 %' },
      { key: 'pct_below_high_52w', label: 'Below 52w high %' },
      { key: 'pct_above_low_52w', label: 'Above 52w low %' },
    ],
  },
];

function fmt(value: string | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const n = parseFloat(value);
  return Number.isFinite(n) ? n.toFixed(2) : value;
}

export function TechnicalWorkbench({ indicators }: { indicators: IndicatorSnapshot }) {
  return (
    <Card
      title="Technical workbench"
      subtitle="Computed indicator values as of the latest stored bar — values only, not signals"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {GROUPS.map((group) => (
          <div key={group.title}>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
              {group.title}
            </div>
            <dl className="space-y-1">
              {group.rows.map((row) => (
                <div
                  key={String(row.key)}
                  className="flex items-center justify-between gap-2 text-xs px-2 py-1 rounded bg-slate-50 dark:bg-slate-900/40"
                >
                  <dt className="text-slate-600 dark:text-slate-400">{row.label}</dt>
                  <dd className="tabular-nums font-medium text-slate-800 dark:text-slate-200">
                    {fmt(indicators[row.key])}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </Card>
  );
}
