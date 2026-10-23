/**
 * Display formatting for MF values. The API sends fractions (0.1218 = 12.18%),
 * category percentiles (0–100) and rupees; this module turns them into text and
 * nothing else. It never computes a new financial measure.
 */
import type { FieldDef, Missing, Unit } from './api';

const MINUS = '−';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

function signed(text: string, value: number, sign: boolean): string {
  if (value < 0) return `${MINUS}${text}`;
  return sign && value > 0 ? `+${text}` : text;
}

/** A fraction as a percentage: `pct(0.1218)` → `12.2%`; `sign` adds `+` to gains. */
export function pct(value: unknown, digits = 1, sign = false): string {
  if (!isNum(value)) return '—';
  const text = `${Math.abs(value * 100).toFixed(digits)}%`;
  return Number(text.slice(0, -1)) === 0 ? `${(0).toFixed(digits)}%` : signed(text, value, sign);
}

export function num(value: unknown, digits = 2): string {
  if (!isNum(value)) return '—';
  return signed(Math.abs(value).toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits }), value, false);
}

/** Rupees with Indian digit grouping: `₹7,98,278`. `compact` gives `₹7.98 L` and `₹2.05 Cr`. */
export function inr(value: unknown, compact = false): string {
  if (!isNum(value)) return '—';
  const abs = Math.abs(value);
  let text: string;
  if (compact && abs >= 1e7) text = `₹${(abs / 1e7).toFixed(2)} Cr`;
  else if (compact && abs >= 1e5) text = `₹${(abs / 1e5).toFixed(2)} L`;
  else text = `₹${abs.toLocaleString('en-IN', { maximumFractionDigits: abs < 1000 ? 2 : 0 })}`;
  return signed(text, value, false);
}

/** `2026-10-22` → `22 Oct 2026`. */
export function date(iso: unknown): string {
  if (typeof iso !== 'string' || iso.length < 10) return '—';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
}

/** `2026-09` → `Sep 2026`. */
export function month(iso: string): string {
  const [y, m] = iso.split('-');
  return `${MONTHS[Number(m) - 1]} ${y}`;
}

export const shortDate = (iso: string) => `${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(2, 4)}`;

const MISSING: Record<string, string> = {
  not_recovered: 'Not recovered',
  history_too_short: 'History too short',
  no_nav: 'No NAV',
  no_recent_nav: 'No recent NAV',
  gap_at_start: 'NAV gap at start',
  gap_in_window: 'NAV gap in window',
  zero_denominator: 'Not meaningful',
  no_peer_group: 'No peer group',
  too_few_peers: 'Too few peers',
  no_risk_free: 'No risk-free data',
  no_pair: 'No direct/regular pair',
};

/** Why a value is missing, in words. Unknown reasons show as sent. */
export function missingLabel(state: Missing | null | undefined): string {
  if (!state) return 'Not available';
  return MISSING[state.reason] ?? state.reason.replace(/_/g, ' ');
}

/** The unit of a field; a category median has its base field's unit. */
export function unitOf(field: FieldDef | undefined, fields?: Map<string, FieldDef>): Unit {
  if (!field) return null;
  if (field.id.endsWith('_cat_median') && fields) return fields.get(field.id.replace(/_cat_median$/, ''))?.unit ?? null;
  return field.unit;
}

/** One registry value as text, by its unit. */
export function formatValue(value: unknown, unit: Unit, type: FieldDef['type'] = 'number', change = false): string {
  if (value === null || value === undefined) return '—';
  if (type === 'date') return date(value);
  if (type === 'boolean') return value ? 'Yes' : 'No';
  if (type === 'enum') return enumLabel(String(value));
  switch (unit) {
    case 'fraction':
      return pct(value, Math.abs(Number(value)) < 0.1 ? 2 : 1);
    case 'percentile':
      if (!isNum(value)) return '—';
      return change ? signed(Math.abs(value).toFixed(1), value, true) : value.toFixed(1);
    case 'ratio':
      return num(value, 2);
    case 'INR':
      return inr(value);
    case 'quartile':
      if (!isNum(value)) return '—';
      return change ? signed(Math.abs(value).toFixed(0), value, true) : `Q${value}`;
    case 'rank':
      return isNum(value) ? `#${value}` : '—';
    case 'days':
      return isNum(value) ? `${value.toLocaleString('en-IN')} d` : '—';
    case 'count':
      return isNum(value) ? value.toLocaleString('en-IN') : '—';
    default:
      return isNum(value) ? num(value, 2) : String(value);
  }
}

/** A registry field's value as text; `*_chg_*` and `*_change_*` fields show a signed change. */
export function formatField(field: FieldDef | undefined, value: unknown, fields?: Map<string, FieldDef>): string {
  if (!field) return isNum(value) ? num(value) : String(value ?? '—');
  return formatValue(value, unitOf(field, fields), field.type, /_(chg|change)_/.test(field.id));
}

const ENUM_LABELS: Record<string, string> = {
  direct: 'Direct',
  regular: 'Regular',
  growth: 'Growth',
  idcw: 'IDCW',
  active: 'Active',
  historical: 'Historical',
  no_nav: 'No NAV',
  open_ended: 'Open ended',
  close_ended: 'Close ended',
  interval: 'Interval',
  nav: 'NAV',
};

export function enumLabel(value: string): string {
  return ENUM_LABELS[value] ?? value;
}

/** `Equity Scheme - Flexi Cap Fund` → `Flexi Cap`. */
export function categoryShort(category: string | null | undefined): string {
  if (!category) return '—';
  const tail = category.includes(' - ') ? category.slice(category.indexOf(' - ') + 3) : category;
  return tail.replace(/ Fund$/, '').trim() || category;
}

/** `Equity Scheme - Flexi Cap Fund` → `Equity`. */
export function assetClassOf(category: string): string {
  return category.split(' ')[0].replace(/\/.*$/, '');
}

/** Gain, loss or flat, for colour plus sign; colour never carries the meaning alone. */
export function tone(value: unknown): 'gain' | 'loss' | 'flat' {
  if (!isNum(value) || value === 0) return 'flat';
  return value > 0 ? 'gain' : 'loss';
}

/** `Parag Parikh Flexi Cap Fund - Direct Plan - Growth` → scheme name only. */
export function schemeName(name: string): string {
  return name.split(/ - (Direct|Regular)/i)[0].trim();
}
