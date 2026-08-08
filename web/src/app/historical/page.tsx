'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRuns, getRankings, historicalScreen } from '@/lib/api-client';
import { Card, MetricCard, Badge, LoadingSpinner, ErrorMessage, PageHeader, EmptyState } from '@/components/shared/Card';
import MomentumTable from '@/components/dashboard/MomentumTable';
import type { RunDTO } from '@/lib/types';
import { focusRing } from '@/lib/theme';

export default function HistoricalReplayPage() {
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayError, setReplayError] = useState<string | null>(null);
  const [replayResult, setReplayResult] = useState<{ run_id: number; total_passed: number; total_evaluated: number } | null>(null);

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['runs', 'completed'],
    queryFn: () => getRuns('completed', 100, 0),
  });

  const { data: rankings, isLoading: rankingsLoading } = useQuery({
    queryKey: ['rankings', selectedRunId],
    queryFn: () => getRankings(selectedRunId!, 100, 0),
    enabled: selectedRunId !== null,
  });

  const runs = runsData?.items ?? [];
  const uniqueDates = Array.from(new Set(runs.map((r) => r.run_date))).sort().reverse();

  const handleReplay = async () => {
    if (!selectedDate) return;
    setIsReplaying(true);
    setReplayError(null);
    try {
      const result = await historicalScreen({
        strategy_name: 'minervini_trend_template',
        as_of_date: selectedDate,
        symbol_filter: null,
      });
      setReplayResult({
        run_id: result.run_id,
        total_passed: result.total_passed,
        total_evaluated: result.total_evaluated,
      });
      setSelectedRunId(result.run_id);
    } catch (err) {
      setReplayError(err instanceof Error ? err.message : 'Replay failed');
    } finally {
      setIsReplaying(false);
    }
  };

  const selectDate = (date: string) => {
    setSelectedDate(date);
    const run = runs.find((r) => r.run_date === date);
    if (run) setSelectedRunId(run.id);
  };

  return (
    <div className="min-h-screen bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Historical Replay"
        subtitle="Replay the screening engine for any past trading date — no future data leakage"
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Controls */}
        <Card title="Replay Controls">
          <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-end gap-4">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Select Date
              </label>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                max={new Date().toISOString().slice(0, 10)}
                className={`w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm ${focusRing}`}
              />
            </div>

            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Or Select Existing Run
              </label>
              <select
                value={selectedRunId ?? ''}
                onChange={(e) => setSelectedRunId(e.target.value ? Number(e.target.value) : null)}
                className={`w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm ${focusRing}`}
              >
                <option value="">— Select a run —</option>
                {runs.slice(0, 50).map((run) => (
                  <option key={run.id} value={run.id}>
                    #{run.id} — {run.run_date} ({run.strategy})
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={handleReplay}
              disabled={!selectedDate || isReplaying}
              className={`px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${focusRing}`}
            >
              {isReplaying ? 'Replaying…' : 'Replay Date'}
            </button>
          </div>
          {replayError && <div className="mt-3 text-sm text-rose-600 dark:text-rose-400">{replayError}</div>}
        </Card>

        {/* Replay Result */}
        {replayResult && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <MetricCard label="Run ID" value={`#${replayResult.run_id}`} />
            <MetricCard label="Evaluated" value={String(replayResult.total_evaluated)} />
            <MetricCard label="Passed" value={String(replayResult.total_passed)} color="text-emerald-400" />
          </div>
        )}

        {/* Available Dates */}
        <Card title="Available Historical Runs" subtitle={`${uniqueDates.length} unique dates`}>
          {uniqueDates.length === 0 ? (
            <EmptyState message="No completed runs available to replay." />
          ) : (
            <div className="flex flex-wrap gap-2">
              {uniqueDates.slice(0, 30).map((date) => (
                <button
                  key={date}
                  type="button"
                  onClick={() => selectDate(date)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                    selectedDate === date
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:border-indigo-400 dark:hover:border-indigo-600'
                  } ${focusRing}`}
                >
                  {date}
                </button>
              ))}
            </div>
          )}
        </Card>

        {/* Rankings Table */}
        {rankingsLoading && <LoadingSpinner text="Loading rankings…" />}
        {rankings && (
          <Card
            title={`Rankings`}
            subtitle={`Run #${rankings.run?.id ?? 'N/A'} — ${rankings.run?.run_date ?? ''}`}
          >
            <MomentumTable items={rankings.items} title={`${rankings.items.length} stocks`} />
          </Card>
        )}
        {!rankingsLoading && !rankings && (
          <EmptyState message="Select a date or run to view historical rankings." />
        )}
      </div>
    </div>
  );
}
