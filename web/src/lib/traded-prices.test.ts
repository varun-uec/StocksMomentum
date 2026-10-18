import { describe, expect, test } from 'vitest';
import type { ChartDrawing } from '@/components/stock/chart-drawings';
import { factorAt, toChartPrices, toTradedPrices } from './traded-prices';

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
