/**
 * Edit one screen condition with inputs that match the field's type (ui-ux doc 02,
 * FilterBuilder): numbers in display units, enum checklists, dates, booleans.
 * The operators are the backend's per type; nothing here is an unlabelled slider.
 */
import { useMemo, useState } from 'react';
import type { Condition, FieldDef, Op } from '../../api';
import { categoryShort, enumLabel, formatField } from '../../format';
import { fromApi, isPercent, toApi } from '../../view-spec';
import { Button, Field, Sheet, inputClass } from '../ui';

const OPS: Record<FieldDef['type'], { op: Op; label: string }[]> = {
  number: [
    { op: '>=', label: 'at least' },
    { op: '<=', label: 'at most' },
    { op: 'between', label: 'between' },
    { op: '>', label: 'more than' },
    { op: '<', label: 'less than' },
    { op: '=', label: 'equal to' },
    { op: '!=', label: 'not equal to' },
    { op: 'top_pct', label: 'in the top % of all funds' },
    { op: 'bottom_pct', label: 'in the bottom % of all funds' },
    { op: 'is_available', label: 'has a value' },
    { op: 'is_missing', label: 'has no value' },
  ],
  date: [
    { op: '>=', label: 'on or after' },
    { op: '<=', label: 'on or before' },
    { op: 'between', label: 'between' },
    { op: 'is_available', label: 'has a date' },
    { op: 'is_missing', label: 'has no date' },
  ],
  boolean: [
    { op: '=', label: 'is' },
    { op: 'is_missing', label: 'has no value' },
  ],
  enum: [
    { op: 'in', label: 'is any of' },
    { op: 'not_in', label: 'is none of' },
    { op: 'is_missing', label: 'has no value' },
  ],
};

const enumText = (field: FieldDef, v: string) => (field.id === 'category' ? categoryShort(v) : enumLabel(v));

function initialText(field: FieldDef, v: unknown): string {
  if (v === null || v === undefined) return '';
  return typeof v === 'number' ? String(fromApi(field, v)) : String(v);
}

export function ConditionEditor({
  field,
  initial,
  onSave,
  onClose,
}: {
  field: FieldDef | null;
  initial?: Condition;
  onSave: (condition: Condition) => void;
  onClose: () => void;
}) {
  return (
    <Sheet open={!!field} onClose={onClose} title={field ? `${initial ? 'Edit' : 'Add'} condition: ${field.label}` : ''}>
      {field && <EditorBody key={field.id + (initial ? JSON.stringify(initial) : '')} field={field} initial={initial} onSave={onSave} onClose={onClose} />}
    </Sheet>
  );
}

