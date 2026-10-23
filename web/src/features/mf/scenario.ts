/**
 * Investment-lab inputs, the calculator request they make, and the URL that
 * carries a saved scenario back into the lab. Every request field round-trips
 * (independent audit A-05), so a reopened scenario is the scenario that was saved.
 *
 * The tax class is never assumed (audit A-04). An empty class lets the server take
 * it from the fund's category, or ask for it when the category does not settle it.
 */
import type { CalculatorKind, CalculatorRequest, TaxClass } from './api';

export const CALCULATOR_KINDS: CalculatorKind[] = ['sip', 'lumpsum', 'swp', 'stp'];

export interface Inputs {
  kind: CalculatorKind;
  code: string;
  target: string;
  amount: string;
  instalment: string;
  day: string;
  start: string;
  end: string;
  stepUp: string;
  /** '' = from the fund's category, decided by the server. */
  taxClass: TaxClass | '';
  slab: string;
}

/** What a saved scenario keeps besides its request: where its numbers came from. */
export interface ScenarioProvenance {
  data_revision: number;
  method_version: number;
  as_of: string;
  calculator_version: number;
  tax_class: string | null;
  tax_class_source: 'chosen' | 'category';
}

export const today = () => new Date().toISOString().slice(0, 10);
export const yearsAgo = (n: number, from = today()) => `${Number(from.slice(0, 4)) - n}${from.slice(4, 8)}01`;

/** Starting amounts per kind: an SWP or STP must outlast a 5-year window on a typical equity fund (audit F-12). */
export const KIND_DEFAULTS: Record<CalculatorKind, Pick<Inputs, 'amount' | 'instalment'>> = {
  sip: { amount: '10000', instalment: '5000' },
  lumpsum: { amount: '100000', instalment: '5000' },
  swp: { amount: '1000000', instalment: '6000' },
  stp: { amount: '500000', instalment: '10000' },
};

export function defaultInputs(kind: CalculatorKind, code: string, target: string, now = today()): Inputs {
  return { kind, code, target, ...KIND_DEFAULTS[kind], day: '1', start: yearsAgo(5, now), end: now, stepUp: '0', taxClass: '', slab: '30' };
}

/** Inputs → a calculator request, or the first problem to fix. */
export function toRequest(i: Inputs, now = today()): { body?: CalculatorRequest; error?: string } {
  const amount = Number(i.amount);
  if (!i.code) return { error: 'Choose a fund.' };
  if (!(amount > 0)) return { error: 'The amount must be more than zero.' };
  if (!i.start || !i.end || i.start >= i.end) return { error: 'The start date must be before the end date.' };
  if (i.end > now) return { error: 'The end date cannot be in the future: this is a historical simulation.' };
  const day = Number(i.day);
  if (i.kind !== 'lumpsum' && !(Number.isInteger(day) && day >= 1 && day <= 28)) return { error: 'Pick a day of the month from 1 to 28.' };
  const body: CalculatorRequest = { code: i.code, amount, start: i.start, end: i.end };
  if (i.taxClass) body.tax_class = i.taxClass;
  if (i.kind !== 'lumpsum') body.day = day;
  if (i.kind === 'sip' && i.stepUp) {
    const s = Number(i.stepUp);
    if (!(s >= 0 && s <= 100)) return { error: 'The step-up is a yearly percentage from 0 to 100.' };
    if (s) body.step_up = s / 100;
  }
  if (i.kind === 'swp' || i.kind === 'stp') {
    const inst = Number(i.instalment);
    if (!(inst > 0)) return { error: `The monthly ${i.kind === 'swp' ? 'withdrawal' : 'transfer'} must be more than zero.` };
    body.instalment = inst;
  }
  if (i.kind === 'stp') {
    if (!i.target) return { error: 'Choose the fund to transfer into.' };
    if (i.target === i.code) return { error: 'The target fund must differ from the source fund.' };
    body.target = i.target;
  }
  // Equity gains never use the slab, so the server ignores it there; a debt class taken
  // from the category needs it, so it travels whenever the class is not chosen as equity.
  if (i.taxClass !== 'equity' && i.slab) {
    const slab = Number(i.slab);
    if (!(slab >= 0 && slab <= 50)) return { error: 'The slab rate is a percentage from 0 to 50.' };
    body.slab_rate = slab / 100;
  }
  return { body };
}

/** The lab URL for a saved request; `revision` pins the replay to the saved snapshot. */
export function scenarioHref(kind: CalculatorKind, r: CalculatorRequest, revision?: number): string {
  const p = new URLSearchParams({ kind, code: r.code, amount: String(r.amount), start: r.start });
  if (r.end) p.set('end', r.end);
  if (r.day != null) p.set('day', String(r.day));
  if (r.step_up) p.set('step_up', String(Math.round(r.step_up * 10_000) / 100));
  if (r.instalment != null) p.set('instalment', String(r.instalment));
  if (r.target) p.set('target', r.target);
  if (r.tax_class) p.set('tax', r.tax_class);
  if (r.slab_rate != null) p.set('slab', String(Math.round(r.slab_rate * 10_000) / 100));
  if (revision != null) p.set('rev', String(revision));
  return `/mf/simulate?${p}`;
}

const CODE = /^\d{1,9}$/;
const ISO = /^\d{4}-\d{2}-\d{2}$/;
const NUMBER = /^\d+(\.\d+)?$/;

/** Lab inputs from a URL; anything missing or malformed keeps its default. */
export function inputsFromSearch(p: URLSearchParams, fallback: Inputs): Inputs {
  const pick = (key: string, ok: RegExp) => (ok.test(p.get(key) ?? '') ? p.get(key)! : undefined);
  const kind = CALCULATOR_KINDS.find((k) => k === p.get('kind')) ?? fallback.kind;
  const tax = (['equity', 'debt', 'other'] as const).find((t) => t === p.get('tax'));
  const base = kind === fallback.kind ? fallback : { ...fallback, kind, ...KIND_DEFAULTS[kind] };
  return {
    ...base,
    code: pick('code', CODE) ?? base.code,
    target: pick('target', CODE) ?? base.target,
    amount: pick('amount', NUMBER) ?? base.amount,
    instalment: pick('instalment', NUMBER) ?? base.instalment,
    day: pick('day', NUMBER) ?? base.day,
    start: pick('start', ISO) ?? base.start,
    end: pick('end', ISO) ?? base.end,
    stepUp: pick('step_up', NUMBER) ?? base.stepUp,
    taxClass: tax ?? '',
    slab: pick('slab', NUMBER) ?? base.slab,
  };
}

/** The pinned revision in a lab URL, if any. */
export const revisionFromSearch = (p: URLSearchParams) => (/^\d+$/.test(p.get('rev') ?? '') ? Number(p.get('rev')) : undefined);
