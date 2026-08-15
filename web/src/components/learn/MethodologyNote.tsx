import Link from 'next/link';
import type { ReactNode } from 'react';

type Kind = 'published' | 'approximation' | 'implementation';

const STYLES: Record<Kind, { label: string; className: string; icon: string }> = {
  published: {
    label: 'Published Methodology',
    className:
      'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-700/50 dark:bg-emerald-950/30 dark:text-emerald-200',
    icon: 'M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25',
  },
  approximation: {
    label: 'Engineering Approximation',
    className:
      'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/30 dark:text-amber-200',
    icon: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z',
  },
  implementation: {
    label: 'Momentum25 Implementation Choice',
    className:
      'border-indigo-300 bg-indigo-50 text-indigo-900 dark:border-indigo-700/50 dark:bg-indigo-950/30 dark:text-indigo-200',
    icon: 'M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5',
  },
};

/**
 * Distinguishes published Minervini methodology from where Momentum25 had to
 * make a concrete engineering decision (a threshold, a proxy, a simplification)
 * that isn't dictated by the source methodology.
 */
export function MethodologyNote({ kind, children }: { kind: Kind; children: ReactNode }) {
  const style = STYLES[kind];
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm my-4 ${style.className}`}>
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider mb-1 opacity-90">
        <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 opacity-70">
          <path fillRule="evenodd" clipRule="evenodd" d={style.icon} />
        </svg>
        {style.label}
      </div>
      <div className="text-slate-800 dark:text-slate-200">{children}</div>
    </div>
  );
}

export function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mt-8 mb-3 first:mt-0">{children}</h2>
  );
}

export function SubHeading({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mt-5 mb-2">{children}</h3>;
}

export function Prose({ children }: { children: ReactNode }) {
  return <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed space-y-3">{children}</div>;
}

/**
 * One source for the score-series caveat. Score Stability, Score Downside
 * Stability and Score Gain/Loss Ratio are shaped like Sharpe, Sortino and
 * profit factor, but they are computed over the momentum score, not over
 * returns. Both research pages said this in their own words (audit §2.3 / U7);
 * they now say it once, here.
 */
export function ScoreSeriesDisclaimer({ className = '' }: { className?: string }) {
  return (
    <p className={`text-xs text-slate-500 dark:text-slate-400 ${className}`}>
      All figures are derived from the momentum-score series and run counts — a setup-quality
      rating, not a return. Score Stability, Score Downside Stability and Score Gain/Loss Ratio
      are shaped like Sharpe, Sortino and profit factor but carry no profit or return meaning.
      Realised performance metrics live on the{' '}
      <Link href="/validation" className="underline hover:text-slate-700 dark:hover:text-slate-300">
        Validation
      </Link>{' '}
      page and require ingested forward returns.
    </p>
  );
}
