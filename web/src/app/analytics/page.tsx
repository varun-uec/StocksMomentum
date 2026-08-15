'use client';

import { useQuery } from '@tanstack/react-query';
import { getRuns, evaluateStrategy, getContributionAnalysis } from '@/lib/api-client';
import { Card, MetricCard, LoadingSpinner, PageHeader, EmptyState } from '@/components/shared/Card';
import { ScoreSeriesDisclaimer } from '@/components/learn/MethodologyNote';
import { useStrategy } from '@/app/strategy-context';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend } from 'recharts';
import { useChartColors } from '@/lib/useChartColors';
import { chartColorList, chartPalette } from '@/lib/theme';

export default function ResearchAnalyticsPage() {
  const chartColors = useChartColors();
  const { strategyName: selectedStrategy } = useStrategy();

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['runs', 'all'],
    queryFn: () => getRuns(undefined, 200, 0),
  });

  const { data: evaluation, isLoading: evalLoading } = useQuery({
    queryKey: ['strategy-evaluation', selectedStrategy],
    queryFn: () => evaluateStrategy(selectedStrategy, 100),
    enabled: !!selectedStrategy,
  });

  const { data: contribution, isLoading: contribLoading } = useQuery({
    queryKey: ['contribution', selectedStrategy],
    queryFn: () => getContributionAnalysis(selectedStrategy, 50),
    enabled: !!selectedStrategy,
  });

  const runs = runsData?.items ?? [];

  const freqByMonth: Record<string, number> = {};
  runs.forEach((r) => {
    const month = r.run_date.slice(0, 7);
    freqByMonth[month] = (freqByMonth[month] || 0) + 1;
  });
  const freqChartData = Object.entries(freqByMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, count]) => ({ month, count }));

  const statusCounts: Record<string, number> = {};
  runs.forEach((r) => {
    statusCounts[r.status] = (statusCounts[r.status] || 0) + 1;
  });
  const statusChartData = Object.entries(statusCounts).map(([name, value]) => ({ name, value }));

  const passRateData = (evaluation?.run_summaries ?? [])
    .map((r) => ({
      date: r.run_date.slice(0, 10),
      passRate: r.total_evaluated > 0 ? parseFloat(((r.total_passed / r.total_evaluated) * 100).toFixed(1)) : 0,
      evaluated: r.total_evaluated,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));

  const enginePieData = (contribution?.engine_stats ?? []).map((e) => ({
    name: e.engine_name,
    value: parseFloat(e.total_importance),
  }));

  const rulePassData = (contribution?.top_rules ?? []).slice(0, 15).map((r) => ({
    name: r.rule_id,
    passRate: parseFloat(r.pass_rate) * 100,
    importance: parseFloat(r.importance_score),
  }));

  const isLoading = runsLoading || evalLoading || contribLoading;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Research Analytics"
        subtitle="Visualize screening frequency, win rates, drawdowns, and rule contributions"
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {isLoading && <LoadingSpinner text="Loading analytics…" />}

        {!isLoading && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="Total Runs" value={String(runs.length)} />
              <MetricCard label="Completed Runs" value={String(statusCounts.COMPLETED ?? 0)} color="text-emerald-400" />
              <MetricCard label="Failed Runs" value={String(statusCounts.FAILED ?? 0)} color="text-rose-400" />
              <MetricCard
                label="Avg Pass Rate"
                value={
                  passRateData.length > 0
                    ? `${(passRateData.reduce((s, d) => s + d.passRate, 0) / passRateData.length).toFixed(1)}%`
                    : '—'
                }
                color="text-emerald-400"
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card title="Screening Frequency" subtitle="Runs per month">
                {freqChartData.length > 0 ? (
                  <div role="img" aria-label="Screening Frequency chart" className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={freqChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                        <XAxis dataKey="month" tick={{ fontSize: 10, fill: chartColors.tick }} />
                        <YAxis tick={{ fontSize: 10, fill: chartColors.tick }} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: chartColors.tooltipBg,
                            border: `1px solid ${chartColors.tooltipBorder}`,
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        <Bar dataKey="count" name="Runs" fill={chartPalette.info} radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <EmptyState message="No run data available" />
                )}
              </Card>

              <Card title="Run Status Distribution">
                {statusChartData.length > 0 ? (
                  <div role="img" aria-label="Run Status Distribution chart" className="h-64 flex items-center justify-center">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={statusChartData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          outerRadius={80}
                          label={({ name, value }) => `${name}: ${value}`}
                        >
                          {statusChartData.map((_, idx) => (
                            <Cell key={idx} fill={chartColorList[idx % chartColorList.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            backgroundColor: chartColors.tooltipBg,
                            border: `1px solid ${chartColors.tooltipBorder}`,
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px' }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <EmptyState message="No run data available" />
                )}
              </Card>

              <Card title="Pass Rate Over Time" subtitle="Historical screening pass rates">
                {passRateData.length > 0 ? (
                  <div role="img" aria-label="Pass Rate Over Time chart" className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={passRateData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: chartColors.tick }} angle={-45} textAnchor="end" height={60} />
                        <YAxis tick={{ fontSize: 10, fill: chartColors.tick }} domain={[0, 100]} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: chartColors.tooltipBg,
                            border: `1px solid ${chartColors.tooltipBorder}`,
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        <Line type="monotone" dataKey="passRate" stroke={chartPalette.success} name="Pass Rate %" dot={false} strokeWidth={2} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <EmptyState message="No evaluation data available" />
                )}
              </Card>

              <Card title="Engine Contribution Share" subtitle="Total importance by engine">
                {enginePieData.length > 0 ? (
                  <div role="img" aria-label="Engine Contribution Share chart" className="h-64 flex items-center justify-center">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={enginePieData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          outerRadius={80}
                          label={({ name, value }) => `${name}: ${value.toFixed(2)}`}
                        >
                          {enginePieData.map((_, idx) => (
                            <Cell key={idx} fill={chartColorList[idx % chartColorList.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            backgroundColor: chartColors.tooltipBg,
                            border: `1px solid ${chartColors.tooltipBorder}`,
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px' }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <EmptyState message="No contribution data available" />
                )}
              </Card>

              <Card title="Rule Pass Rates" subtitle="Top 15 rules by pass rate">
                {rulePassData.length > 0 ? (
                  <div role="img" aria-label="Rule Pass Rates chart" className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={rulePassData} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                        <XAxis type="number" tick={{ fontSize: 10, fill: chartColors.tick }} domain={[0, 100]} />
                        <YAxis dataKey="name" type="category" tick={{ fontSize: 9, fill: chartColors.tick }} width={130} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: chartColors.tooltipBg,
                            border: `1px solid ${chartColors.tooltipBorder}`,
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        <Bar dataKey="passRate" name="Pass Rate %" radius={[0, 4, 4, 0]}>
                          {rulePassData.map((_, idx) => (
                            <Cell key={idx} fill={chartColorList[idx % chartColorList.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <EmptyState message="No contribution data available" />
                )}
              </Card>

              <Card title="Score Statistics" subtitle="Momentum & Buy Setup scores">
                {evaluation?.performance ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-4">
                      <StatBox label="Momentum Volatility" value={evaluation.performance.momentum_score_volatility} />
                      <StatBox label="Buy Setup Volatility" value={evaluation.performance.buy_setup_score_volatility} />
                      <StatBox
                        label="Max Score Drawdown"
                        value={evaluation.performance.max_momentum_score_drawdown}
                      />
                      <StatBox
                        label="Score Gain/Loss Ratio"
                        value={evaluation.performance.momentum_score_gain_loss_ratio}
                      />
                      <StatBox label="Score Stability" value={evaluation.performance.momentum_score_stability} />
                      <StatBox
                        label="Score Downside Stability"
                        value={evaluation.performance.momentum_score_downside_stability}
                      />
                    </div>
                    <ScoreSeriesDisclaimer />
                  </div>
                ) : (
                  <EmptyState message="No evaluation data available" />
                )}
              </Card>

              <Card title="Ranking Stability" subtitle="Top rank consistency across runs">
                {evaluation?.performance ? (
                  <div className="space-y-4">
                    <StatBox
                      label="Top Rank Stability"
                      value={`${(parseFloat(evaluation.performance.avg_top_rank_stability) * 100).toFixed(1)}%`}
                      description="Measures how consistently top-ranked stocks stay in the top ranks"
                    />
                    <div className="grid grid-cols-2 gap-4">
                      <StatBox label="Max Score" value={evaluation.performance.max_momentum_score} accent="emerald" />
                      <StatBox label="Min Score" value={evaluation.performance.min_momentum_score} />
                    </div>
                  </div>
                ) : (
                  <EmptyState message="No evaluation data available" />
                )}
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  description,
  accent,
}: {
  label: string;
  value: string;
  description?: string;
  accent?: 'emerald' | 'rose' | 'amber' | 'slate';
}) {
  const colorMap = {
    emerald: 'text-emerald-600 dark:text-emerald-400',
    rose: 'text-rose-600 dark:text-rose-400',
    amber: 'text-amber-600 dark:text-amber-400',
    slate: 'text-slate-800 dark:text-slate-200',
  };
  return (
    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700/40">
      <div className="text-xs text-slate-500 uppercase">{label}</div>
      <div className={`text-lg font-bold tabular-nums ${accent ? colorMap[accent] : 'text-slate-800 dark:text-slate-200'}`}>{value}</div>
      {description && <div className="text-xs text-slate-500 mt-1 leading-snug">{description}</div>}
    </div>
  );
}
