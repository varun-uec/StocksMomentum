import { describe, expect, it } from 'vitest';
import { returnLabel, safeReturnPath } from '@/lib/return-path';

describe('safeReturnPath', () => {
  it('accepts same-origin paths with their query', () => {
    expect(safeReturnPath('/chart/TCS')).toBe('/chart/TCS');
    expect(safeReturnPath('/backtest?strategy=x')).toBe('/backtest?strategy=x');
  });

  it('rejects anything that could leave the origin', () => {
    for (const raw of [null, '', 'chart/TCS', '//evil.example/x', '/\\evil.example', 'https://evil.example', 'javascript:alert(1)', '/\nx', ' //evil.example']) {
      expect(safeReturnPath(raw)).toBeNull();
    }
  });
});

describe('returnLabel', () => {
  it('names the chart symbol', () => {
    expect(returnLabel('/chart/TCS')).toBe('Back to chart · TCS');
    expect(returnLabel('/chart')).toBe('Back to chart');
    expect(returnLabel('/backtest')).toBe('Back');
  });
});
