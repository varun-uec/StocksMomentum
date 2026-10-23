import { describe, expect, it } from 'vitest';
import type { NavRow, Point } from './api';
import { availableWindows, navPoints, rebase, sinceYears } from './series';

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
