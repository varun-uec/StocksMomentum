'use client';

import type { ScreeningRunSummary } from '@/lib/types';
import { typography } from '@/lib/theme';

interface RunSummaryCardsProps {
  summary: ScreeningRunSummary;
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

  const borderColors: Record<string, string> = {
    emerald: 'border-emerald-200 dark:border-emerald-800/40',
    amber: 'border-amber-200 dark:border-amber-800/40',
    rose: 'border-rose-200 dark:border-rose-800/40',
    slate: 'border-slate-200 dark:border-slate-700/60',
    indigo: 'border-indigo-200 dark:border-indigo-800/40',
  };

  return (
    <div
      className={`bg-white dark:bg-slate-900/80 border ${borderColors[accent]} rounded-xl px-5 py-4 flex flex-col gap-1 shadow-sm`}
    >
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {label}
      </span>
      <span className={`${typography.metricValue} ${accentColors[accent]}`}>{value}</span>
      {description && (
        <span className="text-xs text-slate-500 dark:text-slate-500 leading-snug">{description}</span>
      )}
    </div>
  );
}

export default function RunSummaryCards({ summary }: RunSummaryCardsProps) {
  const passRate =
    summary.total_evaluated > 0
      ? ((summary.passed_count / summary.total_evaluated) * 100).toFixed(1)
      : '0.0';

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
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
        label="Duration"
        value={`${summary.execution_duration_seconds.toFixed(2)}s`}
        accent="indigo"
        description="End-to-end screening time"
      />
    </div>
  );
}
