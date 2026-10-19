import { describe, expect, test } from 'vitest';
import { rebase } from './useCompare';

describe('rebase', () => {
  const main = [
    { date: '2026-08-03', close: 200 },
    { date: '2026-08-04', close: 210 },
    { date: '2026-08-05', close: 220 },
  ];

  test('the line starts on the main close at the first shared bar and keeps its own % moves', () => {
    const other = [
      { date: '2026-07-31', close: 40 }, // before the main series: skipped
      { date: '2026-08-04', close: 50 },
      { date: '2026-08-05', close: 55 },
    ];
    expect(rebase(main, other)).toEqual({
      from: '2026-08-04',
      points: [
        { date: '2026-08-04', price: 210 },
        { date: '2026-08-05', price: 231 }, // +10%, like 50 → 55
      ],
    });
  });

  test('no shared bar gives no line', () => {
    expect(rebase(main, [{ date: '2025-01-01', close: 10 }])).toBeNull();
    expect(rebase(main, [])).toBeNull();
  });
});

test('preset rebasing keeps earlier history available at the same stable comparison factor', () => {
  const main = [{ date: '2026-01-01', close: 100 }, { date: '2026-07-01', close: 200 }, { date: '2026-08-01', close: 220 }];
  const other = [{ date: '2026-01-01', close: 25 }, { date: '2026-07-01', close: 50 }, { date: '2026-08-01', close: 60 }];
  expect(rebase(main, other, '2026-07-01')).toEqual({ from: '2026-07-01', points: [{ date: '2026-01-01', price: 100 }, { date: '2026-07-01', price: 200 }, { date: '2026-08-01', price: 240 }] });
});
