/**
 * Screener column sets and filter pills (plan 2026-10-19, workflow 1). The
 * filters read existing row fields only and keep the run's order, so the same
 * rows and filters always give the same list. They create no new metric.
 */

import type { RankingItemDTO } from '@/lib/types';
import { focusRing } from '@/lib/theme';

/** Column-set tabs over `MomentumTable`'s columns. Overview is today's default view. */
export const COLUMN_SETS = {
  Overview: ['rank', 'symbol', 'name', 'sector', 'momentum_score', 'buy_setup_score', 'rs_rating', 'trend_template', 'risk', 'volume', 'breakout', 'pattern', 'rank_change', 'checklist'],
  Scores: ['rank', 'symbol', 'momentum_score', 'buy_setup_score', 'rs_rating', 'signal_score', 'rank_change'],
  Explanation: ['rank', 'symbol', 'trend_template', 'risk', 'volume', 'breakout', 'pattern', 'checklist'],
  Technical: ['rank', 'symbol', 'rs_rating', 'trend_template', 'pattern', 'checklist'],
} as const;
export type ColumnSet = keyof typeof COLUMN_SETS;

/** One value per group, or none. */
export interface ScreenerFilters {
  qualified?: boolean;
  trend?: boolean;
  risk?: string;
  volume?: string;
  breakout?: string;
}

const CATEGORY_FIELDS = { risk: 'risk_rating', volume: 'volume_quality', breakout: 'breakout_quality' } as const;
type Category = keyof typeof CATEGORY_FIELDS;

const qualifiedOf = (row: RankingItemDTO) => row.rank > 0;
const trendOf = (row: RankingItemDTO): boolean | null => {
  const checklist = row.explanation?.checklist as Record<string, boolean> | undefined;
  return checklist ? Object.values(checklist).every(Boolean) : null;
};
const categoryOf = (row: RankingItemDTO, group: Category) => (row.explanation?.[CATEGORY_FIELDS[group]] as string | undefined) ?? null;

/** The rows that match every set filter, in their original order. */
export function applyFilters(rows: RankingItemDTO[], filters: ScreenerFilters): RankingItemDTO[] {
  return rows.filter(
    (row) =>
      (filters.qualified === undefined || qualifiedOf(row) === filters.qualified) &&
      (filters.trend === undefined || trendOf(row) === filters.trend) &&
      (Object.keys(CATEGORY_FIELDS) as Category[]).every((group) => filters[group] === undefined || categoryOf(row, group) === filters[group]),
  );
}

/** The category values present in the rows, sorted, so no pill offers an empty result. */
export function categoryValues(rows: RankingItemDTO[], group: Category): string[] {
  return [...new Set(rows.map((row) => categoryOf(row, group)).filter((v): v is string => v !== null))].sort();
}

const pill = (on: boolean) =>
  `px-2 py-0.5 rounded-full border text-xs ${focusRing} ${on ? 'border-[var(--ws-accent)] text-[var(--ws-accent)] font-medium' : 'border-[var(--ws-line)] text-slate-600 dark:text-slate-300 hover:bg-[var(--ws-muted)]'}`;

export function ColumnSetTabs({ value, onChange }: { value: ColumnSet; onChange: (next: ColumnSet) => void }) {
  return (
    <div role="group" aria-label="Column set" className="flex items-center gap-1">
      {(Object.keys(COLUMN_SETS) as ColumnSet[]).map((set) => (
        <button key={set} type="button" aria-pressed={value === set} onClick={() => onChange(set)} className={`px-2 py-1 text-xs rounded-md ${focusRing} ${value === set ? 'bg-[var(--ws-muted)] font-semibold' : 'text-slate-600 dark:text-slate-300 hover:bg-[var(--ws-muted)]'}`}>
          {set}
        </button>
      ))}
    </div>
  );
}

export function FilterPills({ rows, value, onChange }: { rows: RankingItemDTO[]; value: ScreenerFilters; onChange: (next: ScreenerFilters) => void }) {
  const set = <K extends keyof ScreenerFilters>(key: K, next: ScreenerFilters[K]) => onChange({ ...value, [key]: value[key] === next ? undefined : next });
  return (
    <div role="group" aria-label="Filters" className="flex flex-wrap items-center gap-1.5">
      <button type="button" aria-pressed={value.qualified === true} onClick={() => set('qualified', true)} className={pill(value.qualified === true)}>Qualified</button>
      <button type="button" aria-pressed={value.qualified === false} onClick={() => set('qualified', false)} className={pill(value.qualified === false)}>Not qualified</button>
      <button type="button" aria-pressed={value.trend === true} onClick={() => set('trend', true)} className={pill(value.trend === true)}>Trend pass</button>
      <button type="button" aria-pressed={value.trend === false} onClick={() => set('trend', false)} className={pill(value.trend === false)}>Trend fail</button>
      {(Object.keys(CATEGORY_FIELDS) as Category[]).flatMap((group) =>
        categoryValues(rows, group).map((v) => (
          <button key={`${group}:${v}`} type="button" aria-pressed={value[group] === v} onClick={() => set(group, v)} className={pill(value[group] === v)}>
            {group[0].toUpperCase() + group.slice(1)}: {v}
          </button>
        )),
      )}
      {Object.values(value).some((v) => v !== undefined) && (
        <button type="button" onClick={() => onChange({})} className={`text-xs underline text-slate-500 ${focusRing}`}>
          Clear filters
        </button>
      )}
    </div>
  );
}
