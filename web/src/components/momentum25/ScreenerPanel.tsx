/**
 * The Stock Screener embedded in /chart's bottom panel (plan 2026-10-19,
 * step 6). It reads the same run and rankings queries as the Screener route,
 * and a row click loads only the active chart.
 */

import { useQuery } from '@tanstack/react-query';
import MomentumTable from '@/components/dashboard/MomentumTable';
import { ProvenanceLine, useLatestRun, useRunRankings } from '@/components/momentum25/run';
import { applyFilters, COLUMN_SETS, ScreenerToolbar, useScreen } from '@/components/momentum25/screener';
import { getRun } from '@/lib/api-client';
import type { ReplayState } from '@/lib/replay';

export function ScreenerPanel({ strategy, configHash, symbol, replay, onOpenSymbol }: { strategy: string; configHash?: string; symbol: string; replay?: ReplayState; onOpenSymbol: (symbol: string) => void }) {
  // Bar replay screens the newest run on or before its date, never a later one.
  const latest = useLatestRun(strategy, configHash);
  const pinned = useQuery({ queryKey: ['run', replay?.runId], queryFn: () => getRun(replay!.runId!), enabled: !!replay?.runId });
  const run = replay ? { data: replay.runId === null ? null : pinned.data } : latest;
  const runId = run.data?.id;
  const rankings = useRunRankings(runId);
  const screen = useScreen();
  const rows = rankings.data?.items ?? [];
  const matches = applyFilters(rows, screen.filters);

  return (
    <div className="space-y-2 p-2 text-xs">
      <ProvenanceLine strategy={strategy} run={run.data} label={replay ? `Replay — newest run on or before ${replay.date}` : undefined} />
      <ScreenerToolbar screen={screen} rows={rows} matches={matches.length} />
      {rankings.isLoading && <p className="text-slate-500">Loading the run…</p>}
      {run.data === null && <p className="text-slate-500">{replay ? `No ${strategy} run is dated on or before ${replay.date}.` : `No completed screening run for ${strategy} yet.`}</p>}
      {rows.length > 0 && <MomentumTable items={matches} onSymbolClick={onOpenSymbol} selectedSymbol={symbol} visibleColumns={COLUMN_SETS[screen.columnSet]} />}
    </div>
  );
}
