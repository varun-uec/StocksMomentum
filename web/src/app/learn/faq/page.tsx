import { PageHeader } from '@/components/shared/Card';
import { SectionHeading } from '@/components/learn/MethodologyNote';

const FAQS = [
  {
    q: 'Why wasn’t my stock selected?',
    a: 'Every stock is evaluated against the same 8-point Trend Template, and all 8 conditions must pass — there is no partial credit. Open the stock’s page and check its Rule Evaluation panel: it will show exactly which condition(s) failed, with the actual value versus the required threshold. The most common reasons are: price not yet above the 200-day average, an RS rating below 70, or trading too close to the 52-week low.',
  },
  {
    q: 'Why are there fewer than 25 stocks today?',
    a: 'Momentum25 never manufactures candidates to fill a fixed list size. The Trend Template is a hard gate: only stocks that genuinely satisfy all 8 conditions are ranked. On any given day, the number of qualifying stocks reflects actual market breadth — in a narrow or weak market, that number can be small, and on a day with no qualifying stocks at all, the dashboard will show zero and say so explicitly, rather than lowering the bar to produce a list.',
  },
  {
    q: 'What is a Stage-2 stock?',
    a: 'Stage 2 is the "advancing" phase of a stock’s cycle (see the Stage Analysis section of the Minervini Methodology page) — a confirmed uptrend with rising moving averages in bullish order, strong relative performance, and price well off its lows and near its highs. It is the only stage this methodology screens for.',
  },
  {
    q: 'Why is Relative Strength important?',
    a: 'A stock can rise in absolute terms while still lagging the broader market — that is not leadership. Relative Strength measures performance versus the universe, not just versus zero, which is what distinguishes a genuine leader from a stock merely drifting up with a rising tide.',
  },
  {
    q: 'What is a proper breakout?',
    a: 'A proper breakout clears the resistance defined by a well-formed base, at or near the base’s pivot point, on volume meaningfully above average (Momentum25 checks for at least 1.4x the 50-day average volume) — and does not immediately reverse back below the breakout day’s midpoint. A move on light volume, or one that reverses the same session, is flagged as unconfirmed or false.',
  },
  {
    q: 'Why can a stock have a high Momentum Score but a low Buy Setup Score?',
    a: 'The Momentum Score answers "is this a genuine Stage 2 leader?" while the Buy Setup Score answers "is right now a good entry?" A stock can be a legitimate leader that already made its move weeks ago and is now consolidating or extended — high momentum quality, but a poor fresh entry point today. See the Scoring Guide for exactly how each score is weighted.',
  },
  {
    q: 'Why do the rankings change from one day to the next?',
    a: 'Every indicator (moving averages, RS, volume, patterns) is recomputed from the latest closing price each session, so scores move incrementally day to day. A stock can also enter or leave the ranked universe entirely if it starts or stops passing the Trend Template gate.',
  },
  {
    q: 'Is this financial advice?',
    a: 'No. Momentum25 is a deterministic research and screening tool that implements a documented technical methodology. It does not execute trades, size positions, or manage risk on your behalf — those decisions, and their consequences, remain entirely yours.',
  },
];

export default function FAQPage() {
  return (
    <div>
      <PageHeader title="Frequently Asked Questions" />
      <SectionHeading>Questions the rankings raise</SectionHeading>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {FAQS.map((f) => (
          <div
            key={f.q}
            className="rounded-xl border border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/40 p-4"
          >
            <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1.5">{f.q}</div>
            <div className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{f.a}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
