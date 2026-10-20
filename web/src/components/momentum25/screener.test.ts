import { describe, expect, it } from 'vitest';
import { applyFilters, categoryValues, COLUMN_SETS, rangeValue, screenFilters } from '@/components/momentum25/screener';
import type { RankingItemDTO } from '@/lib/types';

const row = (symbol: string, rank: number, checklist: boolean[], extra: Record<string, unknown> = {}, fields: Partial<RankingItemDTO> = {}): RankingItemDTO => ({
  rank,
  symbol,
  name: symbol,
  momentum_score: '50',
  buy_setup_score: '50',
  sector: null,
  rs_rating: 80,
  explanation: { checklist: Object.fromEntries(checklist.map((v, i) => [`r${i}`, v])), ...extra },
  ...fields,
});

const rows = [
  row('AAA', 1, [true, true], { risk_rating: 'Low', volume_quality: 'High', breakout_quality: 'Strong', rank_change: -2 }, { momentum_score: '91.5000', sector: 'IT', rs_rating: 95 }),
  row('BBB', 2, [true, true], { risk_rating: 'High', volume_quality: 'Medium', rank_change: 3 }, { momentum_score: '72.2500', sector: 'Banks', rs_rating: 70 }),
  row('CCC', 0, [true, false], { risk_rating: 'Low' }, { momentum_score: '40.0000', sector: 'IT', rs_rating: null }),
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

  it('bound numeric fields inclusively; a missing value never matches a bound', () => {
    const pick = (ranges: Parameters<typeof applyFilters>[1]['ranges']) => applyFilters(rows, { ranges }).map((r) => r.symbol);
    expect(pick({ momentum_score: { min: 72.25 } })).toEqual(['AAA', 'BBB']);
    expect(pick({ momentum_score: { max: 72.25 } })).toEqual(['BBB', 'CCC', 'DDD']);
    expect(pick({ rs_rating: { min: 70, max: 94 } })).toEqual(['BBB', 'DDD']);
    expect(pick({ rs_rating: { min: 0 } })).toEqual(['AAA', 'BBB', 'DDD']);
    expect(pick({ rank: { max: 1 } })).toEqual(['AAA']);
    expect(pick({ rank: { min: 0 } })).toEqual(['AAA', 'BBB']);
    expect(pick({ rank_change: { max: 0 } })).toEqual(['AAA']);
    expect(pick({ rs_rating: { min: null, max: null } })).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    expect(rangeValue(rows[2], 'rank')).toBeNull();
  });

  it('filter by sector and combine with every other filter', () => {
    expect(categoryValues(rows, 'sector')).toEqual(['Banks', 'IT']);
    expect(applyFilters(rows, { sector: 'IT' }).map((r) => r.symbol)).toEqual(['AAA', 'CCC']);
    expect(applyFilters(rows, { sector: 'IT', qualified: true, ranges: { rs_rating: { min: 90 } } }).map((r) => r.symbol)).toEqual(['AAA']);
    expect(applyFilters(rows, { sector: null, qualified: null }).map((r) => r.symbol)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
  });

  it('store filters with every field written out and open ranges dropped', () => {
    expect(screenFilters({ qualified: true, ranges: { rs_rating: { min: 80 }, rank: { min: null, max: null } } })).toEqual({
      qualified: true,
      trend: null,
      risk: null,
      volume: null,
      breakout: null,
      sector: null,
      ranges: { rs_rating: { min: 80, max: null } },
    });
  });
});
