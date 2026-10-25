/**
 * A screen's view: filter, sort, columns and formulas, as the API takes them.
 * It travels in the URL (`?v=`, versioned base64url JSON) or names a preset
 * (`?preset=`), so Back, reload and shared links restore the same screen.
 * Percent inputs show human units and serialise as fractions (15% → 0.15).
 */
import type { Condition, FieldDef, FilterNode, Preset, SortKey } from './api';
import { date } from './format';

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

/** Fields that define the starting universe. "Match any" never ORs them (audit F-05). */
export const UNIVERSE_FIELDS = new Set(['status', 'plan', 'option']);

export const DEFAULT_CATEGORY = 'Equity Scheme - Flexi Cap Fund';
export const DEFAULT_COLUMNS = ['score', 'cagr_3y', 'sharpe_3y', 'mdd_3y', 'consistency_3y', 'score_cat_rank'];

/**
 * The opening screen: one category, by score (audit F-06). The score is a
 * percentile inside a category, so it ranks funds fairly only within one.
 */
export function defaultView(extra: Condition[] = []): ScreenView {
  return {
    mode: 'all',
    conditions: [...UNIVERSE, { field: 'category', op: 'in', value: [DEFAULT_CATEGORY] }, ...extra],
    sort: [{ field: 'score', dir: 'desc' }],
    columns: DEFAULT_COLUMNS,
    formulas: {},
  };
}

/** True when a universe condition (status, plan or option) is a fixed gate. */
export const isGate = (node: FilterNode): boolean => isCondition(node) && UNIVERSE_FIELDS.has(node.field);

/** Score across several categories mixes percentiles of different peer groups. */
export function mixesCategories(view: ScreenView): boolean {
  if (view.sort[0]?.field !== 'score' && view.sort[0]?.field !== 'score_cat_rank') return false;
  const oneCategory = view.conditions.some((c) => isCondition(c) && c.field === 'category' && c.op === 'in' && Array.isArray(c.value) && c.value.length === 1);
  return view.mode === 'any' || !oneCategory;
}

export function presetView(preset: Preset): ScreenView {
  const mode = 'all' in preset.filter ? 'all' : 'any';
  const conditions = 'all' in preset.filter ? preset.filter.all : preset.filter.any;
  return { mode, conditions, sort: preset.sort, columns: preset.columns, formulas: {} };
}

/**
 * The API filter. In "Match any" the universe gates still apply to every fund:
 * ALL(gates, ANY(rest)). The API allows two group levels, so a saved group must
 * not gain a third (independent audit A-08): an ANY group merges into the ANY, and
 * when an ALL group is among the rest the gates move inside each alternative,
 * ANY(ALL(gates, …), …), which selects the same funds.
 */
export function filterOf(view: ScreenView): { all: FilterNode[] } | { any: FilterNode[] } {
  if (view.mode === 'all') return { all: view.conditions };
  const gates = view.conditions.filter(isGate);
  const rest = view.conditions.filter((c) => !isGate(c)).flatMap((c) => (!isCondition(c) && 'any' in c ? c.any : [c]));
  if (!gates.length) return { any: rest };
  if (!rest.length) return { all: gates };
  if (rest.every(isCondition)) return { all: [...gates, { any: rest }] };
  return { any: rest.map((c) => ({ all: [...gates, ...(!isCondition(c) && 'all' in c ? c.all : [c])] })) };
}

export function isCondition(node: FilterNode): node is Condition {
  return 'field' in node;
}

/** A Basic-mode control for one field: a range, a value list or a yes/no flag. */
export type BasicControl =
  | { kind: 'range'; min: unknown; max: unknown }
  | { kind: 'values'; picked: string[] }
  | { kind: 'flag'; value: boolean | null };

const mentions = (node: FilterNode, field: string): boolean =>
  isCondition(node) ? node.field === field : ('all' in node ? node.all : node.any).some((n) => mentions(n, field));

