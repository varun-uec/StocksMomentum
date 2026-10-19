import { describe, expect, it } from 'vitest';
import { applyFilters, categoryValues, COLUMN_SETS } from '@/components/momentum25/screener';
import type { RankingItemDTO } from '@/lib/types';

const row = (symbol: string, rank: number, checklist: boolean[], extra: Record<string, string> = {}): RankingItemDTO => ({
  rank,
  symbol,
  name: symbol,
  momentum_score: '50',
  buy_setup_score: '50',
  sector: null,
  rs_rating: 80,
  explanation: { checklist: Object.fromEntries(checklist.map((v, i) => [`r${i}`, v])), ...extra },
});

const rows = [
  row('AAA', 1, [true, true], { risk_rating: 'Low', volume_quality: 'High', breakout_quality: 'Strong' }),
  row('BBB', 2, [true, true], { risk_rating: 'High', volume_quality: 'Medium' }),
  row('CCC', 0, [true, false], { risk_rating: 'Low' }),
  row('DDD', 0, [false, false]),
];

describe('screener filters', () => {
  it('keep the run order and match every set filter', () => {
    expect(applyFilters(rows, {}).map((r) => r.symbol)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    expect(applyFilters(rows, { qualified: true }).map((r) => r.symbol)).toEqual(['AAA', 'BBB']);
    expect(applyFilters(rows, { qualified: false }).map((r) => r.symbol)).toEqual(['CCC', 'DDD']);
    expect(applyFilters(rows, { trend: false }).map((r) => r.symbol)).toEqual(['CCC', 'DDD']);
    expect(applyFilters(rows, { risk: 'Low' }).map((r) => r.symbol)).toEqual(['AAA', 'CCC']);
    expect(applyFilters(rows, { risk: 'Low', qualified: false }).map((r) => r.symbol)).toEqual(['CCC']);
    expect(applyFilters(rows, { breakout: 'Strong', volume: 'High' }).map((r) => r.symbol)).toEqual(['AAA']);
  });

  it('are deterministic and do not change their input', () => {
    const before = JSON.stringify(rows);
    const once = applyFilters(rows, { trend: true, risk: 'Low' });
    expect(applyFilters(rows, { trend: true, risk: 'Low' })).toEqual(once);
    expect(JSON.stringify(rows)).toBe(before);
  });

  it('offer only the category values present, sorted', () => {
    expect(categoryValues(rows, 'risk')).toEqual(['High', 'Low']);
    expect(categoryValues(rows, 'breakout')).toEqual(['Strong']);
  });

  it('keep rank and symbol in every column set', () => {
    for (const columns of Object.values(COLUMN_SETS)) expect(columns.slice(0, 2)).toEqual(['rank', 'symbol']);
  });
});
