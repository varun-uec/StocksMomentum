/**
 * Screener column sets, filters and saved screens (plan 2026-10-19, workflow 1
 * and B1). The filters read fields a run already stores and keep the run's
 * order, so the same rows and filters always give the same list. They create
 * no new metric and never change a score or rank.
 */

import { useEffect, useRef, useState } from 'react';
import type { components } from '@/lib/api-schema';
import type { RankingItemDTO } from '@/lib/types';
import { focusRing } from '@/lib/theme';
import { mergeById, sameJson } from '@/lib/merge';
import { useServerDocument, type DocumentSpec } from '@/lib/server-document';
import { FloatingPanel } from '@/components/shared/FloatingPanel';

/** Column-set tabs over `MomentumTable`'s columns. Overview is today's default view. */
export const COLUMN_SETS = {
  Overview: ['rank', 'symbol', 'name', 'sector', 'momentum_score', 'buy_setup_score', 'rs_rating', 'trend_template', 'risk', 'volume', 'breakout', 'pattern', 'rank_change', 'checklist'],
  Scores: ['rank', 'symbol', 'momentum_score', 'buy_setup_score', 'rs_rating', 'signal_score', 'rank_change'],
  Explanation: ['rank', 'symbol', 'trend_template', 'risk', 'volume', 'breakout', 'pattern', 'checklist'],
  Technical: ['rank', 'symbol', 'rs_rating', 'trend_template', 'pattern', 'checklist'],
} as const;
export type ColumnSet = keyof typeof COLUMN_SETS;

/** Numeric run fields a range can bound, with their column names. */
export const RANGE_FIELDS = {
  momentum_score: 'Momentum',
  buy_setup_score: 'Buy setup',
  rs_rating: 'RS',
  rank: 'Rank',
  rank_change: 'Δ Rank',
} as const;
export type RangeField = keyof typeof RANGE_FIELDS;
export type Range = components['schemas']['RangeV1'];

/** One value per group, or none (`null` or absent); ranges are inclusive. */
export interface ScreenerFilters {
  qualified?: boolean | null;
  trend?: boolean | null;
  risk?: string | null;
  volume?: string | null;
  breakout?: string | null;
  sector?: string | null;
  ranges?: Partial<Record<RangeField, Range>>;
}

const CATEGORY_FIELDS = { risk: 'risk_rating', volume: 'volume_quality', breakout: 'breakout_quality' } as const;
type Category = keyof typeof CATEGORY_FIELDS | 'sector';
const PILL_CATEGORIES = Object.keys(CATEGORY_FIELDS) as (keyof typeof CATEGORY_FIELDS)[];

const qualifiedOf = (row: RankingItemDTO) => row.rank > 0;
const trendOf = (row: RankingItemDTO): boolean | null => {
  const checklist = row.explanation?.checklist as Record<string, boolean> | undefined;
  return checklist ? Object.values(checklist).every(Boolean) : null;
};
const categoryOf = (row: RankingItemDTO, group: Category): string | null =>
  group === 'sector' ? row.sector : ((row.explanation?.[CATEGORY_FIELDS[group]] as string | undefined) ?? null);

/** The row's value for a range field; `null` when the run has none (an unqualified row has no rank). */
export function rangeValue(row: RankingItemDTO, field: RangeField): number | null {
  switch (field) {
    case 'momentum_score':
    case 'buy_setup_score':
      return Number(row[field]);
    case 'rs_rating':
      return row.rs_rating;
    case 'rank':
      return row.rank > 0 ? row.rank : null;
    case 'rank_change':
      return (row.explanation?.rank_change as number | undefined) ?? null;
  }
}

const inRange = (value: number | null, range: Range | undefined) =>
  !range || ((range.min == null || (value !== null && value >= range.min)) && (range.max == null || (value !== null && value <= range.max)));

/** The rows that match every set filter, in their original order. A missing value never matches a bound. */
export function applyFilters(rows: RankingItemDTO[], filters: ScreenerFilters): RankingItemDTO[] {
  const ranges = Object.entries(filters.ranges ?? {}) as [RangeField, Range][];
  return rows.filter(
    (row) =>
      (filters.qualified == null || qualifiedOf(row) === filters.qualified) &&
      (filters.trend == null || trendOf(row) === filters.trend) &&
      ([...PILL_CATEGORIES, 'sector'] as Category[]).every((group) => filters[group] == null || categoryOf(row, group) === filters[group]) &&
      ranges.every(([field, range]) => inRange(rangeValue(row, field), range)),
  );
}

