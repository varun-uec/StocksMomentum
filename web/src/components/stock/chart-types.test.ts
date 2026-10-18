import { describe, expect, test } from 'vitest';
import { heikinAshi } from './chart-types';

describe('heikinAshi', () => {
  test('golden: two bars worked by hand', () => {
    const bars = [
      { time: 1, open: 10, high: 14, low: 9, close: 12 },
      { time: 2, open: 12, high: 13, low: 8, close: 9 },
    ];
    const [a, b] = heikinAshi(bars);
    expect(a).toEqual({ time: 1, open: 11, close: 11.25, high: 14, low: 9 }); // open (10+12)/2, close 45/4
    expect(b).toEqual({ time: 2, open: 11.125, close: 10.5, high: 13, low: 8 }); // open (11+11.25)/2, close 42/4
  });

  test('high and low always contain the body', () => {
    const ha = heikinAshi([
      { time: 1, open: 100, high: 101, low: 99, close: 100 },
      { time: 2, open: 50, high: 51, low: 49, close: 50 }, // a gap: the body sits above the raw high
    ]);
    expect(ha[1].high).toBeGreaterThanOrEqual(Math.max(ha[1].open, ha[1].close));
    expect(ha[1].low).toBeLessThanOrEqual(Math.min(ha[1].open, ha[1].close));
  });
});
