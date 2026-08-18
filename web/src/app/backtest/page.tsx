'use client';

import { useState } from 'react';
import { runWalkForwardBacktest } from '@/lib/api-client';
import { Card, MetricCard, LoadingSpinner, ErrorMessage, PageHeader, EmptyState } from '@/components/shared/Card';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useChartColors } from '@/lib/useChartColors';
import type { BacktestResponse } from '@/lib/types';
import { focusRing, chartPalette } from '@/lib/theme';

const inputClass = 'px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm';

function formatPercent(value: string): string {
  return `${(parseFloat(value) * 100).toFixed(2)}%`;
}

export default function BacktestPage() {
  const chartColors = useChartColors();
  const [start, setStart] = useState('2019-01-01');
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const [initialCapital, setInitialCapital] = useState('1000000');
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setIsRunning(true);
    setError(null);
    setResult(null);
    try {
      setResult(await runWalkForwardBacktest({ start, end, initial_capital: initialCapital }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backtest failed');
    } finally {
      setIsRunning(false);
    }
  };

  const equityCurve = (result?.rebalances ?? []).map((r) => ({
    date: r.fill_date,
    nav: parseFloat(r.nav_pre_cost),
  }));

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Walk-Forward Backtest"
        subtitle="3/6/12M blended momentum, monthly rebalance, N=30 with a 45-rank buffer"
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <Card title="Backtest Configuration">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label htmlFor="bt-start" className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Start Date</label>
              <input id="bt-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className={`${inputClass} ${focusRing}`} />
            </div>
            <div>
              <label htmlFor="bt-end" className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">End Date</label>
              <input id="bt-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={`${inputClass} ${focusRing}`} />
            </div>
            <div>
              <label htmlFor="bt-capital" className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Initial Capital (INR)</label>
              <input id="bt-capital" type="number" min="1" step="1" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)} className={`${inputClass} w-40 ${focusRing}`} />
            </div>
            <button
              type="button"
              onClick={handleRun}
              disabled={isRunning}
              className={`px-6 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${focusRing}`}
            >
              {isRunning ? 'Running Backtest…' : 'Run Backtest'}
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-3">A multi-year range reads several years of prices from the database and can take a few seconds.</p>
        </Card>

        {isRunning && <LoadingSpinner />}
        {error && <ErrorMessage message={error} />}

        {result && (
          <>
            <div
              role="note"
              className="rounded-lg border border-amber-300 dark:border-amber-700/60 bg-amber-50 dark:bg-amber-900/20 px-4 py-3"
            >
              <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wider mb-1">
                Known data caveat — read before using these numbers
              </p>
              <p className="text-sm text-amber-800 dark:text-amber-200">{result.survivorship_warning}</p>
            </div>

            <Card title="Result" subtitle={`${result.start} to ${result.end}`}>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <MetricCard label="Final NAV" value={parseFloat(result.final_nav).toLocaleString('en-IN', { maximumFractionDigits: 0 })} />
                <MetricCard
                  label="Total Return"
                  value={formatPercent(result.total_return)}
                  color={parseFloat(result.total_return) >= 0 ? 'text-emerald-400' : 'text-rose-400'}
                />
                {/* The benchmark number never appears without its label. */}
                <MetricCard
                  label={result.benchmark_return === null ? 'Benchmark' : `Benchmark — ${result.benchmark_label ?? 'UNLABELED BENCHMARK'}`}
                  value={result.benchmark_return === null ? 'Not available' : formatPercent(result.benchmark_return)}
                />
                <MetricCard label="Rebalances" value={String(result.rebalance_count)} />
                <MetricCard label="Trades" value={String(result.trade_count)} />
              </div>
            </Card>

            {equityCurve.length > 0 && (
              <Card title="Equity Curve" subtitle="NAV before costs, at each rebalance">
                <div role="img" aria-label="Equity curve chart" className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={equityCurve}>
                      <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: chartColors.tick }} minTickGap={24} />
                      <YAxis tick={{ fontSize: 10, fill: chartColors.tick }} domain={['auto', 'auto']} width={80} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: chartColors.tooltipBg,
                          border: `1px solid ${chartColors.tooltipBorder}`,
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <Line type="monotone" dataKey="nav" name="NAV" stroke={chartPalette.info} dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            <Card title="Rebalance Log">
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                      <th scope="col" className="text-left px-3 py-3">Decision Date</th>
                      <th scope="col" className="text-left px-3 py-3">Fill Date</th>
                      <th scope="col" className="text-right px-3 py-3">Universe</th>
                      <th scope="col" className="text-right px-3 py-3">Eligible</th>
                      <th scope="col" className="text-right px-3 py-3">Holdings</th>
                      <th scope="col" className="text-right px-3 py-3">Trades</th>
                      <th scope="col" className="text-right px-3 py-3">Cost</th>
                      <th scope="col" className="text-right px-3 py-3">NAV (pre-cost)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40">
                    {result.rebalances.map((r) => (
                      <tr key={r.fill_date} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                        <td className="px-3 py-3 text-slate-700 dark:text-slate-300">{r.decision_date}</td>
                        <td className="px-3 py-3 text-slate-700 dark:text-slate-300">{r.fill_date}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{r.universe_size}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{r.eligible_count}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{r.selected.length}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{r.trade_count}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{parseFloat(r.total_cost).toFixed(2)}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{parseFloat(r.nav_pre_cost).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}

        {!result && !isRunning && !error && (
          <EmptyState message="Pick a date range above and click 'Run Backtest' to see results." />
        )}
      </div>
    </div>
  );
}
