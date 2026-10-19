/**
 * The Stock Screener embedded in /chart's bottom panel (plan 2026-10-19,
 * step 6). It reads the same run and rankings queries as the Screener route,
 * and a row click loads only the active chart.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import MomentumTable from '@/components/dashboard/MomentumTable';
import { ProvenanceLine, useLatestRun } from '@/components/momentum25/run';
import { applyFilters, COLUMN_SETS, ColumnSetTabs, FilterPills, type ColumnSet, type ScreenerFilters } from '@/components/momentum25/screener';
import { getRankings } from '@/lib/api-client';

export function ScreenerPanel({ strategy, symbol, onOpenSymbol }: { strategy: string; symbol: string; onOpenSymbol: (symbol: string) => void }) {
  const run = useLatestRun(strategy);
  const runId = run.data?.id;
  const rankings = useQuery({
    queryKey: ['rankings', runId],
    queryFn: () => getRankings(runId!, 100, 0),
    enabled: runId !== undefined,
  });
  const [columnSet, setColumnSet] = useState<ColumnSet>('Overview');
  const [filters, setFilters] = useState<ScreenerFilters>({});
  const rows = rankings.data?.items ?? [];

  return (
    <div className="space-y-2 p-2 text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <ColumnSetTabs value={columnSet} onChange={setColumnSet} />
        <ProvenanceLine strategy={strategy} run={run.data} />
      </div>
      <FilterPills rows={rows} value={filters} onChange={setFilters} />
      {rankings.isLoading && <p className="text-slate-500">Loading the run…</p>}
      {run.data === null && <p className="text-slate-500">No completed screening run for {strategy} yet.</p>}
      {rows.length > 0 && <MomentumTable items={applyFilters(rows, filters)} onSymbolClick={onOpenSymbol} selectedSymbol={symbol} visibleColumns={COLUMN_SETS[columnSet]} />}
    </div>
  );
}
