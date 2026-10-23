import { describe, expect, it } from 'vitest';
import type { Backtest, Drawdown, FundRegimes } from './api';
import { backtestVerdict, fallVerdict, recentVerdict } from './verdicts';

const period = (first: string, last: string, s: number, m: number) => ({ months: 12, first_signal: first, last_signal: last, strategy_growth: 0, median_growth: 0, strategy_annualised: s, median_annualised: m, beat_share: 0.5 });

describe('backtestVerdict (audit F-18)', () => {
  it('says when the signal failed on the hold-out', () => {
    const result = { strategy: { top: 5 }, summary: { in_sample: period('2019-10', '2023-12', 0.2347, 0.187), holdout: period('2024-01', '2026-08', 0.0753, 0.0842), whole: null } } as unknown as Backtest;
    const text = backtestVerdict(result);
    expect(text).toContain('In-sample (Oct 2019 – Dec 2023), the top 5 grew 23.5% a year against 18.7%');
    expect(text).toContain('On the hold-out (Jan 2024 – Aug 2026), the top 5 grew 7.5% a year against 8.4%');
    expect(text).toContain('did not hold up');
  });

  it('never claims proof when both periods win', () => {
    const result = { strategy: { top: 3 }, summary: { in_sample: period('2019-10', '2023-12', 0.2, 0.1), holdout: period('2024-01', '2026-08', 0.1, 0.05), whole: null } } as unknown as Backtest;
    expect(backtestVerdict(result)).toContain('One hold-out period is not proof.');
  });
});

describe('fallVerdict (audit U-02)', () => {
  const windows = [
    { start: '2020-02-12', end: '2020-03-23', kind: 'crash', proxy_return: -0.3553, fund_return: -0.3093, state: null, difference: null, capture: null },
    { start: '2022-10-18', end: '2022-06-17', kind: 'correction', proxy_return: -0.1795, fund_return: -0.12, state: null, difference: null, capture: null },
    { start: '2020-03-23', end: '2020-11-09', kind: 'recovery', proxy_return: 0.56, fund_return: 0.5, state: null, difference: null, capture: null },
  ] as FundRegimes['windows'];
  const drawdowns: Drawdown[] = [{ depth: -0.31, peak: '2020-01-20', trough: '2020-03-23', recovery: '2020-07-06', fall_days: 63, recovery_days: 105 }];

  it('reads the deepest proxy fall with the API numbers', () => {
    const v = fallVerdict(windows, drawdowns)!;
    expect(v.fund).toBe(-0.3093);
    expect(v.proxy).toBe(-0.3553);
    expect(v.recoveryDays).toBe(105);
    expect(v.text).toBe("In the deepest market fall it lived through (12 Feb 2020 to 23 Mar 2020), it lost 30.9%, less than the market proxy's 35.5% fall, and regained its previous peak 105 days after its low.");
  });

  it('never implies a recovery that has not happened', () => {
    const v = fallVerdict(windows, [{ ...drawdowns[0], recovery: null, recovery_days: null }])!;
    expect(v.text).toContain('has not yet regained');
  });

  it('is empty without a fall window the fund lived through', () => {
    expect(fallVerdict([{ ...windows[0], fund_return: null }], [])).toBeNull();
  });
});

describe('recentVerdict puts the last year beside the history (audit 5.3)', () => {
  it('states a weak year against the category', () => {
    expect(recentVerdict({ ret_1y: -0.057, ret_1y_cat_median: 0.012, ret_1y_cat_pct: 44, dd_now: -0.066 })).toBe(
      'Over the last year it returned −5.7%, behind the category median of +1.2% (44th percentile). It is 6.6% below its last peak.',
    );
  });
  it('handles a fund at its peak, missing figures and ordinals', () => {
    expect(recentVerdict({ ret_1y: 0.1, dd_now: 0, ret_1y_cat_median: 0.05, ret_1y_cat_pct: 92 })).toContain('(92nd percentile). It is at its peak NAV.');
    expect(recentVerdict({ ret_1y: 0.1, ret_1y_cat_median: 0.05, ret_1y_cat_pct: 11 })).toContain('11th');
    expect(recentVerdict({ ret_1y: null })).toBeNull();
  });
});
