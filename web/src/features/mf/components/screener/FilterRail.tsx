/**
 * The screener browser: Basic discovers and displays metrics without changing
 * the result universe. Filtering is a separate, explicit action. Advanced keeps
 * the full condition editor and query language.
 */
import { useMemo, useState } from 'react';
import type { FieldDef, FilterNode } from '../../api';
import { isGate } from '../../view-spec';
import { I } from '../icons';
import { Segmented, cx, inputClass } from '../ui';

export type FilterMode = 'basic' | 'advanced';

const POPULAR_METRICS = ['ret_1y', 'cagr_3y', 'ter', 'aum_cr', 'vol_3y', 'mdd_3y', 'sharpe_3y', 'score'];
export const METRIC_AS_OF_FIELDS: Record<string, string> = {
  ter: 'ter_as_of',
  aum_cr: 'aum_as_of',
  riskometer: 'riskometer_as_of',
};

function MetricRow({
  field,
  shown,
  canShow,
  onToggle,
  onFilter,
}: {
  field: FieldDef;
  shown: boolean;
  canShow: boolean;
  onToggle: (field: FieldDef, shown: boolean) => void;
  onFilter: (field: FieldDef) => void;
}) {
  return (
    <div className="flex min-h-11 items-center gap-2 rounded-[8px] px-2 hover:bg-mf-sunken">
      <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 py-2 text-sm text-mf-ink">
        <input
          type="checkbox"
          aria-label={`Show ${field.label}`}
          checked={shown}
          disabled={!field.available || (!shown && !canShow)}
          onChange={(e) => onToggle(field, e.target.checked)}
        />
        <span className="truncate" title={field.description}>{field.label}</span>
        <span className="ml-auto shrink-0 text-[11px] tabular text-mf-muted">{field.coverage.values.toLocaleString('en-IN')} values</span>
      </label>
      <button
        type="button"
        disabled={!field.available}
        onClick={() => onFilter(field)}
        className="shrink-0 rounded px-2 py-1.5 text-xs font-medium text-mf-brand hover:bg-mf-brand-soft disabled:opacity-50"
        aria-label={`Filter by ${field.label}`}
        title={`Add an optional ${field.label} condition`}
      >
        Filter
      </button>
    </div>
  );
}

