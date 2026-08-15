'use client';

import { useQuery } from '@tanstack/react-query';
import { getStrategyDetail } from '@/lib/api-client';
import { PageHeader, LoadingSpinner, ErrorMessage } from '@/components/shared/Card';
import { Prose, SectionHeading, SubHeading } from '@/components/learn/MethodologyNote';

const ENGINE_GUIDE: Record<
  string,
  { label: string; measures: string; matters: string; improves: string; reduces: string }
> = {
  trend_template: {
    label: 'Trend Template',
    measures: 'Whether the stock is in a confirmed Stage 2 uptrend (Minervini’s 8-point checklist).',
    matters: 'This is the mandatory gate — a stock that fails it is excluded from ranking entirely, regardless of every other score.',
    improves: 'Price holding above rising 50/150/200-day averages in bullish order, trading well off 52-week lows and near 52-week highs, RS ≥ 70.',
    reduces: 'Any single failed condition removes the stock from the ranked universe — there is no partial credit on the gate itself.',
  },
  relative_strength: {
    label: 'Relative Strength',
    measures: 'How much the stock has outperformed the broader universe over multiple lookback windows.',
    matters: 'Momentum leadership is relative, not absolute — a rising stock that is merely tracking the index isn’t a leader.',
    improves: 'A high percentile RS rating, an RS line making new highs relative to the benchmark, and outperformance versus sector/industry peers.',
    reduces: 'Flat or negative relative performance versus the benchmark, or an RS line that is rolling over even as price holds up.',
  },
  volume_accumulation: {
    label: 'Volume & Accumulation',
    measures: 'Evidence of institutional buying: net accumulation days, adequate liquidity, and breakout volume confirmation.',
    matters: 'Sustainable advances are driven by large, informed buyers, not thin retail speculation.',
    improves: 'More above-average-volume up days than down days over the trailing window, and volume expansion on breakout days.',
    reduces: 'More distribution days than accumulation days, or a breakout on unremarkable volume that fails to confirm.',
  },
  pattern: {
    label: 'Pattern Recognition',
    measures: 'Whether the stock has formed a recognizable, high-quality base (VCP, Cup-with-Handle, Ascending Base, Flat Base, High Tight Flag).',
    matters: 'A well-formed base reflects an orderly transfer from weak to strong hands, and precedes the highest-quality breakouts.',
    improves: 'A tight, low-volatility base with volume contraction as it matures.',
    reduces: 'No detected pattern (neutral, not penalized) or a wide, volatile base with no clear structure.',
  },
  breakout: {
    label: 'Breakout',
    measures: 'Whether the stock is actively breaking out of its base at (or near) the pivot point, with volume confirmation.',
    matters: 'This is the entry-timing signal — the single largest weight in the Buy Setup Score.',
    improves: 'Price near the top of its recent trading range, short-term averages confirming the move, and relative volume clearing 1.4x average.',
    reduces: 'Price well below the recent range high, or a breakout that immediately reverses below the breakout day’s midpoint (false breakout).',
  },
  momentum_quality: {
    label: 'Momentum Quality',
    measures: 'Whether the uptrend is persistent (price consistently above its 50-day average) and accelerating rather than decelerating.',
    matters: 'Distinguishes a steady, sustainable advance from one that has already peaked and is losing steam.',
    improves: 'Price spending most of the recent quarter above its 50-day average, with recent short-term returns outpacing the longer-term trend.',
    reduces: 'A trend that technically remains intact but has clearly slowed — recent returns well below the trailing 63-day pace.',
  },
  risk: {
    label: 'Risk',
    measures: 'How extended the stock is above its 50-day average, its volatility (ADR%), and how far below price a protective stop must sit.',
    matters: 'Even a genuine Stage 2 leader can be a poor entry if it has already run too far or has become too volatile to size safely.',
    improves: 'Trading close to its 50-day average (not extended), moderate daily volatility, and a protective stop that can sit close beneath price.',
    reduces: 'Being extended more than 25% above the 50-day average, high ADR%, or a protective stop that must sit far below price.',
  },
  fundamental: {
    label: 'Fundamentals',
    measures: 'Reserved for future earnings/sales-growth criteria.',
    matters: 'Disabled in the current MVP — see Remaining Limitations.',
    improves: 'N/A (disabled)',
    reduces: 'N/A (disabled)',
  },
};

