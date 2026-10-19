import { describe, expect, test } from 'vitest';
import { rangeStartIndex, withinPriceSpan } from './useChartShell';

describe('withinPriceSpan', () => {
  const panes = ['2025-08-01', '2026-02-02', '2026-04-20', '2026-08-07'].map((date) => ({ date }));

  test('drops indicator bars before the first price bar, so the time axis stays on the price range', () => {
    expect(withinPriceSpan(panes, '2026-04-20').map((b) => b.date)).toEqual(['2026-04-20', '2026-08-07']);
  });

  test('keeps everything until the price bars load', () => {
    expect(withinPriceSpan(panes, undefined)).toBe(panes);
  });
});

describe('rangeStartIndex', () => {
  // Stored data that ends weeks before today, as after a missed import.
  const dates = ['2026-06-01', '2026-07-06', '2026-07-31', '2026-08-03', '2026-08-07'];

  test('counts the range back from the last bar, not from today', () => {
    expect(dates.slice(rangeStartIndex(dates, '1W'))).toEqual(['2026-07-31', '2026-08-03', '2026-08-07']);
    expect(dates.slice(rangeStartIndex(dates, '1M'))).toEqual(['2026-07-31', '2026-08-03', '2026-08-07']);
    expect(dates.slice(rangeStartIndex(dates, '3M'))).toEqual(dates);
  });

  test('MAX and an empty series start at the first bar', () => {
    expect(rangeStartIndex(dates, 'MAX')).toBe(0);
    expect(rangeStartIndex([], '1Y')).toBe(0);
  });
});
