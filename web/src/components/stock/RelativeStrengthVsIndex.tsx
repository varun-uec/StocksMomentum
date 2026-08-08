'use client';

/**
 * Phase 6.2 — relative strength versus the benchmark index, bound to
 * `/stocks/{symbol}/live` → `relative_strength_vs_index`.
 *
 * Raw numbers: the stock's return, the index's return over the same sessions,
 * and the difference. No rating, no percentile, no verdict — a positive excess
 * return is a measurement of the past, not a claim about the future.
 *
 * An unmeasurable period shows "—" rather than 0%: the backend returns `null`
 * when the stock and index do not share enough sessions, and rendering that as
 * zero would read as "matched the index".
 */

import { Card } from '@/components/shared/Card';
import type { RelativeStrengthPoint } from '@/lib/types';

const PERIOD_LABELS: Record<string, string> = {
  '1m': '1 month',
  '3m': '3 months',
  '6m': '6 months',
  '12m': '12 months',
};

function pct(value: string | null): string {
  if (value === null) return '—';
  const n = parseFloat(value);
  return Number.isFinite(n) ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` : '—';
}

function toneFor(value: string | null): string {
  if (value === null) return 'text-slate-400 dark:text-slate-600';
  const n = parseFloat(value);
  if (!Number.isFinite(n)) return 'text-slate-400 dark:text-slate-600';
  return n >= 0
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-rose-600 dark:text-rose-400';
}

export function RelativeStrengthVsIndex({
  points,
  benchmarkIndex,
}: {
  points: RelativeStrengthPoint[];
  benchmarkIndex: string | null;
}) {
  if (points.length === 0) {
    return (
      <Card title="Relative strength vs index">
        <p className="text-xs text-slate-500 italic">
          No benchmark-index history is available
          {benchmarkIndex ? ` for ${benchmarkIndex}` : ''}, so excess return cannot be measured.
        </p>
      </Card>
    );
  }

  return (
    <Card
      title="Relative strength vs index"
      subtitle={`Stock return minus ${benchmarkIndex ?? 'index'} return, measured over the same sessions`}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-slate-500 dark:text-slate-400">
              <th className="font-medium py-1.5 pr-3">Period</th>
              <th className="font-medium py-1.5 px-3 text-right tabular-nums">Stock</th>
              <th className="font-medium py-1.5 px-3 text-right tabular-nums">
                {benchmarkIndex ?? 'Index'}
              </th>
              <th className="font-medium py-1.5 pl-3 text-right tabular-nums">Excess</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr
                key={p.period}
                className="border-t border-slate-200 dark:border-slate-700/40"
              >
                <td className="py-1.5 pr-3 text-slate-700 dark:text-slate-300">
                  {PERIOD_LABELS[p.period] ?? p.period}
                  <span className="text-slate-400 dark:text-slate-600"> · {p.sessions} sessions</span>
                </td>
                <td className="py-1.5 px-3 text-right tabular-nums text-slate-700 dark:text-slate-300">
                  {pct(p.stock_return_pct)}
                </td>
                <td className="py-1.5 px-3 text-right tabular-nums text-slate-700 dark:text-slate-300">
                  {pct(p.index_return_pct)}
                </td>
                <td
                  className={`py-1.5 pl-3 text-right tabular-nums font-semibold ${toneFor(
                    p.excess_return_pct
                  )}`}
                >
                  {pct(p.excess_return_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500 mt-3">
        Descriptive only. This figure does not feed the momentum score or the ranking.
      </p>
    </Card>
  );
}
