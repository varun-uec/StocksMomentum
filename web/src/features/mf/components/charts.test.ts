import { describe, expect, it } from 'vitest';
import type { Point } from '../api';
import { thin } from './charts';

// A daily underwater series with a sharp V on a date uniform sampling skips (audit A-02).
const day = (i: number) => new Date(Date.UTC(2015, 0, 1) + i * 86_400_000).toISOString().slice(0, 10);
const series: Point[] = Array.from({ length: 2600 }, (_, i) => [day(i), -0.05 - 0.02 * Math.sin(i / 40)]);
series[1907] = [series[1907][0], -0.312021];
series[1906] = [series[1906][0], -0.27];

describe('thin keeps the extremes', () => {
  it('keeps the true trough on its own date at every size', () => {
    for (const max of [80, 120, 150, 700]) {
      const out = thin(series, max);
      expect(out.length).toBeLessThanOrEqual(max * 1.1);
      expect(Math.min(...out.map(([, v]) => v))).toBe(-0.312021);
      expect(out.find(([, v]) => v === -0.312021)?.[0]).toBe(series[1907][0]);
      expect(out[0]).toBe(series[0]);
      expect(out.at(-1)).toBe(series.at(-1));
    }
  });

  it('keeps each series extreme in merged rows, even when a series is missing on some dates', () => {
    const rows = series.map(([d, v], i) => (i % 2 ? { date: d, b: -v } : { date: d, a: v, b: -v }));
    rows[1001] = { date: rows[1001].date, b: 0.9 };
    const out = thin(rows, 200);
    expect(out).toContain(rows[1001]);
    const lowestA = (rs: typeof rows) => Math.min(...rs.map((r) => ('a' in r ? (r.a as number) : Infinity)));
    expect(lowestA(out)).toBe(lowestA(rows));
  });

  it('returns short inputs unchanged', () => {
    expect(thin(series.slice(0, 50), 100)).toHaveLength(50);
  });
});
