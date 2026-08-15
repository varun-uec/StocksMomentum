'use client';

/**
 * Phase 6.7 — sector relative-strength ranking, bound to `/market/context` →
 * `sectors`.
 *
 * Each cell is the equal-weighted mean excess return (sector constituent return
 * minus benchmark-index return) over that period. The rank is an ordering of a
 * measured number, not a recommendation to rotate into the top row.
 *
 * Sorting is client-side over the same numbers the backend returned; the
 * backend's own `rank` field always reflects the 3-month column, so switching
 * columns re-orders the table without changing any value.
 */

import { useState } from 'react';
import { Card } from '@/components/shared/Card';
import { focusRing } from '@/lib/theme';
import type { SectorRelativeStrength } from '@/lib/types';

const PERIODS = ['1m', '3m', '6m', '12m'] as const;
type Period = (typeof PERIODS)[number];

function num(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

function Cell({ value }: { value: string | null | undefined }) {
  const n = num(value);
  if (n === null) {
    return <span className="text-slate-400 dark:text-slate-600">—</span>;
  }
  return (
    <span
      className={
        n >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
      }
    >
      {n >= 0 ? '+' : ''}
      {n.toFixed(2)}%
    </span>
  );
}

// Why the panel is empty, as reported by the API. The component used to assert
// "No benchmark-index history is available" while benchmark_index_daily held
// 2858 rows — the real cause was securities.sector being NULL for every row
// (2026-08-09 audit §1.2.8). The endpoint now says which it is.
const UNAVAILABLE_COPY: Record<string, string> = {
  no_sector_classification:
    'Sector classification is not available for this universe, so constituents cannot be grouped. No free NSE source publishes it, so this panel stays empty until a classification is ingested.',
  no_benchmark_history:
    'No benchmark-index history is available, so sector excess returns cannot be measured.',
};

export function SectorStrengthTable({
  sectors,
  benchmarkIndex,
  unavailableReason,
}: {
  sectors: SectorRelativeStrength[];
  benchmarkIndex: string | null;
  unavailableReason?: string | null;
}) {
  const [sortBy, setSortBy] = useState<Period>('3m');

  if (sectors.length === 0) {
    return (
      <Card title="Sector relative strength">
        <p className="text-xs text-slate-500 italic">
          {UNAVAILABLE_COPY[unavailableReason ?? ''] ?? UNAVAILABLE_COPY.no_sector_classification}
        </p>
      </Card>
    );
  }

  // Unmeasurable sectors sort last regardless of direction, then by name — the
  // same total ordering the backend uses, so the table is never ambiguous.
  const rows = [...sectors].sort((a, b) => {
    const av = num(a.excess_return_pct[sortBy]);
    const bv = num(b.excess_return_pct[sortBy]);
    if (av === null && bv === null) return a.sector.localeCompare(b.sector);
    if (av === null) return 1;
    if (bv === null) return -1;
    return bv - av || a.sector.localeCompare(b.sector);
  });

  return (
    <Card
      title="Sector relative strength"
      subtitle={`Equal-weighted mean excess return vs ${benchmarkIndex ?? 'the index'} · sorted by ${sortBy}`}
    >
      <div className="flex items-center gap-1 mb-3">
        <span className="text-xs text-slate-500 mr-1">Sort by</span>
        {PERIODS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setSortBy(p)}
            aria-pressed={sortBy === p}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${focusRing} ${
              sortBy === p
                ? 'bg-indigo-100 dark:bg-indigo-600/20 text-indigo-700 dark:text-indigo-300'
                : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-slate-500 dark:text-slate-400">
              <th scope="col" className="font-medium py-1.5 pr-3">#</th>
              <th scope="col" className="font-medium py-1.5 pr-3">Sector</th>
              <th scope="col" className="font-medium py-1.5 px-3 text-right">Names</th>
              {PERIODS.map((p) => (
                <th scope="col" key={p} className="font-medium py-1.5 px-3 text-right">
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr
                key={row.sector}
                className="border-t border-slate-200 dark:border-slate-700/40"
              >
                <td className="py-1.5 pr-3 tabular-nums text-slate-400 dark:text-slate-600">
                  {idx + 1}
                </td>
                <td className="py-1.5 pr-3 text-slate-800 dark:text-slate-200 font-medium">
                  {row.sector}
                </td>
                <td className="py-1.5 px-3 text-right tabular-nums text-slate-500">
                  {row.constituents}
                </td>
                {PERIODS.map((p) => (
                  <td key={p} className="py-1.5 px-3 text-right tabular-nums font-medium">
                    <Cell value={row.excess_return_pct[p]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-500 mt-3">
        Equal-weighted because the platform ingests no market-cap data — a cap weighting would have
        to be invented. Securities without a sector classification are excluded rather than pooled
        into an &ldquo;Other&rdquo; bucket. Descriptive only: none of this feeds the ranking.
      </p>
    </Card>
  );
}