export function FilterRail({
  view,
  fields,
  onShowMetric,
  onPickField,
  mode,
  onModeChange,
  maxColumns,
}: {
  view: { columns: string[]; mode: 'all' | 'any'; conditions: FilterNode[] };
  fields: Map<string, FieldDef>;
  onShowMetric: (field: FieldDef, shown: boolean) => void;
  onPickField: (field: FieldDef) => void;
  mode: FilterMode;
  onModeChange: (mode: FilterMode) => void;
  maxColumns: number;
}) {
  const [query, setQuery] = useState('');
  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const map = new Map<string, FieldDef[]>();
    for (const field of fields.values()) {
      if (q && !field.label.toLowerCase().includes(q) && !field.id.includes(q) && !field.description.toLowerCase().includes(q)) continue;
      map.set(field.group, [...(map.get(field.group) ?? []), field]);
    }
    return [...map.entries()];
  }, [fields, query]);
  const shown = new Set(view.columns);
  const canShow = (field: FieldDef) => {
    const companion = METRIC_AS_OF_FIELDS[field.id];
    const additionCount = Number(!shown.has(field.id)) + Number(!!companion && fields.has(companion) && !shown.has(companion));
    return shown.size + additionCount <= maxColumns;
  };
  const toggle = (field: FieldDef, enabled: boolean) => onShowMetric(field, enabled);
  const drawBasicField = (field: FieldDef) => (
    <MetricRow key={field.id} field={field} shown={shown.has(field.id)} canShow={canShow(field)} onToggle={toggle} onFilter={onPickField} />
  );

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Segmented label="Filter mode" value={mode} onChange={onModeChange} options={[{ value: 'basic', label: 'Basic' }, { value: 'advanced', label: 'Advanced' }]} />
        <p className="text-xs leading-relaxed text-mf-muted">
          {mode === 'basic'
            ? 'Choose a metric to show its latest value in results. Add a filter only when you want to narrow funds.'
            : `Search all ${fields.size} fields and use the full condition editor.`}
        </p>
        {mode === 'basic' && view.columns.length >= 12 && <p className="text-xs text-mf-muted">All 12 result columns are in use. Remove one in Columns to add another.</p>}
        {mode === 'basic' && view.mode === 'any' && (
          <p className="rounded-[8px] bg-mf-sunken px-2.5 py-2 text-xs leading-relaxed text-mf-ink-soft" role="note">
            {view.conditions.some(isGate)
              ? 'Your active Direct Growth universe still applies. A fund must match at least one of the other conditions.'
              : 'A fund can match any listed condition.'}{' '}
            <button type="button" className="font-medium text-mf-brand underline underline-offset-2" onClick={() => onModeChange('advanced')}>Show advanced logic</button>
          </p>
        )}
      </div>

      {mode === 'basic' && (
        <>
          {!query.trim() && <section aria-labelledby="popular-metrics" className="rounded-[12px] border border-mf-line bg-mf-surface px-3 py-2">
            <h3 id="popular-metrics" className="px-2 pt-1 text-xs font-semibold uppercase tracking-[0.08em] text-mf-muted">Popular metrics</h3>
            <div className="mt-1 divide-y divide-mf-line">
              {POPULAR_METRICS.map((id) => fields.get(id)).filter((field): field is FieldDef => !!field).map(drawBasicField)}
            </div>
          </section>}
          <div className="relative">
            <I.search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-mf-muted" />
            <input className={cx(inputClass, 'pl-9')} placeholder={`Search ${fields.size} metrics`} value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search metrics" />
          </div>
          <nav aria-label="Available metrics" className="space-y-1">
            {groups.length === 0 && <p className="px-1 text-sm text-mf-muted">No metric matches “{query}”.</p>}
            {groups.map(([group, list]) => (
              <details key={group} open={!!query} className="group rounded-[10px] border border-mf-line bg-mf-surface">
                <summary className="flex min-h-10 cursor-pointer list-none items-center justify-between px-3 text-sm font-medium text-mf-ink [&::-webkit-details-marker]:hidden">
                  {group}
                  <span className="flex items-center gap-2 text-xs font-normal text-mf-muted">{list.length}<I.chevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></span>
                </summary>
                <div className="border-t border-mf-line p-1">{list.map(drawBasicField)}</div>
              </details>
            ))}
          </nav>
        </>
      )}

      {mode === 'advanced' && <div className="relative">
        <I.search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-mf-muted" />
        <input className={cx(inputClass, 'pl-9')} placeholder={`Search ${fields.size} fields`} value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search filter fields" />
      </div>}
      {mode === 'advanced' && <nav aria-label="All fields" className="space-y-1">
        {groups.length === 0 && <p className="px-1 text-sm text-mf-muted">No field matches “{query}”.</p>}
        {groups.map(([group, list]) => (
          <details key={group} open={!!query} className="group rounded-[10px] border border-mf-line bg-mf-surface">
            <summary className="flex min-h-10 cursor-pointer list-none items-center justify-between px-3 text-sm font-medium text-mf-ink [&::-webkit-details-marker]:hidden">
              {group}<span className="flex items-center gap-2 text-xs font-normal text-mf-muted">{list.length}<I.chevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></span>
            </summary>
            <ul className="border-t border-mf-line p-1">
              {list.map((field) => (
                <li key={field.id}>
                  <button type="button" onClick={() => onPickField(field)} disabled={!field.available} title={field.description} className="flex w-full items-center gap-2 rounded-[8px] px-2.5 py-2 text-left text-[13px] text-mf-ink-soft hover:bg-mf-sunken disabled:opacity-50">
                    <span className="flex-1">{field.label}</span>
                    {shown.has(field.id) && <I.check className="h-3.5 w-3.5 text-mf-brand" />}
                    <span className="text-[11px] tabular text-mf-muted" aria-hidden="true">{field.coverage.values.toLocaleString('en-IN')}</span>
                    <span className="sr-only">, {field.coverage.values.toLocaleString('en-IN')} values</span>
                  </button>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </nav>}
    </div>
  );
}
