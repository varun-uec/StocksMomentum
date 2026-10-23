/**
 * Plain-language readings of service results (audit F-18, U-02). Each sentence
 * restates numbers the API returned; it computes no new measure and gives no advice.
 */
import type { Backtest, BacktestPeriod, Drawdown, FundRegimes } from './api';
import { date, month, pct } from './format';

/** The backtest in one plain sentence: did the signal beat the median in-sample, and did it hold on the hold-out? (audit F-18) */
export function backtestVerdict(result: Backtest): string {
  const { in_sample: a, holdout: b } = result.summary;
  const top = `the top ${result.strategy.top}`;
  const part = (p: BacktestPeriod) => `${top} grew ${pct(p.strategy_annualised)} a year against ${pct(p.median_annualised)} for the group median`;
  if (!a || !b) return 'There are not enough months to judge this signal on both periods.';
  const first = `In-sample (${month(a.first_signal)} – ${month(a.last_signal)}), ${part(a)}.`;
  const second = `On the hold-out (${month(b.first_signal)} – ${month(b.last_signal)}), ${part(b)}.`;
  const inAhead = a.strategy_annualised >= a.median_annualised;
  const outAhead = b.strategy_annualised >= b.median_annualised;
  const verdict =
    inAhead && outAhead
      ? 'The signal held up on months it was not tuned on. One hold-out period is not proof.'
      : inAhead
        ? 'The signal worked in-sample and did not hold up on the hold-out, so do not rely on the in-sample result.'
        : outAhead
          ? 'The signal lagged in-sample and led on the hold-out. The evidence is mixed.'
          : 'The signal lagged the median in both periods.';
  return `${first} ${second} ${verdict}`;
}


export interface FallVerdict {
  start: string;
  end: string;
  fund: number;
  proxy: number;
  /** Days from the fund's trough to its next peak; null when it has not recovered. */
  recoveryDays: number | null;
  recovered: boolean;
  text: string;
}

/**
 * The fund in the deepest market-proxy fall it lived through, and whether it
 * regained its peak afterwards. Null when the fund has no NAV in any fall window.
 */
export function fallVerdict(windows: FundRegimes['windows'], drawdowns: Drawdown[]): FallVerdict | null {
  const falls = windows.filter((w) => w.kind !== 'recovery' && w.fund_return !== null && w.proxy_return < 0);
  if (!falls.length) return null;
  const w = falls.reduce((a, b) => (b.proxy_return < a.proxy_return ? b : a));
  const fund = w.fund_return!;
  // The fund's own fall that overlaps the window tells how long its recovery took;
  // its trough can land a day after the proxy's.
  const own = drawdowns.find((d) => d.peak <= w.end && d.trough >= w.start);
  const recovered = own ? own.recovery !== null : false;
  const recoveryDays = own?.recovery_days ?? null;
  const compare = fund > w.proxy_return ? 'less than' : fund < w.proxy_return ? 'more than' : 'as much as';
  const tail = !own
    ? '.'
    : recovered
      ? `, and regained its previous peak ${recoveryDays} days after its low.`
      : ', and has not yet regained its previous peak.';
  const move = fund < 0 ? `lost ${pct(-fund)}` : `gained ${pct(fund)}`;
  const text = `In the deepest market fall it lived through (${date(w.start)} to ${date(w.end)}), it ${move}, ${compare} the market proxy's ${pct(-w.proxy_return)} fall${tail}`;
  return { start: w.start, end: w.end, fund, proxy: w.proxy_return, recoveryDays, recovered, text };
}