/** The category values present in the rows, sorted, so no control offers an empty result. */
export function categoryValues(rows: RankingItemDTO[], group: Category): string[] {
  return [...new Set(rows.map((row) => categoryOf(row, group)).filter((v): v is string => v !== null))].sort();
}

/** Filters as the server stores them: every field written out, open ranges dropped. */
export function screenFilters(filters: ScreenerFilters): components['schemas']['ScreenFiltersV1'] {
  const ranges = Object.fromEntries(
    Object.entries(filters.ranges ?? {})
      .filter(([, r]) => r && (r.min != null || r.max != null))
      .map(([field, r]) => [field, { min: r!.min ?? null, max: r!.max ?? null }]),
  );
  return {
    qualified: filters.qualified ?? null,
    trend: filters.trend ?? null,
    risk: filters.risk ?? null,
    volume: filters.volume ?? null,
    breakout: filters.breakout ?? null,
    sector: filters.sector ?? null,
    ranges,
  };
}

const isActive = (filters: ScreenerFilters) => !sameJson(screenFilters(filters), screenFilters({}));

// ── saved screens ─────────────────────────────────────────────────────────

type SavedScreens = components['schemas']['SavedScreensV1'];
export type SavedScreen = components['schemas']['SavedScreenV1'];

export const screensSpec: DocumentSpec<SavedScreens> = {
  path: '/api/v1/screens/default',
  label: 'Your saved screens',
  defaults: () => ({ screens: [] }),
  merge: (base, mine, theirs) => {
    const r = mergeById(base?.screens ?? [], mine.screens, theirs.screens);
    return { mine: { screens: r.mine }, theirs: { screens: r.theirs }, conflicted: r.conflicts.length > 0 };
  },
};

const ACTIVE_SCREEN_KEY = 'wickstreet.screen';
const readActive = () => {
  try {
    return localStorage.getItem(ACTIVE_SCREEN_KEY);
  } catch {
    return null;
  }
};
const writeActive = (id: string | null) => {
  try {
    if (id) localStorage.setItem(ACTIVE_SCREEN_KEY, id);
    else localStorage.removeItem(ACTIVE_SCREEN_KEY);
  } catch {
    /* A remembered screen is a convenience; without storage the screener starts unsaved. */
  }
};

