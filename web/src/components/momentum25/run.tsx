/**
 * Momentum25's run in view and its provenance line (plan 2026-10-19,
 * "Run-level consistency"). Every Momentum25 view shows which strategy, run,
 * as-of date and data version its numbers come from, so a mismatch between
 * two views is always visible.
 */

import { useQuery } from '@tanstack/react-query';
import { getLatestRunForStrategy } from '@/lib/api-client';
import type { RunDTO } from '@/lib/types';

/** The latest run of a strategy: the run in view on /chart and the default screener. */
export function useLatestRun(strategy: string) {
  return useQuery({
    queryKey: ['latest-run', strategy],
    queryFn: () => getLatestRunForStrategy(strategy),
    refetchInterval: 60_000,
  });
}

/** "strategy · run #N · as of DATE · data VERSION". `undefined` while the run loads; `null` when none exists. */
export function ProvenanceLine({ strategy, run, label }: { strategy: string; run: Pick<RunDTO, 'id' | 'run_date' | 'data_version'> | null | undefined; label?: string }) {
  const text =
    run === undefined
      ? `${strategy} · loading run…`
      : run === null
        ? `${strategy} · no completed run`
        : `${strategy} · run #${run.id} · as of ${run.run_date.slice(0, 10)} · data ${run.data_version.slice(0, 8)}`;
  return (
    <p data-testid="provenance" className="text-[11px] leading-4 text-slate-500 dark:text-slate-400 tabular-nums">
      {label && <span className="font-medium">{label} · </span>}
      {text}
    </p>
  );
}
