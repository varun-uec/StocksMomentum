import { describe, expect, it } from 'vitest';
import type { ScreenRow } from './api';
import { csvCell, screenCsv } from './csv';

describe('screen CSV', () => {
  it('quotes commas, quotes and formula-like text', () => {
    expect(csvCell('a,b')).toBe('"a,b"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell('=HYPERLINK()')).toBe('"=HYPERLINK()"');
    expect(csvCell(null)).toBe('');
    expect(csvCell(0.12178020836095005)).toBe('0.12178020836095005');
  });

  it('keeps full precision and names each missing reason', () => {
    const rows: ScreenRow[] = [
      { plan_option_id: 1, amfi_code: '122639', name: 'Fund, Direct', values: { cagr_3y: 0.1217802 }, states: {}, conditions: [] },
      { plan_option_id: 2, amfi_code: '100', name: 'New', values: { cagr_3y: null }, states: { cagr_3y: { state: 'NA', reason: 'history_too_short' } }, conditions: [] },
    ];
    const text = screenCsv(['cagr_3y'], rows, {
      as_of: '2026-10-22', data_revision: 2801, latest_revision: 2801, method_version: 5, sources: ['amfi'], filter: { all: [] }, sort: [], formulas: {},
    });
    const lines = text.trim().split('\n');
    expect(lines[0]).toContain('snapshot 2801');
    expect(lines[3]).toBe('amfi_code,name,cagr_3y,cagr_3y_missing');
    expect(lines[4]).toBe('122639,"Fund, Direct",0.1217802,');
    expect(lines[5]).toBe('100,New,,NA:history_too_short');
  });
});
