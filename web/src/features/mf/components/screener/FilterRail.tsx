/**
 * The screener's filter rail: five quick filters with labelled range inputs, then
 * every registry field by group, searchable by label or id. Picking a field
 * opens the condition editor; nothing here hardcodes the field list.
 */
import { useMemo, useState } from 'react';
import type { Condition, FieldDef } from '../../api';
import { categoryShort } from '../../format';
import { fromApi, isCondition, toApi, type ScreenView } from '../../view-spec';
import { I } from '../icons';
import { cx, inputClass } from '../ui';

interface Quick {
  field: string;
  label: string;
  op: '>=' | '<=';
  min: number;
  max: number;
  step: number;
  start: number;
  suffix: string;
}

/** Quick filters edit one `>=`/`<=` condition on their field, in display units. */
const QUICK: Quick[] = [
  { field: 'score', label: 'Wickstreet score', op: '>=', min: 0, max: 100, step: 5, start: 60, suffix: '' },
  { field: 'cagr_3y', label: 'CAGR 3Y at least', op: '>=', min: -10, max: 40, step: 1, start: 10, suffix: '%' },
  { field: 'sharpe_3y', label: 'Sharpe 3Y at least', op: '>=', min: -1, max: 2.5, step: 0.1, start: 0.4, suffix: '' },
  { field: 'mdd_3y', label: 'Worst 3Y fall no deeper than', op: '>=', min: -60, max: 0, step: 1, start: -35, suffix: '%' },
  { field: 'consistency_3y', label: 'Consistency 3Y at least', op: '>=', min: 0, max: 100, step: 5, start: 60, suffix: '%' },
];

const top = (view: ScreenView) => view.conditions.filter(isCondition);

function setCondition(view: ScreenView, field: string, condition: Condition | null): ScreenView {
  const index = view.conditions.findIndex((c) => isCondition(c) && c.field === field);
  const conditions = [...view.conditions];
  if (condition === null) {
    if (index >= 0) conditions.splice(index, 1);
  } else if (index >= 0) conditions[index] = condition;
  else conditions.push(condition);
  return { ...view, conditions };
}

function QuickFilter({ quick, view, fields, onChange }: { quick: Quick; view: ScreenView; fields: Map<string, FieldDef>; onChange: (v: ScreenView) => void }) {
  const field = fields.get(quick.field);
  const current = top(view).find((c) => c.field === quick.field && c.op === quick.op && typeof c.value === 'number');
  const other = !current && top(view).some((c) => c.field === quick.field);
  const shown = current ? fromApi(field, current.value as number) : quick.start;
  const id = `quick-${quick.field}`;
  if (!field) return null;
  return (
    <div className="py-2.5">
      <div className="flex items-center gap-2.5">
        <input
          id={`${id}-on`}
          type="checkbox"
          checked={!!current}
          disabled={other}
          onChange={(e) => onChange(setCondition(view, quick.field, e.target.checked ? { field: quick.field, op: quick.op, value: toApi(field, quick.start) } : null))}
        />
        <label htmlFor={`${id}-on`} className="flex-1 text-sm text-mf-ink">
          {quick.label}
        </label>
        <span className="text-sm font-medium tabular text-mf-ink-soft">
          {current ? `${shown}${quick.suffix}` : '—'}
        </span>
      </div>
      {other && <p className="mt-1 pl-6 text-xs text-mf-muted">Edit its condition above the results.</p>}
      {current && (
        <input
          type="range"
          aria-label={quick.label}
          aria-valuetext={`${shown}${quick.suffix}`}
          min={quick.min}
          max={quick.max}
          step={quick.step}
          value={shown}
          onChange={(e) => onChange(setCondition(view, quick.field, { field: quick.field, op: quick.op, value: toApi(field, Number(e.target.value)) }))}
          className="mt-2 w-full"
        />
      )}
    </div>
  );
}

