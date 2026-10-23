import { describe, expect, it } from 'vitest';
import { logTicks, niceTicks, pctTick, timeLabel, timeTicks, toTime } from './axis';

describe('niceTicks (audit F-02)', () => {
  it('gives round steps that cover the data', () => {
    // The risk-return map of the audit: volatility 9.92% to 17.70%.
    const ticks = niceTicks(0.0992, 0.177);
    expect(ticks).toEqual([0.08, 0.1, 0.12, 0.14, 0.16, 0.18]);
    expect(ticks[0]).toBeLessThanOrEqual(0.0992);
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(0.177);
  });

  it('labels every gridline with its true value', () => {
    for (const [lo, hi] of [[-0.19, 0.98], [0.02, 0.37], [-0.355, 0], [8000, 41000], [101, 292]] as const) {
      const ticks = niceTicks(lo, hi);
      const step = ticks[1] - ticks[0];
      ticks.forEach((t, i) => expect(t).toBeCloseTo(ticks[0] + i * step, 9));
      expect([1, 2, 5]).toContain(Number((step / 10 ** Math.floor(Math.log10(step))).toFixed(6)));
    }
  });

  it('maps a known point to the labelled grid', () => {
    // Parag Parikh Flexi Cap: vol 9.92%, CAGR 12.18%. The point sits between the 8% and 10% lines, near 10%.
    const ticks = niceTicks(0.0992, 0.177);
    const below = ticks.filter((t) => t <= 0.0992).at(-1)!;
    expect(pctTick(below)).toBe('8%');
    expect(Math.abs(0.1 - 0.0992) * 100).toBeLessThan(1);
  });

  it('widens a flat series', () => {
    expect(niceTicks(5, 5).length).toBeGreaterThan(1);
  });
});

describe('pctTick', () => {
  it('shows the decimals the value needs', () => {
    expect(pctTick(0.025)).toBe('2.5%');
    expect(pctTick(0.1)).toBe('10%');
    expect(pctTick(-0.2)).toBe('−20%');
    expect(pctTick(0)).toBe('0%');
    expect(pctTick(0.0005)).toBe('0.05%');
  });
});

describe('timeTicks (audit F-15)', () => {
  it('puts yearly ticks on 1 January and never before the series start', () => {
    const { ticks, years } = timeTicks(toTime('2016-10-17'), toTime('2026-10-22'));
    expect(years).toBe(true);
    expect(ticks.every((t) => new Date(t).getUTCMonth() === 0 && new Date(t).getUTCDate() === 1)).toBe(true);
    expect(ticks[0]).toBeGreaterThanOrEqual(toTime('2016-10-17'));
    expect(timeLabel(ticks[0], years)).toBe('2018');
  });

  it('puts short-range ticks on month starts', () => {
    const { ticks, years } = timeTicks(toTime('2026-04-22'), toTime('2026-10-22'));
    expect(years).toBe(false);
    expect(ticks.map((t) => timeLabel(t, false))).toEqual(['May 26', 'Jul 26', 'Sep 26']);
  });

  it('spaces regular steps', () => {
    const { ticks } = timeTicks(toTime('2019-01-01'), toTime('2026-10-22'));
    const gaps = new Set(ticks.slice(1).map((t, i) => new Date(t).getUTCFullYear() - new Date(ticks[i]).getUTCFullYear()));
    expect(gaps.size).toBe(1);
  });
});

describe('logTicks', () => {
  it('marks 1, 2 and 5 steps inside the range', () => {
    expect(logTicks(9000, 48000)).toEqual([10000, 20000]);
    expect(logTicks(900, 60000)).toEqual([1000, 2000, 5000, 10000, 20000, 50000]);
    expect(logTicks(0, 10)).toEqual([]);
  });
});
