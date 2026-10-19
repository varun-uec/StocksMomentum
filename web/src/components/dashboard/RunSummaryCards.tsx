import type { ScreeningRunSummary } from '@/lib/types';

interface RunSummaryCardsProps {
  summary: ScreeningRunSummary;
  /** RS ratings of the ranked stocks on screen. Empty when none are rated. */
  rsRatings?: number[];
}

function StatCard({
  label,
  value,
  accent,
  description,
}: {
  label: string;
  value: string | number;
  accent: 'emerald' | 'amber' | 'rose' | 'slate' | 'indigo';
  description?: string;
}) {
  const accentColors: Record<string, string> = {
    emerald: 'text-emerald-600 dark:text-emerald-400',
    amber: 'text-amber-600 dark:text-amber-400',
    rose: 'text-rose-600 dark:text-rose-400',
    slate: 'text-slate-800 dark:text-slate-100',
    indigo: 'text-indigo-600 dark:text-indigo-400',
  };

  // One cell of the stat strip; the description is the cell's tooltip.
  return (
    <div title={description} className="flex items-baseline gap-2 px-4 py-1.5 border-l border-[var(--ws-line)] first:border-l-0 first:pl-0">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</span>
      <span className={`text-base font-bold tabular-nums ${accentColors[accent]}`}>{value}</span>
      {description && <span className="sr-only">{description}</span>}
    </div>
  );
}

export default function RunSummaryCards({ summary, rsRatings = [] }: RunSummaryCardsProps) {
  const passRate =
    summary.total_evaluated > 0
      ? ((summary.passed_count / summary.total_evaluated) * 100).toFixed(1)
      : '0.0';

  // Run duration says nothing about the stocks. Average RS rating does.
  const avgRs = rsRatings.length
    ? Math.round(rsRatings.reduce((a, b) => a + b, 0) / rsRatings.length)
    : null;
  const topRs = rsRatings.length ? Math.max(...rsRatings) : null;

  return (
    <div className="flex flex-wrap items-center" aria-label="Run summary" role="group">
      <StatCard
        label="Universe"
        value={summary.total_evaluated}
        accent="slate"
        description="Stocks evaluated against the methodology"
      />
      <StatCard
        label="Qualified"
        value={summary.passed_count}
        accent="emerald"
        description={`${passRate}% passed the Trend Template gate`}
      />
      <StatCard
        label="Filtered Out"
        value={summary.failed_count}
        accent="rose"
        description="Failed one or more hard gates"
      />
      <StatCard
        label="Avg RS Rating"
        value={avgRs ?? '—'}
        accent="indigo"
        description={
          topRs === null
            ? 'No RS rating available for the ranked stocks'
            : `Across ${rsRatings.length} ranked stocks · top ${topRs}`
        }
      />
    </div>
  );
}
