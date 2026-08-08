'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listStrategies, evaluateStrategy, getContributionAnalysis, compareStrategies } from '@/lib/api-client';
import { Card, MetricCard, Badge, StatusDot, LoadingSpinner, ErrorMessage, PageHeader, EmptyState } from '@/components/shared/Card';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, Legend } from 'recharts';
import { useChartColors } from '@/lib/useChartColors';
import { focusRing, chartPalette, chartColorList } from '@/lib/theme';

export default function StrategyResearchPage() {
  const chartColors = useChartColors();
  const [selectedStrategy, setSelectedStrategy] = useState('minervini_trend_template');
  const [compareA, setCompareA] = useState('minervini_trend_template');
  const [compareB, setCompareB] = useState('minervini_trend_template');

  const { data: strategies, isLoading: strategiesLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: listStrategies,
  });

  const { data: evaluation, isLoading: evalLoading } = useQuery({
    queryKey: ['strategy-evaluation', selectedStrategy],
    queryFn: () => evaluateStrategy(selectedStrategy, 50),
    enabled: !!selectedStrategy,
  });

  const { data: contribution, isLoading: contribLoading } = useQuery({
    queryKey: ['contribution', selectedStrategy],
    queryFn: () => getContributionAnalysis(selectedStrategy, 20),
    enabled: !!selectedStrategy,
  });

  const { data: comparison, isLoading: compLoading } = useQuery({
    queryKey: ['strategy-comparison', compareA, compareB],
    queryFn: () => compareStrategies(compareA, compareB, 20),
    enabled: compareA !== compareB,
  });

  const perf = evaluation?.performance;

  const engineChartData =
    contribution?.engine_stats.map((e) => ({
      name: e.engine_name,
      passRate: parseFloat(e.avg_pass_rate) * 100,
      importance: parseFloat(e.avg_importance),
    })) ?? [];

  const topRulesData =
    contribution?.top_rules.slice(0, 10).map((r) => ({
      name: r.rule_id,
      importance: parseFloat(r.importance_score),
    })) ?? [];

  return (
    <div className="min-h-screen bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
      <PageHeader title="Strategy Research" subtitle="Evaluate, compare, and analyze screening strategies" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Strategy Selector */}
        <Card title="Select Strategy">
          {strategiesLoading && <LoadingSpinner text="Loading strategies…" />}
          {!strategiesLoading && strategies && strategies.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {strategies.map((s) => (
                <button
                  key={s.name}
                  type="button"
                  onClick={() => setSelectedStrategy(s.name)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                    selectedStrategy === s.name
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:border-indigo-400 dark:hover:border-indigo-600'
                  } ${focusRing}`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          )}
          {!strategiesLoading && (!strategies || strategies.length === 0) && (
            <EmptyState message="No strategies available." />
          )}
        </Card>

        {/* Performance Metrics */}
        {evalLoading && <LoadingSpinner text="Evaluating strategy…" />}
        {perf && (
          <>
            <Card title="Performance Metrics" subtitle={`${perf.run_count} runs analyzed`}>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                <MetricCard label="Avg Momentum" value={perf.avg_momentum_score} />
                <MetricCard label="Median Momentum" value={perf.median_momentum_score} />
                <MetricCard label="Avg Buy Setup" value={perf.avg_buy_setup_score} />
                <MetricCard label="Volatility" value={perf.momentum_score_volatility} />
                <MetricCard label="Max Drawdown" value={`${perf.max_drawdown_pct}%`} color="text-rose-400" />
                <MetricCard label="Avg Pass Rate" value={`${(parseFloat(perf.avg_pass_rate) * 100).toFixed(1)}%`} color="text-emerald-400" />
                <MetricCard label="Sharpe Ratio" value={perf.sharpe_ratio} color={parseFloat(perf.sharpe_ratio) >= 1 ? 'text-emerald-400' : 'text-amber-400'} />
                <MetricCard label="Sortino Ratio" value={perf.sortino_ratio} />
                <MetricCard label="Profit Factor" value={perf.profit_factor} color={parseFloat(perf.profit_factor) >= 1.5 ? 'text-emerald-400' : 'text-slate-800 dark:text-slate-200'} />
                <MetricCard label="Rank Stability" value={`${(parseFloat(perf.avg_top_rank_stability) * 100).toFixed(0)}%`} />
                <MetricCard label="Max Score" value={perf.max_momentum_score} color="text-emerald-400" />
                <MetricCard label="Min Score" value={perf.min_momentum_score} />
              </div>
            </Card>

            <Card title="Recent Runs" subtitle={`${evaluation?.run_summaries.length ?? 0} runs`}>
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                      <th className="text-left px-3 py-3">Run ID</th>
                      <th className="text-left px-3 py-3">Date</th>
                      <th className="text-right px-3 py-3">Evaluated</th>
                      <th className="text-right px-3 py-3">Passed</th>
                      <th className="text-right px-3 py-3">Failed</th>
                      <th className="text-right px-3 py-3">Pass Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40">
                    {evaluation?.run_summaries.slice(0, 20).map((run) => (
                      <tr key={run.run_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                        <td className="px-3 py-3 text-slate-700 dark:text-slate-300">#{run.run_id}</td>
                        <td className="px-3 py-3 text-slate-700 dark:text-slate-300">{run.run_date}</td>
                        <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-300 tabular-nums">{run.total_evaluated}</td>
                        <td className="px-3 py-3 text-right text-emerald-600 dark:text-emerald-400 tabular-nums">{run.total_passed}</td>
                        <td className="px-3 py-3 text-right text-rose-600 dark:text-rose-400 tabular-nums">{run.total_failed}</td>
                        <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-300 tabular-nums">
                          {run.total_evaluated > 0 ? `${((run.total_passed / run.total_evaluated) * 100).toFixed(1)}%` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}

        {/* Contribution Analysis */}
        {contribLoading && <LoadingSpinner text="Analyzing contributions…" />}
        {contribution && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Engine Contributions" subtitle="Pass rate & importance by engine">
              {engineChartData.length > 1 && (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={engineChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: chartColors.tick }} />
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
                      <Bar dataKey="passRate" name="Pass Rate %" fill={chartPalette.info} radius={[4, 4, 0, 0]} />
                      <Bar dataKey="importance" name="Importance" fill={chartPalette.secondary} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="mt-3 space-y-2">
                {contribution.engine_stats.map((engine) => (
                  <div key={engine.engine_name} className="flex items-center justify-between text-xs">
                    <span className="text-slate-700 dark:text-slate-300 capitalize">{engine.engine_name.replace(/_/g, ' ')}</span>
                    <div className="flex items-center gap-4">
                      <span className="text-slate-500 tabular-nums">{engine.rule_count} rules</span>
                      <span className="text-emerald-600 dark:text-emerald-400 tabular-nums">{(parseFloat(engine.avg_pass_rate) * 100).toFixed(0)}% pass</span>
                      <span className="text-indigo-600 dark:text-indigo-400 tabular-nums">{parseFloat(engine.avg_importance).toFixed(2)} importance</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card title="Top Rules by Importance" subtitle="Most impactful rules">
              {topRulesData.length > 0 && (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={topRulesData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                      <XAxis type="number" tick={{ fontSize: 10, fill: chartColors.tick }} />
                      <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: chartColors.tick }} width={120} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: chartColors.tooltipBg,
                          border: `1px solid ${chartColors.tooltipBorder}`,
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <Bar dataKey="importance" name="Importance" radius={[0, 4, 4, 0]}>
                        {topRulesData.map((_, idx) => (
                          <Cell key={idx} fill={chartColorList[idx % chartColorList.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>

            {contribution.redundant_rules.length > 0 && (
              <Card title="Redundant Rules" badge={{ text: `${contribution.redundant_rules.length}`, color: 'bg-amber-900/50 text-amber-300' }}>
                <div className="space-y-1">
                  {contribution.redundant_rules.map((rule) => (
                    <div key={rule.rule_id} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                      <StatusDot passed />
                      <span>{rule.rule_id}</span>
                      <span className="text-slate-400 dark:text-slate-600">({rule.engine_id})</span>
                      <span className="text-slate-600 ml-auto">100% pass rate</span>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {contribution.bottom_rules.length > 0 && (
              <Card title="Least Impactful Rules" badge={{ text: `${contribution.bottom_rules.length}`, color: 'bg-rose-900/50 text-rose-300' }}>
                <div className="space-y-1">
                  {contribution.bottom_rules.slice(0, 10).map((rule) => (
                    <div key={rule.rule_id} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                      <StatusDot passed={rule.pass_rate === '1'} />
                      <span>{rule.rule_id}</span>
                      <span className="text-slate-400 dark:text-slate-600">({rule.engine_id})</span>
                      <span className="text-slate-600 ml-auto">imp: {parseFloat(rule.importance_score).toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>
        )}

        {/* Strategy Comparison */}
        <Card title="Strategy Comparison">
          <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-end gap-4 mb-4">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Strategy A (Baseline)</label>
              <select
                value={compareA}
                onChange={(e) => setCompareA(e.target.value)}
                className={`w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm ${focusRing}`}
              >
                {(strategies ?? []).map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Strategy B (Comparison)</label>
              <select
                value={compareB}
                onChange={(e) => setCompareB(e.target.value)}
                className={`w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm ${focusRing}`}
              >
                {(strategies ?? []).map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {compLoading && <LoadingSpinner text="Comparing strategies…" />}
          {compareA === compareB && !compLoading && (
            <EmptyState message="Select two different strategies to compare." />
          )}
          {comparison && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard label="Total Comparisons" value={String(comparison.total_comparisons)} />
                <MetricCard label="Agreement Rate" value={`${(parseFloat(comparison.agreement_rate) * 100).toFixed(1)}%`} color="text-emerald-400" />
                <MetricCard label={`${comparison.strategy_a_name} Wins`} value={String(comparison.a_wins)} color="text-cyan-400" />
                <MetricCard label={`${comparison.strategy_b_name} Wins`} value={String(comparison.b_wins)} color="text-purple-400" />
              </div>

              {comparison.comparisons.length > 0 && (
                <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60 max-h-80">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                        <th className="text-left px-3 py-3">Symbol</th>
                        <th className="text-right px-3 py-3">Rank A</th>
                        <th className="text-right px-3 py-3">Rank B</th>
                        <th className="text-right px-3 py-3">Momentum A</th>
                        <th className="text-right px-3 py-3">Momentum B</th>
                        <th className="text-center px-3 py-3">Agreement</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40">
                      {comparison.comparisons.slice(0, 50).map((c) => (
                        <tr key={c.security_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="px-3 py-3 text-slate-800 dark:text-slate-200 font-medium">{c.symbol}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{c.rank_a ?? '—'}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{c.rank_b ?? '—'}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{c.momentum_a ?? '—'}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{c.momentum_b ?? '—'}</td>
                          <td className="px-3 py-3 text-center">
                            <StatusDot passed={c.agreement} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