/**
 * The field's conditions as one Basic control, or null when only the full editor can show them
 * (a top or bottom share, "none of", missing values, a group). A min and a max condition merge into one range.
 */
export function basicControl(field: FieldDef, conditions: FilterNode[]): BasicControl | null {
  if (conditions.some((n) => !isCondition(n) && mentions(n, field.id))) return null;
  const own = conditions.filter((n): n is Condition => isCondition(n) && n.field === field.id);
  if (field.type === 'enum') {
    if (!own.length) return { kind: 'values', picked: [] };
    const [c] = own;
    return own.length === 1 && c.op === 'in' && Array.isArray(c.value) ? { kind: 'values', picked: c.value.map(String) } : null;
  }
  if (field.type === 'boolean') {
    if (!own.length) return { kind: 'flag', value: null };
    const [c] = own;
    return own.length === 1 && c.op === '=' && typeof c.value === 'boolean' ? { kind: 'flag', value: c.value } : null;
  }
  let min: unknown = null;
  let max: unknown = null;
  for (const c of own) {
    if (c.op === 'between' && Array.isArray(c.value) && min === null && max === null) [min, max] = c.value;
    else if ((c.op === '>=' || c.op === '>') && min === null) min = c.value;
    else if ((c.op === '<=' || c.op === '<') && max === null) max = c.value;
    else return null;
  }
  return { kind: 'range', min, max };
}

/** The one condition a Basic control sets, or null when it keeps every fund. */
export function basicCondition(field: FieldDef, control: BasicControl): Condition | null {
  if (control.kind === 'values') return control.picked.length ? { field: field.id, op: 'in', value: control.picked } : null;
  if (control.kind === 'flag') return control.value === null ? null : { field: field.id, op: '=', value: control.value };
  return control.min === null && control.max === null ? null : { field: field.id, op: 'between', value: [control.min, control.max] };
}

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
  // A true minus sign, as in the tables, and dates as people write them.
  const one = (v: unknown) =>
    typeof v === 'number'
      ? `${fromApi(field, v).toLocaleString('en-IN', { maximumFractionDigits: 4 }).replace(/^-/, '−')}${isPercent(field) ? '%' : ''}`
      : field?.type === 'date'
        ? date(v)
        : short(String(v));
  if (node.op === 'is_available' || node.op === 'is_missing') return `${label} ${op}`;
  if (node.op === 'top_pct' || node.op === 'bottom_pct') return `${label} ${op} ${node.value}%`;
  // A category percentile is 100 for the best fund (for volatility, the calmest), so
  // "≥ 50" reads as "in its category's best 50%", never as "more volatile than half".
  if (node.field.endsWith('_cat_pct') && (node.op === '>=' || node.op === '>') && typeof node.value === 'number')
    return `${label.replace(/ category percentile$/, '')} in its category’s best ${100 - node.value}%`;
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

/** Resolve saved/URL enum aliases before rendering controls; never mutate the saved record. */
export function normalizeEnumAliases(view: ScreenView, fields: readonly FieldDef[]): ScreenView {
  const key = (s: string) => s.trim().replace(/\s+/g, ' ').toLowerCase();
  const aliases = new Map(fields.filter((f) => f.aliases).map((f) => [f.id, new Map(Object.entries(f.aliases!).map(([a, v]) => [key(a), v]))]));
  const normalize = (node: FilterNode): FilterNode => {
    if (!isCondition(node)) return 'all' in node ? { all: node.all.map(normalize) } : { any: node.any.map(normalize) };
    const known = aliases.get(node.field);
    if (!known || !['in', 'not_in'].includes(node.op) || !Array.isArray(node.value)) return node;
    return { ...node, value: [...new Set(node.value.map((v: unknown) => typeof v === 'string' ? known.get(key(v)) ?? v : v))] };
  };
  return { ...view, conditions: view.conditions.map(normalize) };
}
