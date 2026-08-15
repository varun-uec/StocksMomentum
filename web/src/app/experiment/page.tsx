'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listStrategies, runExperiment } from '@/lib/api-client';
import { Card, MetricCard, Badge, StatusDot, LoadingSpinner, ErrorMessage, PageHeader, EmptyState } from '@/components/shared/Card';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, Legend } from 'recharts';
import { useChartColors } from '@/lib/useChartColors';
import type { ExperimentResponse, ParameterOverride } from '@/lib/types';
import { focusRing, chartPalette } from '@/lib/theme';

export default function ExperimentLaboratoryPage() {
  const chartColors = useChartColors();
  const [baseStrategy, setBaseStrategy] = useState('minervini_trend_template');
  const [overrides, setOverrides] = useState<ParameterOverride[]>([{ parameter_path: '', value: '' }]);
  const [runDates, setRunDates] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<ExperimentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => listStrategies(),
  });

  const addOverride = () => {
    setOverrides([...overrides, { parameter_path: '', value: '' }]);
  };

  const updateOverride = (idx: number, field: keyof ParameterOverride, value: string) => {
    const updated = overrides.map((o, i) => (i === idx ? { ...o, [field]: value } : o));
    setOverrides(updated);
  };

  const removeOverride = (idx: number) => {
    setOverrides(overrides.filter((_, i) => i !== idx));
  };

  const handleRun = async () => {
    setIsRunning(true);
    setError(null);
    setResult(null);
    try {
      const validOverrides = overrides.filter((o) => o.parameter_path && o.value);
      const dates = runDates ? runDates.split(',').map((d) => d.trim()).filter(Boolean) : null;

      const response = await runExperiment({
        base_strategy_name: baseStrategy,
        overrides: validOverrides,
        run_dates: dates,
        symbol_filter: null,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Experiment failed');
    } finally {
      setIsRunning(false);
    }
  };

  const chartData = result
    ? result.base_results.map((b) => {
        const v = result.variant_results.find((vr) => vr.run_date === b.run_date);
        return {
          date: b.run_date.slice(0, 10),
          baseMomentum: parseFloat(b.avg_momentum_score),
          variantMomentum: v ? parseFloat(v.avg_momentum_score) : 0,
          basePassed: b.total_passed,
          variantPassed: v?.total_passed ?? 0,
        };
      })
    : [];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Experiment Laboratory"
        subtitle="Controlled experimentation with rule thresholds, weights, and strategy parameters"
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Experiment Configuration */}
        <Card title="Experiment Configuration">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Base Strategy
              </label>
              <select
                value={baseStrategy}
                onChange={(e) => setBaseStrategy(e.target.value)}
                className={`w-full max-w-xs px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm ${focusRing}`}
              >
                {(strategies ?? []).map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Run Dates (comma-separated, optional — defaults to last 5)
              </label>
              <input
                type="text"
                value={runDates}
                onChange={(e) => setRunDates(e.target.value)}
                placeholder="2026-06-15, 2026-06-16, 2026-06-17"
                className={`w-full max-w-lg px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm placeholder-slate-400 dark:placeholder-slate-500 ${focusRing}`}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Parameter Overrides</label>
                <button
                  type="button"
                  onClick={addOverride}
                  className={`text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors ${focusRing} rounded px-2 py-1`}
                >
                  + Add Override
                </button>
              </div>
              <div className="space-y-2">
                {overrides.map((override, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={override.parameter_path}
                      onChange={(e) => updateOverride(idx, 'parameter_path', e.target.value)}
                      placeholder="engines.trend_template.weight"
                      className={`flex-1 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm placeholder-slate-400 dark:placeholder-slate-500 ${focusRing}`}
                    />
                    <input
                      type="text"
                      value={override.value}
                      onChange={(e) => updateOverride(idx, 'value', e.target.value)}
                      placeholder="1.5"
                      className={`w-24 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm placeholder-slate-400 dark:placeholder-slate-500 ${focusRing}`}
                    />
                    <button
                      type="button"
                      onClick={() => removeOverride(idx)}
                      aria-label="Remove override"
                      className={`p-2 text-rose-500 hover:text-rose-600 dark:hover:text-rose-400 transition-colors ${focusRing} rounded`}
                    >
                      <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                        <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <button
              type="button"
              onClick={handleRun}
              disabled={isRunning}
              className={`px-6 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${focusRing}`}
            >
              {isRunning ? 'Running Experiment…' : 'Run Experiment'}
            </button>
          </div>
        </Card>

        {error && <ErrorMessage message={error} />}

        {result && (
          <>
            <Card title="Experiment Results" subtitle={`${result.variant_label} vs ${result.base_strategy_name}`}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard label="Run Count" value={String(result.run_count)} />
                <MetricCard
                  label="Avg Improvement"
                  value={`${(parseFloat(result.avg_improvement) * 100).toFixed(2)}%`}
                  color={result.is_better ? 'text-emerald-400' : 'text-rose-400'}
                />
                <MetricCard
                  label="Verdict"
                  value={result.is_better ? 'BETTER' : 'WORSE'}
                  color={result.is_better ? 'text-emerald-400' : 'text-rose-400'}
                />
                <MetricCard label="Best Date" value={result.best_run_date ?? '—'} />
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-3">{result.summary}</p>
            </Card>

            {chartData.length > 0 && (
              <Card title="Momentum Score Comparison" subtitle="Base vs Variant">
                <div role="img" aria-label="Momentum Score Comparison chart" className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: chartColors.tick }} />
                      <YAxis tick={{ fontSize: 10, fill: chartColors.tick }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: chartColors.tooltipBg,
                          border: `1px solid ${chartColors.tooltipBorder}`,
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                      <Bar dataKey="baseMomentum" name="Base" fill={chartPalette.info} radius={[4, 4, 0, 0]} />
                      <Bar dataKey="variantMomentum" name="Variant" fill={chartPalette.secondary} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            <Card title="Per-Date Results">
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                      <th scope="col" className="text-left px-3 py-3">Date</th>
                      <th scope="col" className="text-right px-3 py-3">Base Evaluated</th>
                      <th scope="col" className="text-right px-3 py-3">Base Passed</th>
                      <th scope="col" className="text-right px-3 py-3">Base Avg Momentum</th>
                      <th scope="col" className="text-right px-3 py-3">Variant Evaluated</th>
                      <th scope="col" className="text-right px-3 py-3">Variant Passed</th>
                      <th scope="col" className="text-right px-3 py-3">Variant Avg Momentum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40">
                    {result.base_results.map((b) => {
                      const v = result.variant_results.find((vr) => vr.run_date === b.run_date);
                      return (
                        <tr key={b.run_date} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="px-3 py-3 text-slate-700 dark:text-slate-300">{b.run_date}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{b.total_evaluated}</td>
                          <td className="px-3 py-3 text-right tabular-nums text-emerald-600 dark:text-emerald-400">{b.total_passed}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{b.avg_momentum_score}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{v?.total_evaluated ?? '—'}</td>
                          <td className="px-3 py-3 text-right tabular-nums text-emerald-600 dark:text-emerald-400">{v?.total_passed ?? '—'}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{v?.avg_momentum_score ?? '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}

        {!result && !isRunning && !error && (
          <EmptyState message="Configure your experiment above and click 'Run Experiment' to see results." />
        )}
      </div>
    </div>
  );
}