function CategoryQuick({ view, fields, onChange }: { view: ScreenView; fields: Map<string, FieldDef>; onChange: (v: ScreenView) => void }) {
  const field = fields.get('category');
  const current = top(view).find((c) => c.field === 'category' && c.op === 'in');
  const values = (current?.value as string[] | undefined) ?? [];
  if (!field) return null;
  return (
    <div className="py-2.5">
      <label htmlFor="quick-category" className="mb-1.5 block text-sm text-mf-ink">
        Category
      </label>
      <select
        id="quick-category"
        className={inputClass}
        value={values.length === 1 ? values[0] : values.length > 1 ? '__many' : ''}
        onChange={(e) => {
          const v = e.target.value;
          if (v === '__many') return;
          onChange(setCondition(view, 'category', v ? { field: 'category', op: 'in', value: [v] } : null));
        }}
      >
        <option value="">All categories</option>
        {values.length > 1 && <option value="__many">{values.length} categories chosen</option>}
        {['Equity', 'Debt', 'Hybrid', 'Solution', 'Other', 'Income/Debt', 'Life'].map((group) => {
          const options = (field.values ?? []).filter((c) => c.startsWith(group));
          return options.length ? (
            <optgroup key={group} label={group === 'Life' ? 'Life cycle' : group}>
              {options.map((c) => (
                <option key={c} value={c}>
                  {categoryShort(c)}
                </option>
              ))}
            </optgroup>
          ) : null;
        })}
      </select>
    </div>
  );
}

export function FilterRail({
  view,
  fields,
  onChange,
  onPickField,
}: {
  view: ScreenView;
  fields: Map<string, FieldDef>;
  onChange: (view: ScreenView) => void;
  onPickField: (field: FieldDef) => void;
}) {
  const [query, setQuery] = useState('');
  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const map = new Map<string, FieldDef[]>();
    for (const f of fields.values()) {
      if (q && !f.label.toLowerCase().includes(q) && !f.id.includes(q) && !f.description.toLowerCase().includes(q)) continue;
      map.set(f.group, [...(map.get(f.group) ?? []), f]);
    }
    return [...map.entries()];
  }, [fields, query]);
  const used = new Set(top(view).map((c) => c.field));

  return (
    <div className="space-y-4">
      <div className="relative">
        <I.search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-mf-muted" />
        <input className={cx(inputClass, 'pl-9')} placeholder={`Search ${fields.size} fields`} value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search filter fields" />
      </div>
      {!query && (
        <section aria-labelledby="quick-filters" className="rounded-[12px] border border-mf-line bg-mf-surface px-4 py-2">
          <h3 id="quick-filters" className="pt-2 text-xs font-semibold uppercase tracking-[0.08em] text-mf-muted">
            Popular filters
          </h3>
          <div className="divide-y divide-mf-line">
            {QUICK.slice(0, 1).map((q) => (
              <QuickFilter key={q.field} quick={q} view={view} fields={fields} onChange={onChange} />
            ))}
            <CategoryQuick view={view} fields={fields} onChange={onChange} />
            {QUICK.slice(1).map((q) => (
              <QuickFilter key={q.field} quick={q} view={view} fields={fields} onChange={onChange} />
            ))}
          </div>
        </section>
      )}
      <nav aria-label="All fields" className="space-y-1">
        {groups.length === 0 && <p className="px-1 text-sm text-mf-muted">No field matches “{query}”.</p>}
        {groups.map(([group, list]) => (
          <details key={group} open={!!query} className="group rounded-[10px] border border-mf-line bg-mf-surface">
            <summary className="flex min-h-10 cursor-pointer list-none items-center justify-between px-3 text-sm font-medium text-mf-ink [&::-webkit-details-marker]:hidden">
              {group}
              <span className="flex items-center gap-2 text-xs font-normal text-mf-muted">
                {list.length}
                <I.chevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
              </span>
            </summary>
            <ul className="border-t border-mf-line p-1">
              {list.map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() => onPickField(f)}
                    disabled={!f.available}
                    title={f.description}
                    className="flex w-full items-center gap-2 rounded-[8px] px-2.5 py-2 text-left text-[13px] text-mf-ink-soft hover:bg-mf-sunken disabled:opacity-50"
                  >
                    <span className="flex-1">{f.label}</span>
                    {used.has(f.id) && <I.check className="h-3.5 w-3.5 text-mf-brand" />}
                    <span className="text-[11px] tabular text-mf-muted" aria-hidden="true">{f.coverage.values.toLocaleString('en-IN')}</span>
                    <span className="sr-only">, {f.coverage.values.toLocaleString('en-IN')} values</span>
                  </button>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </nav>
    </div>
  );
}
