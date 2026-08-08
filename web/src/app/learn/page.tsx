import Link from 'next/link';
import { PageHeader } from '@/components/shared/Card';
import { Prose, SectionHeading } from '@/components/learn/MethodologyNote';
import { focusRing } from '@/lib/theme';

const CARDS = [
  {
    href: '/learn/momentum-investing',
    title: 'Momentum Investing',
    body: 'What momentum investing is, why it persists as a market anomaly, and how holding period changes what "momentum" means.',
  },
  {
    href: '/learn/minervini-methodology',
    title: "Mark Minervini's Methodology",
    body: 'Stage analysis, the Trend Template, relative strength, institutional accumulation, constructive bases, and risk management.',
  },
  {
    href: '/learn/momentum25-methodology',
    title: 'Momentum25 Methodology',
    body: 'The complete pipeline: universe selection, eligibility gates, indicators, pattern recognition, scoring, ranking, and explainability.',
  },
  {
    href: '/learn/scoring-guide',
    title: 'Scoring Guide',
    body: 'What the Momentum Score and Buy Setup Score measure, how each engine contributes, and what moves them up or down.',
  },
  {
    href: '/learn/rule-guide',
    title: 'Rule Guide',
    body: 'Every rule the engine evaluates today, with its live threshold, rationale, and a worked pass/fail example.',
  },
  {
    href: '/learn/faq',
    title: 'Frequently Asked Questions',
    body: 'Why a stock wasn’t selected, why the list can be short, and other questions the rankings raise.',
  },
];

export default function LearnOverviewPage() {
  return (
    <div>
      <PageHeader
        title="Learning Center"
        subtitle="Understand the methodology behind every ranking before you trust it"
      />
      <div className="mt-6">
        <Prose>
          <p>
            Momentum25 India screens the NSE for stocks in a confirmed Stage 2 uptrend using a
            deterministic, rule-based implementation of momentum and trend-following principles
            popularized by Mark Minervini. Every score you see on the dashboard is produced by
            evaluating a fixed set of rules against real price and volume data &mdash; there is no
            discretionary judgment, no hidden weighting, and no randomness. Given the same market
            data, the platform always produces the same ranking.
          </p>
          <p>
            This section explains the methodology in plain language, shows exactly how
            Momentum25&rsquo;s implementation maps to (and occasionally departs from) the published
            methodology, and documents every rule and threshold currently in force &mdash; pulled
            live from the active strategy configuration, so this page can never drift out of sync
            with what the engine actually does.
          </p>
        </Prose>
      </div>

      <SectionHeading>Where to start</SectionHeading>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {CARDS.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className={`group block rounded-xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/50 p-4 hover:border-indigo-400 dark:hover:border-indigo-600/60 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all shadow-sm hover:shadow-md ${focusRing}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                {c.title}
              </div>
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-4 h-4 text-slate-400 group-hover:text-indigo-500 transition-colors shrink-0 mt-0.5"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06.02z"
                />
              </svg>
            </div>
            <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{c.body}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
