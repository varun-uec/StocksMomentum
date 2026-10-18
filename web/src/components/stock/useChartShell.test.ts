import { describe, expect, test } from 'vitest';
import { withinPriceSpan } from './useChartShell';

describe('withinPriceSpan', () => {
  const panes = ['2025-08-01', '2026-02-02', '2026-04-20', '2026-08-07'].map((date) => ({ date }));

  test('drops indicator bars before the first price bar, so the time axis stays on the price range', () => {
    expect(withinPriceSpan(panes, '2026-04-20').map((b) => b.date)).toEqual(['2026-04-20', '2026-08-07']);
  });

  test('keeps everything until the price bars load', () => {
    expect(withinPriceSpan(panes, undefined)).toBe(panes);
  });
});
