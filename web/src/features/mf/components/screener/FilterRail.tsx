/**
 * The screener browser: Basic discovers and displays metrics without changing
 * the result universe. Showing a metric opens its refine control: a range, a
 * value list or a yes/no choice, with no operator to pick. Advanced keeps the
 * full condition editor and query language.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { Condition, FieldDef, FilterNode } from '../../api';
import { formatField, valueLabel } from '../../format';
import { basicCondition, basicControl, describe, fromApi, isCondition, isGate, isPercent, toApi, type BasicControl } from '../../view-spec';
import { I } from '../icons';
import { Segmented, cx, inputClass } from '../ui';

export type FilterMode = 'basic' | 'advanced';

const POPULAR_METRICS = ['ret_1y', 'cagr_3y', 'ter', 'aum_cr', 'vol_3y', 'mdd_3y', 'sharpe_3y', 'score'];
export const METRIC_AS_OF_FIELDS: Record<string, string> = {
  ter: 'ter_as_of',
  aum_cr: 'aum_as_of',
  riskometer: 'riskometer_as_of',
};
const UNIT_SUFFIX: Record<string, string> = { fraction: ' (%)', INR: ' (₹)', 'INR crore': ' (₹ cr)', days: ' (days)', years: ' (years)', percentile: ' (0–100)' };

/** Minimum and maximum inputs; a number field also shows the snapshot's value range. */
function RangeControl({ field, min, max, onChange, onScreen }: { field: FieldDef; min: unknown; max: unknown; onChange: (control: BasicControl) => void; onScreen?: { range: [number, number]; count: number } }) {
  const date = field.type === 'date';
  const shown = (v: unknown) => (v == null ? '' : date ? String(v) : String(fromApi(field, Number(v))));
  const [low, setLow] = useState(shown(min));
  const [high, setHigh] = useState(shown(max));
  // Resync only when the applied bounds change, so a half-typed number is never overwritten.
  const applied = JSON.stringify([min, max]);
  useEffect(() => {
    setLow(shown(min));
    setHigh(shown(max));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applied]);
  const parse = (text: string) => {
    if (!text.trim()) return null;
    if (date) return text;
    const n = Number(text);
    return Number.isFinite(n) ? toApi(field, n) : NaN;
  };
  const apply = (lowText: string, highText: string) => {
    const lo = parse(lowText);
    const hi = parse(highText);
    if (Number.isNaN(lo) || Number.isNaN(hi) || (lo !== null && hi !== null && lo > hi)) return;
    onChange({ kind: 'range', min: lo, max: hi });
  };
  const inverted = low.trim() && high.trim() && (date ? low > high : Number(low) > Number(high));
  const suffix = date ? '' : UNIT_SUFFIX[field.unit ?? ''] ?? '';
  const input = (side: 'Minimum' | 'Maximum', value: string, set: (v: string) => void) => (
    <label className="text-[11px] font-medium text-mf-muted">
      {date ? (side === 'Minimum' ? 'From' : 'To') : side}{suffix}
      <input
        className={`${inputClass} mt-1 h-9 text-sm`}
        type={date ? 'date' : 'number'}
        inputMode={date ? undefined : 'decimal'}
        step="any"
        placeholder="Any"
        aria-label={`${side} ${field.label}`}
        value={value}
        onChange={(e) => {
          set(e.target.value);
          if (!e.target.validity.badInput) apply(side === 'Minimum' ? e.target.value : low, side === 'Maximum' ? e.target.value : high);
        }}
      />
    </label>
  );
  return (
    <div className="grid grid-cols-2 gap-2">
      {input('Minimum', low, setLow)}
      {input('Maximum', high, setHigh)}
      {inverted && <p className="col-span-2 text-xs text-mf-loss" role="alert">Minimum must be less than or equal to maximum. Results keep the last valid range.</p>}
      <p className="col-span-2 text-[11px] text-mf-muted">
        {onScreen ? `The ${onScreen.count.toLocaleString('en-IN')} funds shown run from ${formatField(field, onScreen.range[0])} to ${formatField(field, onScreen.range[1])}. ` : ''}
        {!onScreen && field.range ? `Values run from ${formatField(field, field.range[0])} to ${formatField(field, field.range[1])}. ` : ''}
        Results update as you type. Leave both empty to keep all funds.
      </p>
    </div>
  );
}

