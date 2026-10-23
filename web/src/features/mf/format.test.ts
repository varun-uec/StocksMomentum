import { describe, expect, it } from 'vitest';
import type { FieldDef } from './api';
import { categoryShort, date, formatField, formatValue, inr, missingLabel, pct, schemeName, unitOf } from './format';

describe('MF formatting', () => {
  it('shows fractions as percentages with a true minus sign', () => {
    expect(pct(0.12178)).toBe('12.2%');
    expect(pct(-0.0569, 1)).toBe('−5.7%');
    expect(pct(0.0569, 1, true)).toBe('+5.7%');
    expect(pct(-0.00001)).toBe('0.0%');
    expect(pct(null)).toBe('—');
    expect(pct(Number.NaN)).toBe('—');
  });

  it('groups rupees the Indian way and abbreviates lakh and crore', () => {
    expect(inr(798277.99)).toBe('₹7,98,278');
    expect(inr(798277.99, true)).toBe('₹7.98 L');
    expect(inr(20478358, true)).toBe('₹2.05 Cr');
    expect(inr(-1500)).toBe('−₹1,500');
  });

  it('formats dates as DD MMM YYYY', () => {
    expect(date('2026-10-22')).toBe('22 Oct 2026');
    expect(date(null)).toBe('—');
  });

  it('formats each registry unit', () => {
    expect(formatValue(97.7777, 'percentile')).toBe('97.8');
    expect(formatValue(0.5968, 'ratio')).toBe('0.60');
    expect(formatValue(2, 'quartile')).toBe('Q2');
    expect(formatValue(-1, 'quartile', 'number', true)).toBe('−1');
    expect(formatValue(12.5, 'percentile', 'number', true)).toBe('+12.5');
    expect(formatValue(3, 'rank')).toBe('#3');
    expect(formatValue(360, 'days')).toBe('360 d');
    expect(formatValue(-0.0098, 'fraction')).toBe('−0.98%');
    expect(formatValue('direct', null, 'enum')).toBe('Direct');
    expect(formatValue('2026-10-22', null, 'date')).toBe('22 Oct 2026');
    expect(formatValue(true, null, 'boolean')).toBe('Yes');
  });

  it('signs change fields by id', () => {
    const field = { id: 'quartile_change_1y', unit: 'quartile', type: 'number' } as FieldDef;
    expect(formatField(field, 1)).toBe('+1');
  });

  it('gives a category median its base field unit', () => {
    const base = { id: 'cagr_3y', unit: 'fraction' } as FieldDef;
    const median = { id: 'cagr_3y_cat_median', unit: null } as FieldDef;
    expect(unitOf(median, new Map([['cagr_3y', base]]))).toBe('fraction');
  });

  it('names missing reasons and shortens names', () => {
    expect(missingLabel({ state: 'NA', reason: 'not_recovered' })).toBe('Not recovered');
    expect(missingLabel({ state: 'NA', reason: 'new_reason' })).toBe('new reason');
    expect(categoryShort('Equity Scheme - Flexi Cap Fund')).toBe('Flexi Cap');
    expect(categoryShort('Unclassified')).toBe('Unclassified');
    expect(schemeName('Parag Parikh Flexi Cap Fund - Direct Plan - Growth')).toBe('Parag Parikh Flexi Cap Fund');
  });
});
