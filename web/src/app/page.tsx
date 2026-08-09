'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import RunSummaryCards from '@/components/dashboard/RunSummaryCards';
import MomentumTable from '@/components/dashboard/MomentumTable';
import { StrategySelector } from '@/components/dashboard/StrategySelector';
import {
  executeScreening,
  getLatestRunForStrategy,
  getRankings,
  getDataFreshness,
  getRun,
} from '@/lib/api-client';
import { Badge, PageHeader, EmptyState, LoadingSpinner, ErrorMessage } from '@/components/shared/Card';
import { useStrategy } from '@/app/strategy-context';
import type { RankingsResponse, ScreeningRunSummary, DataFreshnessDTO } from '@/lib/types';
import { focusRing } from '@/lib/theme';

/**
 * Data-freshness banner (Phase 1.5). Previously the only staleness signal
 * was a bare "Latest screening: <timestamp>" string -- indistinguishable
 * from a broken ingest without the reader doing calendar arithmetic
 * themselves. This states the classification explicitly, using the real
 * NSE trading calendar so a market-closed weekend/holiday never reads as
 * a problem.
 */
function StalenessBanner({ freshness }: { freshness: DataFreshnessDTO }) {
  if (freshness.classification === 'FRESH') return null;

  const isMarketClosed = freshness.classification === 'MARKET_CLOSED';
  const tone = isMarketClosed
    ? 'border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-300'
    : 'border-amber-200 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300';

  const message = isMarketClosed
    ? 'Market closed since the last session — no new data expected until it reopens.'
    : freshness.latest_bar_date
      ? `Data is ${freshness.sessions_missed} trading session${freshness.sessions_missed === 1 ? '' : 's'} behind — last bar ${freshness.latest_bar_date}.`
      : 'No market data has been ingested yet.';

  return (
    <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${tone}`}>
      <Badge color={isMarketClosed ? 'slate' : 'amber'}>{freshness.classification.replace('_', ' ')}</Badge>
      <span>{message}</span>
      {freshness.next_session && (
        <span className="text-slate-400 dark:text-slate-500 ml-auto tabular-nums">
          Next session: {freshness.next_session}
        </span>
      )}
    </div>
  );
}

/** Build a summary object from the run stats. */
function buildSummary(data: RankingsResponse): ScreeningRunSummary {
  const stats = data.run?.stats ?? {};
  return {
    total_evaluated: (stats.total_evaluated as number) ?? data.total,
    passed_count: (stats.total_passed as number) ?? 0,
    failed_count: (stats.total_failed as number) ?? 0,
    execution_duration_seconds: (stats.duration_seconds as number) ?? 0,
  };
}

export default function Home() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { strategyName } = useStrategy();
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [screeningError, setScreeningError] = useState<string | null>(null);

  const { data: run, isLoading: runIdLoading, isFetching: runFetching } = useQuery({
    queryKey: ['latest-run', strategyName],
    queryFn: () => getLatestRunForStrategy(strategyName),
    refetchInterval: 60_000,
  });

  const { data: rankings, isLoading: rankingsLoading, error: rankingsError, isFetching: rankingsFetching } = useQuery({
    queryKey: ['rankings', run?.id],
    queryFn: () => getRankings(run!.id, 100, 0),
    enabled: run !== null && run !== undefined,
    refetchInterval: 60_000,
  });

  const { data: freshness } = useQuery({
    queryKey: ['data-freshness'],
    queryFn: getDataFreshness,
    refetchInterval: 60_000,
  });

  // Start an on-demand screening run. The button is the manual fallback for
  // the scheduler: the API runs the pipeline in the background, this page
  // polls the new run's status until it finishes, then swaps the dashboard
  // to the fresh snapshot.
  const refreshMutation = useMutation({
    mutationFn: () => executeScreening(strategyName),
    onSuccess: (created) => {
      setScreeningError(null);
      setActiveRunId(created.id);
    },
    onError: (err) => setScreeningError(err instanceof Error ? err.message : 'Screening failed to start.'),
  });

  const { data: activeRun } = useQuery({
    queryKey: ['active-run', activeRunId],
    queryFn: () => getRun(activeRunId!),
    enabled: activeRunId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'PENDING' || status === 'RUNNING' ? 5000 : false;
    },
  });

  useEffect(() => {
    if (!activeRun) return;
    if (activeRun.status === 'COMPLETED') {
      queryClient.invalidateQueries({ queryKey: ['latest-run', strategyName] });
      queryClient.invalidateQueries({ queryKey: ['data-freshness'] });
      setActiveRunId(null);
    } else if (activeRun.status === 'FAILED') {
      setScreeningError(activeRun.error ?? 'Screening run failed.');
      setActiveRunId(null);
    }
  }, [activeRun, strategyName, queryClient]);

  const isLoading = runIdLoading || rankingsLoading;
  const isScreening = refreshMutation.isPending || activeRunId !== null;
  const isRefreshing = runFetching || rankingsFetching || isScreening;

  const handleSymbolClick = (symbol: string) => {
    router.push(`/stock/${symbol}?strategy=${strategyName}`);
  };

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Live Momentum Dashboard"
        subtitle="Top-ranked stocks based on deterministic momentum screening"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
          <StrategySelector />
          {run && isScreening && activeRun && (
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <Badge color="amber">Run #{activeRun.id} screening in progress</Badge>
            </div>
          )}
          {run && !isScreening && (
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <Badge color="indigo">Run #{run.id}</Badge>
              <span className="tabular-nums">
                Latest screening:{' '}
                {new Date(run.finished_at ?? run.run_date).toLocaleString(undefined, {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          )}
          <div className="flex flex-col items-start gap-1">
            <button
              type="button"
              onClick={() => refreshMutation.mutate()}
              disabled={isRefreshing}
              className={`px-3 py-1.5 rounded-md text-xs font-medium border border-slate-200 dark:border-slate-700/60 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60 disabled:opacity-50 transition-colors ${focusRing}`}
            >
              {isScreening ? 'Screening…' : 'Refresh'}
            </button>
            <span className="text-[10px] text-slate-400 dark:text-slate-500">
              This re-evaluates the universe; it usually takes a few minutes.
            </span>
          </div>
        </div>
      </PageHeader>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {freshness && <StalenessBanner freshness={freshness} />}

        {isLoading && <LoadingSpinner text="Loading screening data…" />}

        {(rankingsError || screeningError) && !isLoading && (
          <ErrorMessage
            message={screeningError ?? 'Failed to load screening results. Is the backend running?'}
          />
        )}

        {rankings && !isLoading && (
          <>
            {/* Summary Cards + Last Refresh */}
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <RunSummaryCards summary={buildSummary(rankings)} />
              </div>
              {rankings.run?.finished_at && (
                <div className="text-xs text-slate-500 text-left sm:text-right whitespace-nowrap bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700/40 rounded-xl px-3 py-2 shadow-sm">
                  <div className="text-slate-400 dark:text-slate-500">Last refresh</div>
                  <div className="tabular-nums font-medium text-slate-700 dark:text-slate-300">
                    {new Date(rankings.run.finished_at).toLocaleString()}
                  </div>
                </div>
              )}
            </div>

            {rankings.items.length === 0 ? (
              <EmptyState
                message={`No stocks currently satisfy the ${strategyName} methodology. This is expected behavior, not an error — Momentum25 never lowers its screening bar to populate a list. Check back after the next session, or try a different strategy.`}
              />
            ) : (
              <MomentumTable
                items={rankings.items}
                onSymbolClick={handleSymbolClick}
                title="Ranked Universe"
              />
            )}
          </>
        )}

        {!isLoading && !rankings && !rankingsError && (
          <EmptyState message="No completed screening runs found for this strategy. Trigger a run from the API." />
        )}
      </div>
    </main>
  );
}
