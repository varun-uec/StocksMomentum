'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import RunSummaryCards from '@/components/dashboard/RunSummaryCards';
import MomentumTable from '@/components/dashboard/MomentumTable';
import { getLatestRunForStrategy, getRankings, getDataFreshness } from '@/lib/api-client';
import { Badge, PageHeader, EmptyState, LoadingSpinner, ErrorMessage } from '@/components/shared/Card';
import { HORIZONS, DEFAULT_HORIZON, type Horizon } from '@/lib/horizons';
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
    passed_count: (stats.passed_count as number) ?? 0,
    failed_count: (stats.failed_count as number) ?? 0,
    execution_duration_seconds: (stats.duration_seconds as number) ?? 0,
  };
}

function HorizonSelector({
  selected,
  onSelect,
}: {
  selected: Horizon;
  onSelect: (h: Horizon) => void;
}) {
  return (
    <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-lg p-1">
      {HORIZONS.map((h) => (
        <button
          key={h.strategyName}
          type="button"
          onClick={() => onSelect(h)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${focusRing} ${
            selected.strategyName === h.strategyName
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700/60'
          }`}
        >
          {h.label}
        </button>
      ))}
    </div>
  );
}

export default function Home() {
  const router = useRouter();
  const [horizon, setHorizon] = useState<Horizon>(DEFAULT_HORIZON);

  const { data: run, isLoading: runIdLoading, refetch: refetchRun, isFetching: runFetching } = useQuery({
    queryKey: ['latest-run', horizon.strategyName],
    queryFn: () => getLatestRunForStrategy(horizon.strategyName),
    refetchInterval: 60_000,
  });

  const { data: rankings, isLoading: rankingsLoading, error: rankingsError, refetch: refetchRankings, isFetching: rankingsFetching } = useQuery({
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

  const isLoading = runIdLoading || rankingsLoading;
  const isRefreshing = runFetching || rankingsFetching;

  // Re-fetch the latest completed live run (and its rankings) on demand. If a
  // newer run exists, react-query swaps in the new run id and the displayed
  // "Latest screening" timestamp updates accordingly.
  const handleRefresh = () => {
    void refetchRun().then(() => refetchRankings());
  };

  const handleSymbolClick = (symbol: string) => {
    router.push(`/stock/${symbol}?strategy=${horizon.strategyName}`);
  };

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Live Momentum Dashboard"
        subtitle="Top-ranked stocks based on deterministic momentum screening"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
          <HorizonSelector selected={horizon} onSelect={setHorizon} />
          {run && (
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
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className={`px-3 py-1.5 rounded-md text-xs font-medium border border-slate-200 dark:border-slate-700/60 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60 disabled:opacity-50 transition-colors ${focusRing}`}
          >
            {isRefreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </PageHeader>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {freshness && <StalenessBanner freshness={freshness} />}

        {isLoading && <LoadingSpinner text="Loading screening data…" />}

        {rankingsError && !isLoading && (
          <ErrorMessage message="Failed to load screening results. Is the backend running?" />
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
                message={`No stocks currently satisfy the ${horizon.label} methodology. This is expected behavior, not an error — Momentum25 never lowers its screening bar to populate a list. Check back after the next session, or try a different horizon.`}
              />
            ) : (
              <MomentumTable
                items={rankings.items}
                onSymbolClick={handleSymbolClick}
                title={`Ranked Universe — ${horizon.label}`}
              />
            )}
          </>
        )}

        {!isLoading && !rankings && !rankingsError && (
          <EmptyState message={`No completed screening runs found for the ${horizon.label} horizon. Trigger a run from the API.`} />
        )}
      </div>
    </main>
  );
}
