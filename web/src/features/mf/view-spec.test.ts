import { describe, expect, it } from 'vitest';
import type { FieldDef, FilterNode } from './api';
import { UNIVERSE, decodeView, defaultView, describe as describeCondition, encodeView, filterOf, formulaNameError, fromApi, mixesCategories, toApi } from './view-spec';
import { toggleCode } from './workspace';

const fields = new Map<string, FieldDef>([
  ['cagr_3y', { id: 'cagr_3y', label: 'CAGR 3Y', unit: 'fraction', type: 'number' } as FieldDef],
  ['score', { id: 'score', label: 'Score', unit: 'percentile', type: 'number' } as FieldDef],
  ['category', { id: 'category', label: 'Category', unit: null, type: 'enum' } as FieldDef],
]);

describe('screen view links', () => {
  it('round-trips through the URL, including non-ASCII text', () => {
    const view = { ...defaultView([{ field: 'cagr_3y', op: '>=', value: 0.15 }]), formulas: { edge: 'cagr_3y - cagr_3y_cat_median' } };
    view.columns = ['category', 'cagr_3y', 'edge'];
    const decoded = decodeView(encodeView({ ...view, formulas: { ...view.formulas, note_x: '1' } }));
    expect(decoded?.conditions).toEqual(view.conditions);
    expect(decoded?.formulas.edge).toBe('cagr_3y - cagr_3y_cat_median');
    expect(decodeView(encodeView({ ...view, columns: ['निधि'] }))?.columns).toEqual(['निधि']);
  });

  it('rejects malformed, foreign-version and oversized links', () => {
    expect(decodeView('not-base64!')).toBeNull();
    expect(decodeView(btoa(JSON.stringify({ v: 99, mode: 'all', conditions: [], sort: [], columns: [], formulas: {} })))).toBeNull();
    expect(decodeView('a'.repeat(7000))).toBeNull();
    expect(decodeView('')).toBeNull();
  });
});

describe('percent fields', () => {
  it('serialise typed percentages as fractions and back without float noise', () => {
    expect(toApi(fields.get('cagr_3y'), 15)).toBe(0.15);
    expect(toApi(fields.get('cagr_3y'), 12.3)).toBe(0.123);
    expect(fromApi(fields.get('cagr_3y'), 0.123)).toBe(12.3);
    expect(toApi(fields.get('score'), 75)).toBe(75);
  });

  it('describe conditions in display units', () => {
    expect(describeCondition({ field: 'cagr_3y', op: '>=', value: 0.1 }, fields)).toBe('CAGR 3Y ≥ 10%');
    expect(describeCondition({ field: 'score', op: 'between', value: [60, null] }, fields)).toBe('Score ≥ 60');
    expect(describeCondition({ field: 'category', op: 'in', value: ['A', 'B', 'C'] }, fields)).toBe('Category is A, B +1');
    expect(describeCondition({ field: 'cagr_3y', op: 'top_pct', value: 25 }, fields)).toBe('CAGR 3Y in top 25%');
  });
});

describe('formula names', () => {
  it('follow the backend rule and avoid collisions', () => {
    expect(formulaNameError('edge_3y', fields, [])).toBeNull();
    expect(formulaNameError('Edge', fields, [])).not.toBeNull();
    expect(formulaNameError('cagr_3y', fields, [])).toMatch(/registry/);
    expect(formulaNameError('edge', fields, ['edge'])).toMatch(/in use/);
  });
});

describe('watchlist set edits', () => {
  it('add once, keep order, remove cleanly', () => {
    expect(toggleCode(['a', 'b'], 'c', true)).toEqual(['a', 'b', 'c']);
    expect(toggleCode(['a', 'b'], 'a', true)).toEqual(['a', 'b']);
    expect(toggleCode(['a', 'b'], 'a', false)).toEqual(['b']);
    expect(toggleCode([], 'x', false)).toEqual([]);
  });
});

describe('Match any keeps the universe (audit F-05)', () => {
  it('ANDs the gates and ORs the other conditions', () => {
    const view = { ...defaultView([{ field: 'cagr_3y', op: '>=', value: 0.15 }]), mode: 'any' as const };
    const filter = filterOf(view);
    expect(filter).toEqual({ all: [...UNIVERSE, { any: [view.conditions[3], view.conditions[4]] }] });
  });

  it('keeps Match all unchanged and handles a view with only gates', () => {
    const view = defaultView();
    expect(filterOf(view)).toEqual({ all: view.conditions });
    expect(filterOf({ ...view, mode: 'any', conditions: UNIVERSE })).toEqual({ all: UNIVERSE });
  });
});

describe('Match any never nests deeper than the API allows (audit A-08)', () => {
  type Fund = Record<string, number | string>;
  // A tiny evaluator mirroring the API's operators used here, to check meaning is kept.
  const test = (n: FilterNode, f: Fund): boolean =>
    'all' in n ? n.all.every((c) => test(c, f)) : 'any' in n ? n.any.some((c) => test(c, f)) : n.op === 'in' ? (n.value as unknown[]).includes(f[n.field]) : n.op === '>' ? Number(f[n.field]) > Number(n.value) : Number(f[n.field]) < Number(n.value);
  const depth = (n: FilterNode): number => ('field' in n ? 0 : 1 + Math.max(...('all' in n ? n.all : n.any).map(depth)));
  const fast: FilterNode = { field: 'cagr_3y', op: '>', value: 0.15 };
  const calm: FilterNode = { field: 'vol_3y', op: '<', value: 0.12 };
  const cheap: FilterNode = { field: 'ter', op: '<', value: 0.01 };
  const funds: Fund[] = [0, 1].flatMap((a) => [0.1, 0.2].flatMap((c) => [0.1, 0.2].flatMap((v) => [0.005, 0.02].map((t) => ({ status: a ? 'active' : 'historical', plan: 'direct', option: 'growth', cagr_3y: c, vol_3y: v, ter: t })))));
  const meaning = (n: FilterNode) => funds.map((f) => test(n, f));

  it.each<[string, FilterNode[]]>([
    ['a saved ANY group', [{ any: [fast, calm] }]],
    ['a saved ALL group beside a condition', [{ all: [fast, calm] }, cheap]],
    ['both kinds of group', [{ any: [fast, cheap] }, { all: [fast, calm] }]],
  ])('%s', (_, extra) => {
    const view = { ...defaultView(), conditions: [...UNIVERSE, ...extra], mode: 'any' as const };
    const filter = filterOf(view) as FilterNode;
    expect(depth(filter)).toBeLessThanOrEqual(2);
    expect(meaning(filter)).toEqual(meaning({ all: [...UNIVERSE, { any: extra }] }));
  });
});

describe('default screen is category-aware (audit F-06)', () => {
  it('opens on one category sorted by score', () => {
    const view = defaultView();
    expect(view.sort[0].field).toBe('score');
    expect(mixesCategories(view)).toBe(false);
  });

  it('flags a score sort across categories', () => {
    const view = defaultView();
    expect(mixesCategories({ ...view, conditions: UNIVERSE })).toBe(true);
    expect(mixesCategories({ ...view, conditions: UNIVERSE, sort: [{ field: 'cagr_3y', dir: 'desc' }] })).toBe(false);
  });
});
