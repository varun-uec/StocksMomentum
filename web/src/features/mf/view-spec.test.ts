import { describe, expect, it } from 'vitest';
import type { FieldDef } from './api';
import { decodeView, defaultView, describe as describeCondition, encodeView, formulaNameError, fromApi, toApi } from './view-spec';
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
