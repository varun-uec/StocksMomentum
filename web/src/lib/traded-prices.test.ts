import { describe, expect, test } from 'vitest';
import type { ChartDrawing } from '@/components/stock/chart-drawings';
import { factorAt, periodBarFor, toChartPrices, toTradedPrices } from './traded-prices';

// GOLDIAM: a 1:5 split went ex on 2022-03-28 and a 1:3 bonus on 2026-07-10.
const GOLDIAM = [
  { until: '2022-03-25', factor: '0.15000000' },
  { until: '2026-07-09', factor: '0.75000000' },
  { until: '2026-08-07', factor: '1.00000000' },
];

const ray = (id: string, date: string, price: number): ChartDrawing => ({ id, kind: 'horizontal', color: '#6366f1', points: [{ date, price }] });

describe('factorAt', () => {
  test('each date takes the factor of its run, inclusive of the last day', () => {
    expect(factorAt(GOLDIAM, '2019-10-01')).toBe(0.15);
    expect(factorAt(GOLDIAM, '2022-03-25')).toBe(0.15);
    expect(factorAt(GOLDIAM, '2022-03-26')).toBe(0.75); // a weekend before the ex-date
    expect(factorAt(GOLDIAM, '2026-07-10')).toBe(1);
    expect(factorAt(GOLDIAM, '2027-01-01')).toBe(1); // a projection past the last bar
    expect(factorAt([], '2026-01-01')).toBe(1);
  });
});

describe('drawings across a split and a bonus', () => {
  const saved = [
    ray('pre-split', '2022-03-23', 801.75), // the raw close that day
    ray('pre-bonus', '2026-07-09', 420.5),
    ray('post-bonus', '2026-07-13', 374.55),
    { id: 'across', kind: 'trendline', color: '#6366f1', points: [{ date: '2022-03-23', price: 801.75 }, { date: '2026-07-13', price: 374.55 }] } as ChartDrawing,
  ];

  test('a drawing made on the raw chart lands on its adjusted bar', () => {
    const chart = toChartPrices(saved, GOLDIAM);
    expect(chart[0].points[0].price).toBeCloseTo(120.2625, 6); // the adjusted close of 2022-03-23
    expect(chart[1].points[0].price).toBeCloseTo(315.375, 6); // the adjusted close of 2026-07-09
    expect(chart[2].points[0].price).toBe(374.55);
    expect(chart[3].points.map((p) => p.price)).toEqual([chart[0].points[0].price, 374.55]);
  });

  test('untouched drawings go back as the same saved objects, so a merge sees no edit', () => {
    const back = toTradedPrices(toChartPrices(saved, GOLDIAM), saved, GOLDIAM);
    back.forEach((d, i) => expect(d).toBe(saved[i]));
  });

  test('a moved point is saved at the traded price of its date', () => {
    const chart = toChartPrices(saved, GOLDIAM);
    const moved = { ...chart[0], points: [{ date: '2021-06-01', price: 30 }] };
    const back = toTradedPrices([moved, ...chart.slice(1)], saved, GOLDIAM);
    expect(back[0].points[0].price).toBeCloseTo(200, 9); // 30 / 0.15
    expect(back[1]).toBe(saved[1]);
  });

  test('a later corporate action moves the bars and the drawing together', () => {
    // The same drawing after a future 1:1 bonus halves every earlier factor.
    const later = [...GOLDIAM.map((s) => ({ ...s, factor: String(parseFloat(s.factor) / 2) })), { until: '2027-03-01', factor: '1' }];
    expect(toChartPrices(saved, later)[2].points[0].price).toBeCloseTo(374.55 / 2, 6);
  });
});

describe('drawings on weekly bars', () => {
  // Weekly bars are dated at each week's last session; 2026-07-03 closes a
  // week whose Friday was a session, 2026-08-13 a week cut short on Thursday.
  const weeks = { interval: '1W' as const, dates: ['2026-07-03', '2026-07-10', '2026-08-13'] };

  test('a point moves to the bar of its ISO week', () => {
    expect(periodBarFor('2026-06-29', weeks)).toBe('2026-07-03'); // Monday
    expect(periodBarFor('2026-07-08', weeks)).toBe('2026-07-10'); // Wednesday
    expect(periodBarFor('2026-08-10', weeks)).toBe('2026-08-13');
    expect(periodBarFor('2026-07-20', weeks)).toBe('2026-07-20'); // a week with no bar keeps its date
    expect(periodBarFor('2026-09-01', weeks)).toBe('2026-09-01'); // after the last bar
  });

  test('an untouched drawing still goes back as the saved object; a moved one takes its bar date', () => {
    const saved = [ray('a', '2026-07-08', 420.5)];
    const chart = toChartPrices(saved, GOLDIAM, weeks);
    expect(chart[0].points[0]).toEqual({ date: '2026-07-10', price: 315.375 }); // snapped; priced at its own date's factor, 0.75
    expect(toTradedPrices(chart, saved, GOLDIAM, weeks)[0]).toBe(saved[0]);
    const moved = [{ ...chart[0], points: [{ date: '2026-07-03', price: 300 }] }];
    expect(toTradedPrices(moved, saved, GOLDIAM, weeks)[0].points[0]).toEqual({ date: '2026-07-03', price: 400 }); // 300 / 0.75
  });

  test('style-only edits retain original anchors across an intra-week corporate action', () => {
    const saved = [ray('a', '2026-07-08', 420.5)];
    const chart = toChartPrices(saved, GOLDIAM, weeks);
    const styled = { ...chart[0], hidden: true, locked: true, dash: 'dashed' as const, color: '#0ea5e9' };
    const result = toTradedPrices([styled], saved, GOLDIAM, weeks)[0];
    expect(result.points).toBe(saved[0].points);
    expect(result).toMatchObject({ hidden: true, locked: true, dash: 'dashed', color: '#0ea5e9' });
  });
});

describe('drawings on monthly bars', () => {
  // Monthly bars are dated at each month's last session; July 2026 is still running.
  const months = { interval: '1M' as const, dates: ['2026-05-29', '2026-06-30', '2026-07-10'] };

  test('a point moves to the bar of its calendar month', () => {
    expect(periodBarFor('2026-05-01', months)).toBe('2026-05-29');
    expect(periodBarFor('2026-06-01', months)).toBe('2026-06-30'); // a Monday that opens a month and a week
    expect(periodBarFor('2026-07-01', months)).toBe('2026-07-10'); // ISO week of 29 June, but July
    expect(periodBarFor('2026-04-15', months)).toBe('2026-04-15'); // a month with no bar keeps its date
    expect(periodBarFor('2026-08-03', months)).toBe('2026-08-03'); // after the last bar
  });

  test('a snapped point keeps the price of its own date', () => {
    const chart = toChartPrices([ray('a', '2026-07-09', 420.5)], GOLDIAM, months);
    expect(chart[0].points[0]).toEqual({ date: '2026-07-10', price: 315.375 });
  });
});