function EditorBody({ field, initial, onSave, onClose }: { field: FieldDef; initial?: Condition; onSave: (c: Condition) => void; onClose: () => void }) {
  const ops = OPS[field.type];
  const [op, setOp] = useState<Op>(initial?.op ?? ops[0].op);
  const pair = Array.isArray(initial?.value) && initial?.op === 'between' ? (initial.value as unknown[]) : [];
  const [a, setA] = useState(initial && initial.op !== 'between' && !Array.isArray(initial.value) ? initialText(field, initial.value) : initialText(field, pair[0]));
  const [b, setB] = useState(initialText(field, pair[1]));
  const [picked, setPicked] = useState<string[]>(Array.isArray(initial?.value) && field.type === 'enum' ? (initial.value as string[]) : []);
  const [bool, setBool] = useState(initial?.value === false ? 'false' : 'true');
  const [filter, setFilter] = useState('');
  const unit = isPercent(field) ? '%' : field.unit === 'percentile' ? 'percentile (0–100)' : field.unit === 'INR' ? '₹' : field.unit === 'days' ? 'days' : '';
  const values = useMemo(() => (field.values ?? []).filter((v) => v.toLowerCase().includes(filter.toLowerCase())), [field.values, filter]);

  const parse = (text: string): number | string | null => {
    if (text.trim() === '') return null;
    if (field.type === 'date') return text;
    const n = Number(text);
    return Number.isFinite(n) ? toApi(field, n) : NaN;
  };

  let value: unknown = null;
  let error: string | null = null;
  if (op === 'is_available' || op === 'is_missing') value = null;
  else if (field.type === 'enum') {
    value = picked;
    if (!picked.length) error = 'Choose at least one value.';
  } else if (field.type === 'boolean') value = bool === 'true';
  else if (op === 'between') {
    value = [parse(a), parse(b)];
    const [lo, hi] = value as (number | null)[];
    if (Number.isNaN(lo) || Number.isNaN(hi)) error = 'Enter numbers only.';
    else if (lo === null && hi === null) error = 'Enter a minimum, a maximum or both.';
    else if (lo !== null && hi !== null && lo > hi) error = 'The minimum is above the maximum.';
  } else if (op === 'top_pct' || op === 'bottom_pct') {
    const n = Number(a);
    value = n;
    if (!(n > 0 && n <= 100)) error = 'Enter a percentage from 0 to 100.';
  } else {
    value = parse(a);
    if (value === null) error = 'Enter a value.';
    else if (Number.isNaN(value)) error = 'Enter a number.';
  }

  const percentOp = op === 'top_pct' || op === 'bottom_pct';
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!error) onSave({ field: field.id, op, value });
      }}
      className="space-y-5"
    >
      <p className="text-sm text-mf-ink-soft">{field.description}</p>
      <p className="text-xs text-mf-muted">
        {field.coverage.values.toLocaleString('en-IN')} plan options have a value.
        {field.type === 'number' && ' A fund with no value never matches a comparison, including “not equal to”.'}
      </p>
      <Field label="Condition">
        <select className={inputClass} value={op} onChange={(e) => setOp(e.target.value as Op)}>
          {ops.map((o) => (
            <option key={o.op} value={o.op}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>

      {field.type === 'enum' && op !== 'is_missing' && (
        <fieldset>
          <legend className="mb-1 text-[13px] font-medium text-mf-ink-soft">
            Values <span className="font-normal text-mf-muted">({picked.length} chosen)</span>
          </legend>
          {(field.values?.length ?? 0) > 8 && <input className={`${inputClass} mb-2`} placeholder="Find a value" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Find a value" />}
          <ul className="mf-scroll max-h-72 space-y-0.5 overflow-y-auto rounded-[10px] border border-mf-line p-1">
            {values.map((v) => (
              <li key={v}>
                <label className="flex min-h-9 cursor-pointer items-center gap-2.5 rounded-[8px] px-2 text-sm hover:bg-mf-sunken">
                  <input type="checkbox" checked={picked.includes(v)} onChange={(e) => setPicked((p) => (e.target.checked ? [...p, v] : p.filter((x) => x !== v)))} />
                  <span>{enumText(field, v)}</span>
                  {field.id === 'category' && <span className="ml-auto truncate text-xs text-mf-muted">{v.split(' - ')[0]}</span>}
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      )}

      {field.type === 'boolean' && op === '=' && (
        <Field label="Value">
          <select className={inputClass} value={bool} onChange={(e) => setBool(e.target.value)}>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </Field>
      )}

      {(field.type === 'number' || field.type === 'date') && op !== 'is_available' && op !== 'is_missing' && (
        <div className={op === 'between' ? 'grid grid-cols-2 gap-3' : ''}>
          <Field label={op === 'between' ? 'Minimum' : percentOp ? 'Top or bottom share' : 'Value'} hint={percentOp ? 'Share of every fund in the snapshot with a value, across all categories, before other conditions apply. For a standing among category peers, filter a “category percentile” field instead.' : unit && `In ${unit}`}>
            <input className={inputClass} type={field.type === 'date' ? 'date' : 'number'} step="any" inputMode="decimal" value={a} onChange={(e) => setA(e.target.value)} autoFocus />
          </Field>
          {op === 'between' && (
            <Field label="Maximum" hint="Leave a side empty for no limit.">
              <input className={inputClass} type={field.type === 'date' ? 'date' : 'number'} step="any" inputMode="decimal" value={b} onChange={(e) => setB(e.target.value)} />
            </Field>
          )}
        </div>
      )}

      {error && (a || b || picked.length || op === 'between') ? (
        <p role="alert" className="text-sm text-mf-loss">
          {error}
        </p>
      ) : null}
      {!error && field.type === 'number' && typeof value === 'number' && !percentOp && (
        <p className="text-xs text-mf-muted">Sent as {formatField(field, value)}.</p>
      )}
      <div className="flex justify-end gap-2 pt-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={!!error}>
          {initial ? 'Update condition' : 'Add condition'}
        </Button>
      </div>
    </form>
  );
}
