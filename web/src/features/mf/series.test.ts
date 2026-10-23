import { describe, expect, it } from 'vitest';
import type { NavRow, Point } from './api';
import { availableWindows, compound, growthByMonth, monthEnd, navPoints, rebase, sinceYears } from './series';

const points: Point[] = [
  ['2016-10-17', 10],
  ['2023-10-23', 20],
  ['2025-10-20', 25],
  ['2026-10-22', 30],
];

describe('chart series', () => {
  it('cuts a window at the same calendar date', () => {
    expect(sinceYears(points, 1).map(([d]) => d)).toEqual(['2026-10-22']);
    expect(sinceYears(points, 3).map(([d]) => d)).toEqual(['2023-10-23', '2025-10-20', '2026-10-22']);
    expect(sinceYears(points, 99)).toHaveLength(4);
  });

  it('rebases to a starting amount from a start date', () => {
    expect(rebase(points, 10000, '2023-01-01')).toEqual([
      ['2023-10-23', 10000],
      ['2025-10-20', 12500],
      ['2026-10-22', 15000],
    ]);
    expect(rebase([], 100)).toEqual([]);
  });

  it('drops anomalous and non-positive NAVs instead of bridging them', () => {
    const rows = [
      { date: '2026-10-20', nav: '10.5', anomaly: null },
      { date: '2026-10-21', nav: '105', anomaly: 'jump' },
      { date: '2026-10-22', nav: '0', anomaly: null },
    ] as NavRow[];
    expect(navPoints(rows)).toEqual([['2026-10-20', 10.5]]);
  });

  it('offers only the windows the history covers', () => {
    expect(availableWindows(points)).toEqual(['1Y', '3Y', '5Y', '10Y', 'Max']);
    expect(availableWindows(points.slice(1))).toEqual(['1Y', '3Y', 'Max']);
    expect(availableWindows([['2026-01-01', 1]])).toEqual(['Max']);
  });
});

describe('compound', () => {
  it('turns monthly returns into a growth line whose end matches the total growth', () => {
    const line = compound([['2024-01-28', 0.1], ['2024-02-28', -0.05], ['2024-03-28', 0.02]]);
    expect(line.map(([, v]) => Number(v.toFixed(4)))).toEqual([110, 104.5, 106.59]);
    expect(line[2][1] / 100 - 1).toBeCloseTo(1.1 * 0.95 * 1.02 - 1, 12);
  });
});

describe('backtest growth sits on realised dates (audit A-14)', () => {
  it('starts at 100 on the signal month end and books each return at the next month end', () => {
    const g = growthByMonth([{ signal_month: '2019-10' }, { signal_month: '2019-11' }, { signal_month: '2020-01' }], [0.00591268, 0.01, -0.02]);
    expect(g[0]).toEqual(['2019-10-31', 100]);
    expect(g[1][0]).toBe('2019-11-30');
    expect(g[1][1]).toBeCloseTo(100.591268, 6);
    expect(g[2][0]).toBe('2019-12-31');
    expect(g[3][0]).toBe('2020-02-29');
  });
  it('handles December and an empty run', () => {
    expect(monthEnd('2019-12', 1)).toBe('2020-01-31');
    expect(growthByMonth([], [])).toEqual([]);
  });
});
