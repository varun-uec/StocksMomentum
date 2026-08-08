import { PageHeader } from '@/components/shared/Card';
import { Prose, SectionHeading } from '@/components/learn/MethodologyNote';

const STAGES = [
  {
    title: 'Universe',
    body: 'Every active NSE equity in the strategy’s configured universe (NIFTY 500 constituents by default) is a candidate. Each session’s Bhavcopy provides EOD OHLCV for the full exchange.',
  },
  {
    title: 'Eligibility Gates',
    body: 'Minimum price, minimum average turnover, and minimum history length are enforced before any scoring happens — a stock that is too illiquid, too cheap, or too new to have a reliable 200-day average never reaches the scoring stage.',
  },
  {
    title: 'Indicator Calculation',
    body: 'Deterministic technical indicators are computed once per stock per day: 50/150/200-day SMAs and their slopes, 52-week high/low, ATR/ADR volatility, relative volume, and multi-period returns for Relative Strength.',
  },
  {
    title: 'Pattern Recognition',
    body: 'VCP, Cup-with-Handle, Ascending Base, Flat Base, and High Tight Flag detectors run against the price history, each producing a quality-scored pass/fail rule result.',
  },
  {
    title: 'Rule Evaluation',
    body: 'Every engine (Trend Template, Relative Strength, Volume & Accumulation, Pattern, Breakout, Momentum Quality, Risk) evaluates its rules independently and deterministically against the computed indicators.',
  },
  {
    title: 'Scoring',
    body: 'Each engine produces a 0–1 engine score. A weighted combination (configured per strategy) produces two headline numbers: the Momentum Score (is this a genuine Stage 2 leader?) and the Buy Setup Score (is now the right entry moment?).',
  },
  {
    title: 'Ranking',
    body: 'Stocks that fail any mandatory gate (Trend Template, minimum liquidity) are excluded entirely — not merely scored lower. Passing stocks are sorted by Momentum Score, then Buy Setup Score, then RS rating, then symbol, for a fully deterministic order.',
  },
  {
    title: 'Explainability',
    body: 'Every rule evaluated for every stock is persisted alongside the run, so any ranking can be explained — in full, rule by rule — at any point in the future, not just at screening time.',
  },
  {
    title: 'Research',
    body: 'The research platform replays historical strategy configurations against historical data to measure rule effectiveness, engine contribution, and ranking stability over time — the same evidence used to calibrate this methodology.',
  },
];

export default function Momentum25MethodologyPage() {
  return (
    <div>
      <PageHeader
        title="Momentum25 Methodology"
        subtitle="The complete, deterministic screening pipeline, stage by stage"
      />
      <Prose>
        <p>
          Every ranking on the dashboard is the output of the same nine-stage pipeline, run
          identically for every stock in the universe. There is no manual curation at any stage
          &mdash; the pipeline is a pure function of (market data, strategy configuration): the
          same inputs always produce the same outputs.
        </p>
      </Prose>

      <SectionHeading>The pipeline</SectionHeading>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {STAGES.map((s, i) => (
          <div
            key={s.title}
            className="flex gap-4 rounded-xl border border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/40 p-4"
          >
            <div className="shrink-0 w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-600/20 text-indigo-600 dark:text-indigo-300 text-sm font-bold flex items-center justify-center">
              {i + 1}
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">{s.title}</div>
              <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{s.body}</div>
            </div>
          </div>
        ))}
      </div>

      <SectionHeading>Determinism</SectionHeading>
      <Prose>
        <p>
          Given the same market data snapshot and the same versioned strategy configuration
          (identified by a content hash), re-running the pipeline always produces byte-identical
          scores and rankings. This is what makes every explanation on this platform trustworthy:
          it describes the actual calculation that produced the number you&rsquo;re looking at, not
          an approximation of it.
        </p>
      </Prose>
    </div>
  );
}
