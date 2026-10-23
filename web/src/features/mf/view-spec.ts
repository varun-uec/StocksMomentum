/**
 * A screen's view: filter, sort, columns and formulas, as the API takes them.
 * It travels in the URL (`?v=`, versioned base64url JSON) or names a preset
 * (`?preset=`), so Back, reload and shared links restore the same screen.
 * Percent inputs show human units and serialise as fractions (15% → 0.15).
 */
import type { Condition, FieldDef, FilterNode, Preset, SortKey } from './api';

export const VIEW_VERSION = 1;
export const MAX_FORMULAS = 10;
const MAX_URL_VIEW = 6000;

export interface ScreenView {
  mode: 'all' | 'any';
  conditions: FilterNode[];
  sort: SortKey[];
  columns: string[];
  formulas: Record<string, string>;
}

/** The universe every screen starts from: active Direct Growth plans. */
export const UNIVERSE: Condition[] = [
  { field: 'status', op: 'in', value: ['active'] },
  { field: 'plan', op: 'in', value: ['direct'] },
  { field: 'option', op: 'in', value: ['growth'] },
];

export const DEFAULT_COLUMNS = ['category', 'score', 'cagr_3y', 'sharpe_3y', 'mdd_3y', 'consistency_3y', 'score_cat_rank'];

export function defaultView(extra: Condition[] = []): ScreenView {
  return { mode: 'all', conditions: [...UNIVERSE, ...extra], sort: [{ field: 'score', dir: 'desc' }], columns: DEFAULT_COLUMNS, formulas: {} };
}

export function presetView(preset: Preset): ScreenView {
  const mode = 'all' in preset.filter ? 'all' : 'any';
  const conditions = 'all' in preset.filter ? preset.filter.all : preset.filter.any;
  return { mode, conditions, sort: preset.sort, columns: preset.columns, formulas: {} };
}

export function filterOf(view: ScreenView): { all: FilterNode[] } | { any: FilterNode[] } {
  return view.mode === 'all' ? { all: view.conditions } : { any: view.conditions };
}

export const isCondition = (node: FilterNode): node is Condition => 'field' in node;

function toBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function fromBase64Url(text: string): string {
  const binary = atob(text.replace(/-/g, '+').replace(/_/g, '/'));
  return new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0)));
}

export function encodeView(view: ScreenView): string {
  return toBase64Url(JSON.stringify({ v: VIEW_VERSION, ...view }));
}

/** The view in a link, or null when the link is malformed, too long or from another version. */
export function decodeView(text: string): ScreenView | null {
  if (!text || text.length > MAX_URL_VIEW) return null;
  try {
    const raw = JSON.parse(fromBase64Url(text));
    const ok =
      raw?.v === VIEW_VERSION &&
      (raw.mode === 'all' || raw.mode === 'any') &&
      Array.isArray(raw.conditions) &&
      Array.isArray(raw.sort) &&
      Array.isArray(raw.columns) &&
      raw.columns.every((c: unknown) => typeof c === 'string') &&
      typeof raw.formulas === 'object' &&
      raw.formulas !== null &&
      Object.keys(raw.formulas).length <= MAX_FORMULAS;
    if (!ok) return null;
    return { mode: raw.mode, conditions: raw.conditions, sort: raw.sort, columns: raw.columns, formulas: raw.formulas };
  } catch {
    return null;
  }
}

/** True when a field's values are fractions the user types as percentages. */
export const isPercent = (field: FieldDef | undefined) => field?.unit === 'fraction';

/** A typed number → the API value: percent fields divide by 100. */
export function toApi(field: FieldDef | undefined, input: number): number {
  return isPercent(field) ? Number((input / 100).toPrecision(12)) : input;
}

/** An API value → the number the user sees and edits. */
export function fromApi(field: FieldDef | undefined, value: number): number {
  return isPercent(field) ? Number((value * 100).toPrecision(12)) : value;
}

const OP_TEXT: Record<string, string> = {
  '>': '>',
  '>=': '≥',
  '<': '<',
  '<=': '≤',
  '=': '=',
  '!=': '≠',
  in: 'is',
  not_in: 'is not',
  between: 'between',
  top_pct: 'in top',
  bottom_pct: 'in bottom',
  is_available: 'has a value',
  is_missing: 'has no value',
};

/** A condition in words: `CAGR 3Y ≥ 10%`, `Category is Flexi Cap`. */
export function describe(node: FilterNode, fields: Map<string, FieldDef>, short: (v: string) => string = (v) => v): string {
  if (!isCondition(node)) {
    const [mode, children] = 'all' in node ? ['all', node.all] : ['any', node.any];
    return `${mode === 'all' ? 'All' : 'Any'} of ${children.length} conditions`;
  }
  const field = fields.get(node.field);
  const label = field?.label ?? node.field;
  const op = OP_TEXT[node.op] ?? node.op;
  const one = (v: unknown) => (typeof v === 'number' ? `${fromApi(field, v).toLocaleString('en-IN', { maximumFractionDigits: 4 })}${isPercent(field) ? '%' : ''}` : short(String(v)));
  if (node.op === 'is_available' || node.op === 'is_missing') return `${label} ${op}`;
  if (node.op === 'top_pct' || node.op === 'bottom_pct') return `${label} ${op} ${node.value}%`;
  if (node.op === 'between' && Array.isArray(node.value)) {
    const [lo, hi] = node.value;
    return `${label} ${lo === null ? '' : `≥ ${one(lo)}`}${lo !== null && hi !== null ? ' and ' : ''}${hi === null ? '' : `≤ ${one(hi)}`}`;
  }
  if (Array.isArray(node.value)) {
    const values = node.value.map((v) => short(String(v)));
    return `${label} ${op} ${values.length > 2 ? `${values.slice(0, 2).join(', ')} +${values.length - 2}` : values.join(' or ')}`;
  }
  return `${label} ${op} ${one(node.value)}`;
}

/** A formula name the backend accepts: 1–40 lower-case letters, digits or `_`, not a field id. */
export function formulaNameError(name: string, fields: Map<string, FieldDef>, taken: string[]): string | null {
  if (!/^[a-z][a-z0-9_]{0,39}$/.test(name)) return 'Use 1–40 lower-case letters, digits or _, starting with a letter.';
  if (fields.has(name)) return 'That name is a registry field.';
  if (taken.includes(name)) return 'That name is in use.';
  return null;
}