/** A checklist of the field's values; none ticked keeps every fund. */
function ValuesControl({ field, picked, onChange }: { field: FieldDef; picked: string[]; onChange: (control: BasicControl) => void }) {
  const [find, setFind] = useState('');
  const all = field.values ?? [];
  const list = all.filter((v) => !find || valueLabel(v).toLowerCase().includes(find.toLowerCase()) || v.toLowerCase().includes(find.toLowerCase()));
  return (
    // A fieldset is min-content wide by default; min-w-0 keeps a long value inside the rail.
    <fieldset className="min-w-0">
      <legend className="sr-only">{field.label} values</legend>
      {all.length > 8 && <input className={`${inputClass} mb-2 h-9 text-sm`} placeholder={`Find in ${all.length} values`} value={find} onChange={(e) => setFind(e.target.value)} aria-label={`Find a ${field.label} value`} />}
      <ul className="mf-scroll max-h-56 space-y-0.5 overflow-y-auto">
        {list.map((v) => (
          <li key={v}>
            <label className="flex min-h-9 cursor-pointer items-center gap-2.5 rounded-[8px] px-1.5 text-sm hover:bg-mf-surface">
              <input type="checkbox" checked={picked.includes(v)} onChange={(e) => onChange({ kind: 'values', picked: e.target.checked ? [...picked, v] : picked.filter((x) => x !== v) })} />
              <span className="truncate" title={v}>{valueLabel(v)}</span>
            </label>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-[11px] text-mf-muted">{picked.length ? `${picked.length} chosen. ` : ''}Tick none to keep all funds.</p>
    </fieldset>
  );
}

function RefineControl({ field, control, onChange, shown }: { field: FieldDef; control: BasicControl; onChange: (control: BasicControl) => void; shown?: { range: [number, number]; count: number } }) {
  if (control.kind === 'values') return <ValuesControl field={field} picked={control.picked} onChange={onChange} />;
  if (control.kind === 'flag')
    return (
      <Segmented
        label={field.label}
        value={control.value === null ? 'any' : String(control.value)}
        onChange={(v) => onChange({ kind: 'flag', value: v === 'any' ? null : v === 'true' })}
        options={[{ value: 'any', label: 'Any' }, { value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }]}
      />
    );
  return <RangeControl field={field} min={control.min} max={control.max} onChange={onChange} onScreen={shown} />;
}

function MetricRow({
  field,
  shown,
  canShow,
  onToggle,
  conditions,
  onConditionChange,
  onEdit,
  onAdvanced,
  open,
  onOpenToggle,
  shownRange,
}: {
  field: FieldDef;
  shown: boolean;
  canShow: boolean;
  onToggle: (field: FieldDef, shown: boolean) => void;
  conditions: FilterNode[];
  onConditionChange: (field: FieldDef, condition: Condition | null) => void;
  onEdit: (field: FieldDef) => void;
  onAdvanced: () => void;
  open: boolean;
  onOpenToggle: (field: FieldDef) => void;
  shownRange?: { range: [number, number]; count: number };
}) {
  const control = basicControl(field, conditions);
  const own = conditions.filter((n): n is Condition => isCondition(n) && n.field === field.id);
  const active = own.length > 0 || control === null;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open || !ref.current) return;
    const group = ref.current.closest('details');
    if (group && !group.open) group.open = true;
    ref.current.scrollIntoView?.({ block: 'nearest' });
  }, [open]);

  return (
    <div ref={ref} className={cx('rounded-[8px] px-2 hover:bg-mf-sunken', open && 'bg-mf-sunken')}>
      <div className="flex min-h-11 items-center gap-2">
        <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 py-2 text-sm text-mf-ink">
          <input
            type="checkbox"
            aria-label={`Show ${field.label}`}
            checked={shown}
            disabled={!field.available || (!shown && !canShow)}
            onChange={(e) => onToggle(field, e.target.checked)}
          />
          <span className="truncate" title={field.description}>{field.label}</span>
          {active && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-mf-brand" title="Filtered" aria-hidden="true" />}
          <span className="ml-auto shrink-0 text-[11px] tabular text-mf-muted" title="Plan options with a value">{field.coverage.values.toLocaleString('en-IN')}<span className="sr-only"> values</span></span>
        </label>
        <button
          type="button"
          disabled={!field.available}
          onClick={() => onOpenToggle(field)}
          className="shrink-0 rounded px-2 py-1.5 text-xs font-medium text-mf-brand hover:bg-mf-brand-soft disabled:opacity-50"
          aria-label={`Filter by ${field.label}`}
          aria-expanded={open}
          title={`Narrow funds by ${field.label}; optional`}
        >
          {open ? 'Close' : 'Filter'}
        </button>
      </div>
      {open && (
        <div className="pb-3 pl-7 pr-1" aria-label={`${field.label} filter`} role="group">
          {control ? (
            <RefineControl field={field} control={control} shown={shownRange} onChange={(next) => onConditionChange(field, basicCondition(field, next))} />
          ) : own.length ? (
            <p className="text-xs text-mf-ink-soft">
              {own.map((c) => describe(c, new Map([[field.id, field]]), valueLabel)).join('; ')}.{' '}
              <button type="button" className="font-medium text-mf-brand underline underline-offset-2" onClick={() => onEdit(field)}>Edit condition</button>
            </p>
          ) : (
            <p className="text-xs text-mf-ink-soft">
              A condition group uses {field.label}.{' '}
              <button type="button" className="font-medium text-mf-brand underline underline-offset-2" onClick={onAdvanced}>Show advanced logic</button>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function FilterRail({
  view,
  fields,
  onShowMetric,
  onPickField,
  onConditionChange,
  onEditField,
  openField,
  onOpenField,
  shownRanges,
  matched,
  mode,
  onModeChange,
  maxColumns,
}: {
  view: { columns: string[]; mode: 'all' | 'any'; conditions: FilterNode[] };
  fields: Map<string, FieldDef>;
  onShowMetric: (field: FieldDef, shown: boolean) => void;
  onPickField: (field: FieldDef) => void;
  onConditionChange: (field: FieldDef, condition: Condition | null) => void;
  onEditField: (field: FieldDef) => void;
  openField: string | null;
  onOpenField: (id: string | null) => void;
  shownRanges?: Map<string, [number, number]>;
  matched?: number;
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
      // Basic lists a popular metric once, at the top, so it has one set of controls.
      if (!q && mode === 'basic' && POPULAR_METRICS.includes(field.id)) continue;
      map.set(field.group, [...(map.get(field.group) ?? []), field]);
    }
    return [...map.entries()];
  }, [fields, query, mode]);
  const shown = new Set(view.columns);
  const canShow = (field: FieldDef) => shown.has(field.id) || shown.size < maxColumns;
  const toggle = (field: FieldDef, enabled: boolean) => onShowMetric(field, enabled);
  const drawBasicField = (field: FieldDef) => (
    <MetricRow
      key={field.id}
      field={field}
      shown={shown.has(field.id)}
      canShow={canShow(field)}
      onToggle={toggle}
      conditions={view.conditions}
      onConditionChange={onConditionChange}
      onEdit={onEditField}
      onAdvanced={() => onModeChange('advanced')}
      open={openField === field.id}
      onOpenToggle={(picked) => onOpenField(openField === picked.id ? null : picked.id)}
      shownRange={shownRanges?.has(field.id) && matched ? { range: shownRanges.get(field.id)!, count: matched } : undefined}
    />
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
