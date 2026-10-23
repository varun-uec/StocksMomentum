import { describe, expect, it } from 'vitest';
import type { CalculatorKind } from './api';
import { defaultInputs, inputsFromSearch, revisionFromSearch, scenarioHref, toRequest, type Inputs } from './scenario';

const NOW = '2026-10-22';
const blank = defaultInputs('sip', '1', '', NOW);
const reopen = (kind: CalculatorKind, i: Inputs, rev?: number) => {
  const req = toRequest(i, NOW).body!;
  const url = new URL(scenarioHref(kind, req, rev), 'http://x');
  return { req, back: toRequest(inputsFromSearch(url.searchParams, blank), NOW).body, rev: revisionFromSearch(url.searchParams) };
};

describe('saved scenarios round-trip every request field (audit A-05)', () => {
  it.each<[CalculatorKind, Partial<Inputs>]>([
    ['sip', { amount: '25000', day: '15', start: '2019-04-15', end: '2025-10-15', stepUp: '10', taxClass: 'equity' }],
    ['lumpsum', { amount: '1000000', start: '2023-07-24', end: '2024-07-24' }],
    ['swp', { amount: '1500000', instalment: '7500', day: '7', start: '2020-01-01', end: '2025-01-01', taxClass: 'debt', slab: '20' }],
    ['stp', { amount: '600000', instalment: '12500', day: '3', target: '118987', start: '2021-02-01', end: '2024-02-01', taxClass: 'other', slab: '5' }],
  ])('%s', (kind, patch) => {
    const { req, back, rev } = reopen(kind, { ...defaultInputs(kind, '122639', '', NOW), ...patch }, 2801);
    expect(back).toEqual(req);
    expect(rev).toBe(2801);
  });

  it('the old fund-only link keeps defaults and leaves the tax class to the category', () => {
    const i = inputsFromSearch(new URLSearchParams('kind=sip&code=118987'), blank);
    expect(i).toMatchObject({ code: '118987', amount: '10000', day: '1', taxClass: '' });
    expect(toRequest(i, NOW).body).not.toHaveProperty('tax_class');
  });

  it('ignores malformed values', () => {
    const i = inputsFromSearch(new URLSearchParams('kind=nope&code=abc&amount=-5&start=yesterday&tax=gold&rev=x'), blank);
    expect(i).toEqual(blank);
    expect(revisionFromSearch(new URLSearchParams('rev=x'))).toBeUndefined();
  });
});

describe('tax class is never assumed (audit A-04)', () => {
  it('sends no class by default, but sends the slab so a category-derived debt class can use it', () => {
    const body = toRequest(defaultInputs('sip', '118987', '', NOW), NOW).body!;
    expect(body.tax_class).toBeUndefined();
    expect(body.slab_rate).toBe(0.3);
  });
  it('a chosen equity class carries no slab', () => {
    expect(toRequest({ ...blank, taxClass: 'equity' }, NOW).body).not.toHaveProperty('slab_rate');
  });
});
