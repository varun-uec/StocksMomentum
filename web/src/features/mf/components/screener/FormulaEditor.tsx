/**
 * Custom formula columns (ui-ux doc 02, FormulaEditor). The backend evaluates
 * them: numeric registry ids, numbers, + − × ÷ and brackets. The browser only
 * checks the name rule and length; it never evaluates the expression.
 */
import { useRef, useState } from 'react';
import type { FieldDef } from '../../api';
import { MAX_FORMULAS, formulaNameError } from '../../view-spec';
import { I } from '../icons';
import { Button, Field, Sheet, inputClass } from '../ui';

const MAX_EXPRESSION = 500;
const EXAMPLES = [
  { name: 'edge_3y', expr: 'cagr_3y - cagr_3y_cat_median', note: 'How far 3Y CAGR beats the category median' },
  { name: 'calmar_3y', expr: 'cagr_3y / (0 - mdd_3y)', note: 'Return per unit of worst fall' },
  { name: 'gain_vs_pain', expr: 'rolling_3y_median / (0 - worst_1y)', note: 'Median 3Y outcome per worst year' },
];

export function FormulaEditor({
  open,
  onClose,
  formulas,
  fields,
  onChange,
}: {
  open: boolean;
  onClose: () => void;
  formulas: Record<string, string>;
  fields: Map<string, FieldDef>;
  onChange: (formulas: Record<string, string>) => void;
}) {
  const [name, setName] = useState('');
  const [expr, setExpr] = useState('');
  const exprRef = useRef<HTMLTextAreaElement>(null);
  const numeric = [...fields.values()].filter((f) => f.type === 'number');
  const nameError = name ? formulaNameError(name, fields, Object.keys(formulas)) : null;
  const exprError = expr.length > MAX_EXPRESSION ? `Use at most ${MAX_EXPRESSION} characters.` : /[^a-z0-9_+\-*/().\s]/.test(expr) ? 'Use field ids, numbers, + - * / and brackets only.' : null;
  const full = Object.keys(formulas).length >= MAX_FORMULAS;
  const canAdd = name && expr.trim() && !nameError && !exprError && !full;

  const insert = (text: string) => {
    const el = exprRef.current;
    const at = el?.selectionStart ?? expr.length;
    setExpr(expr.slice(0, at) + text + expr.slice(el?.selectionEnd ?? at));
    requestAnimationFrame(() => el?.focus());
  };

  return (
    <Sheet open={open} onClose={onClose} title="Custom formulas">
      <div className="space-y-5">
        <p className="text-sm text-mf-ink-soft">
          A formula becomes a column you can sort, filter and export. Fractions stay raw: 12% is 0.12. A missing input gives a missing result; dividing by zero gives “not meaningful”.
        </p>
        {Object.keys(formulas).length > 0 && (
          <ul className="space-y-2">
            {Object.entries(formulas).map(([n, e]) => (
              <li key={n} className="flex items-start gap-2 rounded-[10px] border border-mf-line p-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{n}</p>
                  <code className="block break-all text-xs text-mf-muted">{e}</code>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Remove formula ${n}`}
                  onClick={() => {
                    const next = { ...formulas };
                    delete next[n];
                    onChange(next);
                  }}
                >
                  <I.x className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!canAdd) return;
            onChange({ ...formulas, [name]: expr.trim() });
            setName('');
            setExpr('');
          }}
          className="space-y-3 rounded-[12px] border border-mf-line bg-mf-sunken/60 p-4"
        >
          <Field label="Name" hint={nameError ?? 'Lower-case letters, digits and _.'}>
            <input className={inputClass} value={name} onChange={(e) => setName(e.target.value.toLowerCase())} aria-invalid={!!nameError} placeholder="edge_3y" />
          </Field>
          <Field label="Expression" hint={exprError ?? `${expr.length}/${MAX_EXPRESSION}`}>
            <textarea ref={exprRef} className={`${inputClass} h-24 py-2 font-mono`} value={expr} onChange={(e) => setExpr(e.target.value)} aria-invalid={!!exprError} placeholder="cagr_3y - cagr_3y_cat_median" />
          </Field>
          <Field label="Insert a field">
            <select className={inputClass} value="" onChange={(e) => e.target.value && insert(e.target.value)}>
              <option value="">Choose a numeric field…</option>
              {numeric.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label} ({f.id})
                </option>
              ))}
            </select>
          </Field>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-mf-muted">{full ? `At most ${MAX_FORMULAS} formulas.` : 'The screener checks the expression when it runs.'}</p>
            <Button type="submit" variant="primary" size="sm" disabled={!canAdd}>
              Add formula
            </Button>
          </div>
        </form>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-mf-muted">Examples</p>
          <ul className="space-y-1.5">
            {EXAMPLES.map((x) => (
              <li key={x.name}>
                <button
                  type="button"
                  onClick={() => {
                    setName(x.name);
                    setExpr(x.expr);
                  }}
                  className="w-full rounded-[10px] px-3 py-2 text-left hover:bg-mf-sunken"
                >
                  <code className="text-xs text-mf-brand-strong">{x.expr}</code>
                  <p className="text-xs text-mf-muted">{x.note}</p>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Sheet>
  );
}