export default function ScoringGuidePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['strategy-detail', 'minervini_trend_template'],
    queryFn: () => getStrategyDetail('minervini_trend_template'),
  });

  const momentumWeights = data?.config.scoring.momentum_weights ?? {};
  const buySetupWeights = data?.config.scoring.buy_setup_weights ?? {};
  const engineIds = data?.config.engines.filter((e) => e.enabled).map((e) => e.id) ?? [];

  return (
    <div>
      <PageHeader
        title="Scoring Guide"
        subtitle="What each score measures, using the live weights from the active strategy"
      />

      <SectionHeading>Momentum Score vs. Buy Setup Score</SectionHeading>
      <Prose>
        <p>
          Momentum25 deliberately produces <span className="text-slate-900 dark:text-slate-200 font-medium">two</span>{' '}
          headline scores rather than one, because &ldquo;is this a genuine momentum leader&rdquo;
          and &ldquo;is right now a good time to buy it&rdquo; are different questions with
          different answers.
        </p>
        <p>
          The <span className="text-slate-900 dark:text-slate-200 font-medium">Momentum Score</span> weights the Trend
          Template and Relative Strength most heavily &mdash; it answers &ldquo;does this stock
          qualify as a Stage 2 leader?&rdquo; The{' '}
          <span className="text-slate-900 dark:text-slate-200 font-medium">Buy Setup Score</span> weights Breakout and
          Volume & Accumulation most heavily &mdash; it answers &ldquo;is this stock actively
          breaking out, right now, with confirmation?&rdquo; A stock can have a high Momentum Score
          and a low Buy Setup Score: it&rsquo;s a genuine leader, but it already made its move and
          isn&rsquo;t at a fresh entry point today.
        </p>
      </Prose>

      {isLoading && <LoadingSpinner text="Loading live strategy weights…" />}
      {error && <ErrorMessage message="Could not load the active strategy configuration." />}

      {data && (
        <>
          <SectionHeading>Engine weights (live, from the active strategy)</SectionHeading>
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700/60">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 dark:text-slate-500 text-xs uppercase tracking-wider">
                  <th scope="col" className="text-left py-3 px-3">Engine</th>
                  <th scope="col" className="text-right py-3 px-3">Momentum Weight</th>
                  <th scope="col" className="text-right py-3 px-3">Buy Setup Weight</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-700 dark:text-slate-300">
                {engineIds.map((id) => (
                  <tr key={id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                    <td className="py-3 px-3 font-medium text-slate-900 dark:text-slate-200">
                      {ENGINE_GUIDE[id]?.label ?? id}
                    </td>
                    <td className="py-3 px-3 text-right tabular-nums">{momentumWeights[id] ?? '—'}</td>
                    <td className="py-3 px-3 text-right tabular-nums">{buySetupWeights[id] ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Strategy version {data.version} &middot; config hash{' '}
            <span className="font-mono">{data.config_hash.slice(0, 16)}</span>
          </p>

          <SectionHeading>What each engine measures</SectionHeading>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {engineIds.map((id) => {
              const g = ENGINE_GUIDE[id];
              if (!g) return null;
              return (
                <div
                  key={id}
                  className="rounded-xl border border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/40 p-4"
                >
                  <SubHeading>{g.label}</SubHeading>
                  <div className="text-sm text-slate-700 dark:text-slate-300 space-y-1.5">
                    <p>
                      <span className="text-slate-500">Measures: </span>
                      {g.measures}
                    </p>
                    <p>
                      <span className="text-slate-500">Why it matters: </span>
                      {g.matters}
                    </p>
                    <p>
                      <span className="text-emerald-600 dark:text-emerald-400">Improves the score: </span>
                      {g.improves}
                    </p>
                    <p>
                      <span className="text-rose-600 dark:text-rose-400">Reduces the score: </span>
                      {g.reduces}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
