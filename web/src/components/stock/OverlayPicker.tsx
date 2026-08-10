'use client';

/**
 * The indicator picker: a searchable list rendered from the catalogue, the
 * parameter inputs for whatever is active, and the legend with each active
 * indicator's latest value.
 *
 * Overlay series set `lastValueVisible: false`, so they never show in the
 * chart's crosshair readout box. This legend is where their numbers live.
 */

import { useMemo, useState } from 'react';
import {
  INDICATOR_BY_ID,
  defaultParams,
  indicatorGroups,
  type IndicatorDef,
} from '@/lib/indicators/catalogue';
import { newUid, type ActiveIndicator } from '@/lib/overlay-preferences';
import { focusRing } from '@/lib/theme';

export interface LegendEntry {
  label: string;
  color: string;
  /** Latest defined value of the series, already formatted. */
  value: string;
}

export function OverlayPicker({
  active,
  onChange,
  legend,
  paneCount,
  maxPanes,
}: {
  active: ActiveIndicator[];
  onChange: (next: ActiveIndicator[]) => void;
  legend: LegendEntry[];
  paneCount: number;
  maxPanes: number;
}) {
  const [query, setQuery] = useState('');

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return indicatorGroups()
      .map((g) => ({
        ...g,
        items: g.items.filter(
          (d) => !needle || d.label.toLowerCase().includes(needle) || d.group.toLowerCase().includes(needle)
        ),
      }))
      .filter((g) => g.items.length > 0);
  }, [query]);

  const countFor = (id: string) => active.filter((a) => a.id === id).length;
  const paneFull = paneCount >= maxPanes;

  const add = (def: IndicatorDef) => {
    if (def.kind === 'pane' && paneFull) return;
    onChange([...active, { uid: newUid(def.id), id: def.id, params: defaultParams(def) }]);
  };

  const remove = (uid: string) => onChange(active.filter((a) => a.uid !== uid));

  const setParam = (uid: string, key: string, value: number | string) =>
    onChange(active.map((a) => (a.uid === uid ? { ...a, params: { ...a.params, [key]: value } } : a)));

  return (
    <div className="space-y-4">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search indicators…"
        className={`w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm ${focusRing}`}
      />

      {paneFull && (
        <p className="text-[11px] text-amber-600 dark:text-amber-400">
          {maxPanes} sub-panes is the cap — remove one before adding another, or the price pane
          gets too short to read.
        </p>
      )}

      <div className="max-h-64 overflow-y-auto pr-1 space-y-3">
        {groups.map((group) => (
          <div key={group.group}>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
              {group.group}
            </div>
            <ul className="space-y-0.5">
              {group.items.map((def) => {
                const count = countFor(def.id);
                const blocked = def.kind === 'pane' && (paneFull || count > 0);
                return (
                  <li key={def.id}>
                    <button
                      type="button"
                      onClick={() => add(def)}
                      disabled={blocked || (count > 0 && !def.repeatable)}
                      className={`w-full text-left px-2 py-1 rounded-md text-xs hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent ${focusRing}`}
                    >
                      <span className="text-slate-700 dark:text-slate-300">{def.label}</span>
                      {count > 0 && <span className="text-slate-400"> · {count} active</span>}
                      <span className="text-slate-400"> · {def.source}</span>
                      {def.note && (
                        <span className="block text-[10px] text-slate-500">{def.note}</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
        {groups.length === 0 && (
          <p className="text-xs text-slate-500">No indicator matches “{query}”.</p>
        )}
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Active</div>
        {active.length === 0 && (
          <p className="text-xs text-slate-500">
            Nothing added. Quick MAs above the chart still apply.
          </p>
        )}
        <ul className="space-y-2">
          {active.map((instance) => {
            const def = INDICATOR_BY_ID.get(instance.id);
            if (!def) return null;
            return (
              <li
                key={instance.uid}
                className="rounded-lg border border-slate-200 dark:border-slate-700/60 p-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                    {def.label}
                  </span>
                  <button
                    type="button"
                    onClick={() => remove(instance.uid)}
                    className={`text-[11px] text-rose-600 dark:text-rose-400 hover:underline ${focusRing}`}
                  >
                    Remove
                  </button>
                </div>
                {def.params.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-2">
                    {def.params.map((param) => (
                      <label
                        key={param.key}
                        className="flex items-center gap-1 text-[11px] text-slate-500"
                      >
                        {param.label}
                        {param.type === 'select' ? (
                          <select
                            value={String(instance.params[param.key] ?? param.default)}
                            onChange={(e) => setParam(instance.uid, param.key, e.target.value)}
                            className={`px-1 py-0.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 ${focusRing}`}
                          >
                            {(param.options ?? []).map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          // Steppers, not drag sliders: every edit rebuilds the
                          // overlay series, so it commits once per change.
                          <input
                            type={param.type}
                            value={String(instance.params[param.key] ?? param.default)}
                            min={param.min}
                            max={param.max}
                            step={param.step}
                            onChange={(e) =>
                              setParam(
                                instance.uid,
                                param.key,
                                param.type === 'number' ? Number(e.target.value) : e.target.value
                              )
                            }
                            className={`w-20 px-1 py-0.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 tabular-nums ${focusRing}`}
                          />
                        )}
                      </label>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      {legend.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
            Legend · latest value
          </div>
          <ul className="space-y-0.5">
            {legend.map((entry) => (
              <li key={entry.label} className="flex items-baseline justify-between gap-2 text-[11px]">
                <span style={{ color: entry.color }}>{entry.label}</span>
                <span className="tabular-nums text-slate-500">{entry.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