/** The screener's column set, filters and open saved screen; the open screen survives a reload. */
export function useScreen() {
  const doc = useServerDocument(screensSpec);
  const [columnSet, setColumnSet] = useState<ColumnSet>('Overview');
  const [filters, setFilters] = useState<ScreenerFilters>({});
  const [activeId, setActiveId] = useState<string | null>(readActive);
  const restored = useRef(false);

  const open = (screen: SavedScreen | null) => {
    setActiveId(screen?.id ?? null);
    writeActive(screen?.id ?? null);
    setColumnSet(screen?.column_set ?? 'Overview');
    setFilters(screen?.filters ?? {});
  };

  useEffect(() => {
    if (restored.current || doc.status === 'loading') return;
    restored.current = true;
    open(doc.body.screens.find((s) => s.id === activeId) ?? null);
    // Runs once, when the saved screens first arrive.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc.status]);

  const active = doc.body.screens.find((s) => s.id === activeId) ?? null;
  const current = (name: string, id: string): SavedScreen => ({ id, name, column_set: columnSet, filters: screenFilters(filters) });
  return {
    columnSet,
    setColumnSet,
    filters,
    setFilters,
    screens: doc.body.screens,
    active,
    modified: active !== null && (active.column_set !== columnSet || !sameJson(screenFilters(active.filters), screenFilters(filters))),
    open,
    save: () => {
      if (active) doc.update((body) => ({ screens: body.screens.map((s) => (s.id === active.id ? current(active.name, active.id) : s)) }));
    },
    saveAs: (name: string) => {
      const screen = current(name, `scr-${crypto.randomUUID().slice(0, 8)}`);
      doc.update((body) => ({ screens: [...body.screens, screen] }));
      setActiveId(screen.id);
      writeActive(screen.id);
    },
    remove: () => {
      if (!active) return;
      doc.update((body) => ({ screens: body.screens.filter((s) => s.id !== active.id) }));
      setActiveId(null);
      writeActive(null);
    },
  };
}
export type Screen = ReturnType<typeof useScreen>;

// ── controls ──────────────────────────────────────────────────────────────

const pill = (on: boolean) =>
  `px-2 py-0.5 rounded-full border text-xs whitespace-nowrap ${focusRing} ${on ? 'border-[var(--ws-accent)] text-[var(--ws-accent)] font-medium' : 'border-[var(--ws-line)] text-slate-600 dark:text-slate-300 hover:bg-[var(--ws-muted)]'}`;
const menuItem = `w-full text-left px-2 py-1 rounded ${focusRing} hover:bg-[var(--ws-muted)]`;
const inputClass = `w-full px-2 py-1 rounded border border-[var(--ws-line)] bg-white dark:bg-slate-900 text-xs ${focusRing}`;

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

const fmt = (n: number) => String(Number(n.toFixed(2)));
function rangeText(label: string, range: Range | undefined): string {
  if (!range || (range.min == null && range.max == null)) return label;
  if (range.min != null && range.max != null) return `${label} ${fmt(range.min)}–${fmt(range.max)}`;
  return range.min != null ? `${label} ≥ ${fmt(range.min)}` : `${label} ≤ ${fmt(range.max!)}`;
}

function RangePill({ field, range, onChange }: { field: RangeField; range: Range | undefined; onChange: (next: Range | undefined) => void }) {
  const label = RANGE_FIELDS[field];
  const on = !!range && (range.min != null || range.max != null);
  const bound = (key: 'min' | 'max', raw: string) => {
    const next = { ...range, [key]: raw === '' ? null : Number(raw) };
    onChange(next.min == null && next.max == null ? undefined : next);
  };
  return (
    <FloatingPanel
      trigger={({ ref, onClick, open }) => (
        <button ref={ref} type="button" onClick={onClick} aria-expanded={open} aria-haspopup="dialog" className={pill(on)}>
          {rangeText(label, range)} <span aria-hidden="true">▾</span>
        </button>
      )}
    >
      <div className="p-3 space-y-2 text-xs">
        <p className="font-semibold">{label}</p>
        <div className="flex items-center gap-2">
          <label className="flex-1 min-w-0">
            <span className="block text-slate-500">From</span>
            <input type="number" aria-label={`Minimum ${label}`} value={range?.min ?? ''} onChange={(e) => bound('min', e.target.value)} className={inputClass} />
          </label>
          <label className="flex-1 min-w-0">
            <span className="block text-slate-500">To</span>
            <input type="number" aria-label={`Maximum ${label}`} value={range?.max ?? ''} onChange={(e) => bound('max', e.target.value)} className={inputClass} />
          </label>
        </div>
        <p className="text-slate-500">Bounds include their value. {field === 'rank' ? 'Only qualified stocks have a rank.' : 'A stock with no value does not match.'}</p>
        {on && (
          <button type="button" onClick={() => onChange(undefined)} className={`underline text-slate-500 ${focusRing}`}>
            Reset {label}
          </button>
        )}
      </div>
    </FloatingPanel>
  );
}

export function FilterPills({ rows, value, onChange }: { rows: RankingItemDTO[]; value: ScreenerFilters; onChange: (next: ScreenerFilters) => void }) {
  const set = <K extends keyof ScreenerFilters>(key: K, next: ScreenerFilters[K]) => onChange({ ...value, [key]: value[key] === next ? null : next });
  const sectors = categoryValues(rows, 'sector');
  return (
    <div role="group" aria-label="Filters" className="flex flex-wrap items-center gap-1.5">
      <button type="button" aria-pressed={value.qualified === true} onClick={() => set('qualified', true)} className={pill(value.qualified === true)}>Qualified</button>
      <button type="button" aria-pressed={value.qualified === false} onClick={() => set('qualified', false)} className={pill(value.qualified === false)}>Not qualified</button>
      <button type="button" aria-pressed={value.trend === true} onClick={() => set('trend', true)} className={pill(value.trend === true)}>Trend pass</button>
      <button type="button" aria-pressed={value.trend === false} onClick={() => set('trend', false)} className={pill(value.trend === false)}>Trend fail</button>
      {(Object.keys(RANGE_FIELDS) as RangeField[]).map((f) => (
        <RangePill key={f} field={f} range={value.ranges?.[f]} onChange={(next) => onChange({ ...value, ranges: { ...value.ranges, [f]: next } })} />
      ))}
      {sectors.length > 0 && (
        <select aria-label="Sector" value={value.sector ?? ''} onChange={(e) => onChange({ ...value, sector: e.target.value || null })} className={`${pill(!!value.sector)} bg-transparent`}>
          <option value="">All sectors</option>
          {sectors.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      )}
      {PILL_CATEGORIES.flatMap((group) =>
        categoryValues(rows, group).map((v) => (
          <button key={`${group}:${v}`} type="button" aria-pressed={value[group] === v} onClick={() => set(group, v)} className={pill(value[group] === v)}>
            {group[0].toUpperCase() + group.slice(1)}: {v}
          </button>
        )),
      )}
      {isActive(value) && (
        <button type="button" onClick={() => onChange({})} className={`text-xs underline text-slate-500 ${focusRing}`}>
          Clear filters
        </button>
      )}
    </div>
  );
}

/** The screen menu: open a saved screen, save changes, save as new, delete. */
export function ScreenMenu({ screen }: { screen: Screen }) {
  const [name, setName] = useState('');
  const trimmed = name.trim();
  const taken = screen.screens.some((s) => s.name.toLowerCase() === trimmed.toLowerCase());
  const title = screen.active?.name ?? 'Unsaved screen';
  return (
    <FloatingPanel
      trigger={({ ref, onClick, open }) => (
        <button ref={ref} type="button" onClick={onClick} aria-expanded={open} aria-haspopup="dialog" aria-label={`Screen: ${title}${screen.modified ? ', changed' : ''}`} className={`px-2 py-1 rounded-md text-xs font-semibold border border-[var(--ws-line)] hover:bg-[var(--ws-muted)] max-w-[14rem] truncate ${focusRing}`}>
          {title}
          {screen.modified && <span aria-hidden="true"> *</span>} <span aria-hidden="true">▾</span>
        </button>
      )}
    >
      {(close) => (
        <div className="p-2 space-y-2 text-xs">
          <ul aria-label="Saved screens" className="max-h-56 overflow-y-auto">
            {screen.screens.length === 0 && <li className="px-2 py-1 text-slate-500">No saved screens yet.</li>}
            {screen.screens.map((s) => (
              <li key={s.id}>
                <button type="button" aria-pressed={s.id === screen.active?.id} onClick={() => { screen.open(s); close(); }} className={`${menuItem} ${s.id === screen.active?.id ? 'font-semibold text-[var(--ws-accent)]' : ''}`}>
                  {s.name}
                </button>
              </li>
            ))}
          </ul>
          <div className="border-t border-[var(--ws-line)] pt-2 space-y-1">
            {screen.active && screen.modified && (
              <button type="button" onClick={() => { screen.save(); close(); }} className={menuItem}>Save changes to “{screen.active.name}”</button>
            )}
            <button type="button" onClick={() => { screen.open(null); close(); }} className={menuItem}>New screen</button>
            {screen.active && (
              <button type="button" onClick={() => { screen.remove(); close(); }} className={`${menuItem} text-rose-700 dark:text-rose-400`}>Delete “{screen.active.name}”</button>
            )}
          </div>
          <form
            className="border-t border-[var(--ws-line)] pt-2 space-y-1"
            onSubmit={(e) => {
              e.preventDefault();
              if (!trimmed || taken) return;
              screen.saveAs(trimmed);
              setName('');
              close();
            }}
          >
            <label className="block">
              <span className="block text-slate-500">Save as a new screen</span>
              <input value={name} maxLength={64} onChange={(e) => setName(e.target.value)} aria-label="New screen name" placeholder="Screen name" className={inputClass} aria-invalid={taken || undefined} />
            </label>
            {taken && <p className="text-rose-700 dark:text-rose-400">A screen with this name exists.</p>}
            <button type="submit" disabled={!trimmed || taken} className={`px-2 py-1 rounded-md border border-[var(--ws-line)] font-medium disabled:opacity-50 ${focusRing}`}>
              Save screen
            </button>
          </form>
        </div>
      )}
    </FloatingPanel>
  );
}

/** Screen menu, column sets, filters and the match count, shared by the Screener route and the bottom panel. */
export function ScreenerToolbar({ screen, rows, matches }: { screen: Screen; rows: RankingItemDTO[]; matches: number }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <ScreenMenu screen={screen} />
        <ColumnSetTabs value={screen.columnSet} onChange={screen.setColumnSet} />
        <p data-testid="screen-count" aria-live="polite" className="text-xs text-slate-500 tabular-nums">
          Matches: {matches} of {rows.length}
        </p>
      </div>
      <div className="hidden sm:block">
        <FilterPills rows={rows} value={screen.filters} onChange={screen.setFilters} />
      </div>
      <details className="sm:hidden rounded-md border border-[var(--ws-line)] bg-white dark:bg-slate-900">
        <summary className={`cursor-pointer list-none px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-200 ${focusRing}`}>
          Filters <span className="ml-1 text-slate-500">· {matches} matches</span>
        </summary>
        <div className="border-t border-[var(--ws-line)] px-2 py-2">
          <FilterPills rows={rows} value={screen.filters} onChange={screen.setFilters} />
        </div>
      </details>
    </div>
  );
}
