/**
 * The Stock Screener embedded in /chart's bottom panel (plan 2026-10-19,
 * step 6). It reads the same run and rankings queries as the Screener route,
 * and a row click loads only the active chart.
 */

import MomentumTable from '@/components/dashboard/MomentumTable';
import { ProvenanceLine, useLatestRun, useRunRankings } from '@/components/momentum25/run';
import { applyFilters, COLUMN_SETS, ScreenerToolbar, useScreen } from '@/components/momentum25/screener';

export function ScreenerPanel({ strategy, symbol, onOpenSymbol }: { strategy: string; symbol: string; onOpenSymbol: (symbol: string) => void }) {
  const run = useLatestRun(strategy);
  const runId = run.data?.id;
  const rankings = useRunRankings(runId);
  const screen = useScreen();
  const rows = rankings.data?.items ?? [];
  const matches = applyFilters(rows, screen.filters);

  return (
    <div className="space-y-2 p-2 text-xs">
      <ProvenanceLine strategy={strategy} run={run.data} />
      <ScreenerToolbar screen={screen} rows={rows} matches={matches.length} />
      {rankings.isLoading && <p className="text-slate-500">Loading the run…</p>}
      {run.data === null && <p className="text-slate-500">No completed screening run for {strategy} yet.</p>}
      {rows.length > 0 && <MomentumTable items={matches} onSymbolClick={onOpenSymbol} selectedSymbol={symbol} visibleColumns={COLUMN_SETS[screen.columnSet]} />}
    </div>
  );
}
