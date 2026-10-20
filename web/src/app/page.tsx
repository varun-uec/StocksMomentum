import { useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import { Link, useSearchParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import RunSummaryCards from '@/components/dashboard/RunSummaryCards';
import MomentumTable from '@/components/dashboard/MomentumTable';
import { useShell, useShellPanel } from '@/components/shell/shell-context';
import { ProvenanceLine, useRunRankings } from '@/components/momentum25/run';
import { applyFilters, COLUMN_SETS, ScreenerToolbar, useScreen } from '@/components/momentum25/screener';
import { StrategySelector } from '@/components/dashboard/StrategySelector';
import {
  executeScreening,
  getLatestRunForStrategy,
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
function StalenessBanner({ freshness }: { freshness?: DataFreshnessDTO }) {
  // The row is always in the layout and only its contents change, so a
  // FRESH -> STALE transition never inserts a row and shifts the table.
  const hidden = !freshness || freshness.classification === 'FRESH';
  if (hidden) return <div className="h-0" aria-hidden="true" />;

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
        <span className="text-slate-600 dark:text-slate-400 ml-auto tabular-nums">
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
  const queryClient = useQueryClient();
  const { strategyName, strategyHash } = useStrategy();
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [screeningError, setScreeningError] = useState<string | null>(null);

  const { data: run, isLoading: runIdLoading, isFetching: runFetching } = useQuery({
    queryKey: ['latest-run', strategyName, strategyHash],
    queryFn: () => getLatestRunForStrategy(strategyName, undefined, strategyHash),
    refetchInterval: 60_000,
  });

  // `?run=N` pins an older or historical run (Research → Historical); otherwise the latest run.
  const [params] = useSearchParams();
  const pinnedRun = Number(params.get('run')) || null;
  const viewRunId = pinnedRun ?? run?.id;
  const historical = pinnedRun !== null && pinnedRun !== run?.id;
  // Keep the previous run's rows on screen while the next one loads.
  const { data: candidateRankings, isLoading: rankingsLoading, error: rankingsError, isFetching: rankingsFetching } = useRunRankings(viewRunId, { keepPrevious: true });
  // The query keeps the previous page while a new run loads. That is useful
  // during refreshes, but it must never make another strategy's rows look like
  // the selected strategy's results (especially when the selected version has
  // no run at all).
  const rankings = viewRunId !== undefined && candidateRankings?.run?.id === viewRunId ? candidateRankings : undefined;

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
    mutationFn: () => executeScreening(strategyName, false, strategyHash),
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
      queryClient.invalidateQueries({ queryKey: ['latest-run', strategyName, strategyHash] });
      queryClient.invalidateQueries({ queryKey: ['data-freshness'] });
      setActiveRunId(null);
    } else if (activeRun.status === 'FAILED') {
      setScreeningError(activeRun.error ?? 'Screening run failed.');
      setActiveRunId(null);
    }
  }, [activeRun, strategyName, strategyHash, queryClient]);

  const isLoading = runIdLoading || rankingsLoading;
  const isScreening = refreshMutation.isPending || activeRunId !== null;
  const isRefreshing = runFetching || rankingsFetching || isScreening;

  // The selected row is the route's context: the shell's Assessment panel shows it (A8.2).
  const [picked, setPicked] = useState<string | null>(null);
  const selected = rankings?.items.some((i) => i.symbol === picked) ? picked : null;
  const { openPanel } = useShell();
  useShellPanel({ symbol: selected ?? undefined, assessment: true, runId: rankings?.run?.id });
  const handleSymbolClick = (symbol: string) => {
    flushSync(() => setPicked(symbol));
    openPanel('details');
  };
  const screen = useScreen();
  const matches = rankings ? applyFilters(rankings.items, screen.filters) : [];

  return (
    <div className="min-h-full bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader title="Stock Screener" subtitle="Top-ranked stocks from deterministic momentum screening">
        <StrategySelector />
        {run && isScreening && activeRun && <Badge color="amber">Run #{activeRun.id} screening in progress</Badge>}
        <button
          type="button"
          onClick={() => refreshMutation.mutate()}
          disabled={isRefreshing}
          title="Uses stored market data; it does not download exchange data."
          className={`px-3 py-1 rounded-md text-xs font-medium border border-[var(--ws-line)] text-slate-600 dark:text-slate-300 hover:bg-[var(--ws-muted)] disabled:opacity-50 transition-colors ${focusRing}`}
        >
          {isScreening ? 'Screening…' : 'Run screening'}
        </button>
      </PageHeader>

      <div className="px-4 sm:px-6 py-3 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceLine strategy={rankings?.run?.strategy ?? strategyName} run={rankings?.run ?? (run === null && !pinnedRun ? null : undefined)} label={historical && rankings?.run ? `Historical — as of ${rankings.run.run_date.slice(0, 10)}` : undefined} />
          {historical && <Link to="/" className={`text-xs text-[var(--ws-accent)] hover:underline ${focusRing}`}>Show the latest run</Link>}
        </div>
        <StalenessBanner freshness={freshness} />

        {isLoading && <LoadingSpinner text="Loading screening data…" />}

        {(rankingsError || screeningError) && !isLoading && (
          <ErrorMessage
            message={screeningError ?? 'Failed to load screening results. Is the backend running?'}
          />
        )}

        {rankings && !isLoading && (
          <>
            <RunSummaryCards
              summary={buildSummary(rankings)}
              rsRatings={rankings.items
                .map((i) => i.rs_rating)
                .filter((r): r is number => r !== null)}
            />

            {rankings.items.length === 0 ? (
              <EmptyState
                message={`No stocks currently satisfy the ${strategyName} methodology. This is expected behavior, not an error — Momentum25 never lowers its screening bar to populate a list. Check back after the next session, or try a different strategy.`}
              />
            ) : (
              <>
                <div className="border-t border-[var(--ws-line)] pt-2">
                  <ScreenerToolbar screen={screen} rows={rankings.items} matches={matches.length} />
                </div>
                <MomentumTable
                  items={matches}
                  onSymbolClick={handleSymbolClick}
                  selectedSymbol={selected}
                  title="Ranked Universe"
                  visibleColumns={COLUMN_SETS[screen.columnSet]}
                  dense
                />
              </>
            )}
          </>
        )}

        {!isLoading && !rankings && !rankingsError && (
          <div>
            <EmptyState message="No completed screening run for this strategy version yet. Import authorized EOD and benchmark CSV data from the CLI (see README), then run screening. Wickstreet does not download exchange data by default." />
            <div className="flex justify-center pb-4">
              <button
                type="button"
                onClick={() => refreshMutation.mutate()}
                disabled={isRefreshing}
                className={`px-3 py-1.5 rounded-md bg-[var(--ws-accent)] text-white text-xs font-medium disabled:opacity-50 ${focusRing}`}
              >
                {isScreening ? 'Screening…' : 'Run screening now'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
