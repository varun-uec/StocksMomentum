'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  getResearchDashboard,
  getStrategyScorecard,
  getAlphaAnalysis,
  getRuleEffectiveness,
  getEngineEffectiveness,
  getHistoricalValidation,
  runParameterExperiment,
} from '@/lib/api-client';
import type {
  Measurability,
  ResearchDashboardResponse,
  StrategyScorecard,
  AlphaAnalysisResponse,
  RuleEffectivenessResponse,
  EngineEffectivenessResponse,
  HistoricalValidationResponse,
} from '@/lib/types';
import { Card, LoadingSpinner, ErrorMessage, PageHeader, EmptyState } from '@/components/shared/Card';
import { focusRing } from '@/lib/theme';

const UNMEASURED = '—';

const MEASURABILITY_COPY: Record<string, string> = {
  no_forward_returns:
    'Performance metrics require forward returns, which have not been ingested for this database. Every return-based figure below is shown as \u2014 rather than 0.',
  no_runs: 'No completed screening runs exist for this strategy yet, so there is nothing to measure.',
};

/** A number is either measured or it is not. Never render an unmeasured metric as 0. */
function MeasurabilityNotice({ measurability }: { measurability?: Measurability }) {
  if (!measurability || measurability.forward_returns_available) return null;
  const reason = measurability.reason ?? 'no_forward_returns';
  return (
    <div className="rounded-lg border border-amber-300 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-950/40 px-4 py-3">
      <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">Not yet measurable</p>
      <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
        {MEASURABILITY_COPY[reason] ?? MEASURABILITY_COPY.no_forward_returns}
      </p>
    </div>
  );
}

function fmt(val: string | number | undefined | null, decimals = 4): string {
  if (val === undefined || val === null) return UNMEASURED;
  const n = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(n)) return UNMEASURED;
  return n.toFixed(decimals);
}

function pct(val: string | number | undefined | null): string {
  if (val === undefined || val === null) return UNMEASURED;
  const n = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(n)) return UNMEASURED;
  return `${(n * 100).toFixed(2)}%`;
}

/** Numeric view of a possibly-null metric; NaN keeps every `good`/`bad` test false. */
function num(val: string | number | undefined | null): number {
  if (val === undefined || val === null) return NaN;
  return typeof val === 'string' ? parseFloat(val) : val;
}

/** `null`/`undefined` means "never measured". Colour is suppressed so an
 *  unmeasured metric can never read as a good or bad result. */
function MetricCard({ label, value, good, bad }: { label: string; value: string; good?: boolean; bad?: boolean }) {
  const unmeasured = value === UNMEASURED;
  const color = unmeasured
    ? 'text-slate-400 dark:text-slate-500'
    : good ? 'text-emerald-600 dark:text-emerald-400' : bad ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-slate-100';
  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 border border-slate-200 dark:border-slate-700/50">
      <div className="text-xs font-semibold text-slate-500 mb-1">{label}</div>
      <div className={`text-sm font-semibold font-mono ${color}`}>{value}</div>
    </div>
  );
}

function ScorecardSection({ data }: { data: StrategyScorecard | null }) {
  if (!data) return null;

  return (
    <Card title="Strategy Scorecard" subtitle={`${data.period_label} · ${data.total_trading_days} trading days`}>
      <div className="space-y-6">
        <MeasurabilityNotice measurability={data.measurability} />
        <MetricGroup title="Return Metrics">
          <MetricCard label="CAGR" value={pct(data.cagr)} good={num(data.cagr) > 0} />
          <MetricCard label="Annual Return" value={pct(data.annual_return)} good={num(data.annual_return) > 0} />
          <MetricCard label="Cumulative Return" value={pct(data.cumulative_return)} good={num(data.cumulative_return) > 0} />
          <MetricCard label="Avg Holding Return" value={pct(data.avg_holding_return)} />
          <MetricCard label="Best Return" value={pct(data.best_return)} good />
          <MetricCard label="Worst Return" value={pct(data.worst_return)} bad />
        </MetricGroup>

        <MetricGroup title="Win / Loss">
          <MetricCard label="Win Rate" value={pct(data.win_rate)} good={num(data.win_rate) > 0.5} />
          <MetricCard label="Total Wins" value={data.total_wins === null || data.total_wins === undefined ? UNMEASURED : String(data.total_wins)} good />
          <MetricCard label="Total Losses" value={data.total_losses === null || data.total_losses === undefined ? UNMEASURED : String(data.total_losses)} bad />
          <MetricCard label="Avg Winner" value={pct(data.avg_winner)} good />
          <MetricCard label="Avg Loser" value={pct(data.avg_loser)} bad />
          <MetricCard label="Profit Factor" value={fmt(data.profit_factor, 2)} good={num(data.profit_factor) > 1} />
        </MetricGroup>

        <MetricGroup title="Risk Metrics">
          <MetricCard label="Max Drawdown" value={pct(data.max_drawdown)} bad />
          <MetricCard
            label="Drawdown Duration"
            value={data.max_drawdown_duration === null ? UNMEASURED : `${data.max_drawdown_duration}d`}
            bad={num(data.max_drawdown_duration) > 30}
          />
          <MetricCard label="Volatility" value={pct(data.volatility)} bad={num(data.volatility) > 0.3} />
          <MetricCard label="Downside Vol" value={pct(data.downside_volatility)} />
        </MetricGroup>

        <MetricGroup title="Risk-Adjusted Returns">
          <MetricCard label="Sharpe Ratio" value={fmt(data.sharpe_ratio, 2)} good={num(data.sharpe_ratio) > 1} />
          <MetricCard label="Sortino Ratio" value={fmt(data.sortino_ratio, 2)} good={num(data.sortino_ratio) > 1} />
          <MetricCard label="Calmar Ratio" value={fmt(data.calmar_ratio, 2)} good={num(data.calmar_ratio) > 1} />
          <MetricCard label="Information Ratio" value={fmt(data.information_ratio, 2)} />
        </MetricGroup>

        <MetricGroup title="Market-Relative">
          <MetricCard label="Alpha" value={fmt(data.alpha, 4)} good={num(data.alpha) > 0} />
          <MetricCard label="Beta" value={fmt(data.beta, 2)} />
          <MetricCard label="R-Squared" value={fmt(data.r_squared, 4)} />
        </MetricGroup>

        <MetricGroup title="Screening Quality">
          <MetricCard label="Pass Rate" value={pct(data.avg_pass_rate)} />
          <MetricCard label="Avg Momentum Score" value={fmt(data.avg_momentum_score, 4)} />
          <MetricCard label="Avg Buy Setup" value={fmt(data.avg_buy_setup_score, 4)} />
          <MetricCard label="False Positive Rate" value={pct(data.false_positive_rate)} bad={num(data.false_positive_rate) > 0.1} />
          <MetricCard label="False Negative Rate" value={pct(data.false_negative_rate)} bad={num(data.false_negative_rate) > 0.1} />
        </MetricGroup>
      </div>
    </Card>
  );
}

function MetricGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">{title}</h4>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">{children}</div>
    </div>
  );
}

function AlphaSection({ data }: { data: AlphaAnalysisResponse | null }) {
  if (!data) return null;
  if (data.comparisons.length === 0) {
    return (
      <Card title="Alpha Analysis" subtitle={data.period_label}>
        <MeasurabilityNotice measurability={data.measurability} />
      </Card>
    );
  }

  return (
    <Card title="Alpha Analysis" subtitle={data.period_label}>
      <div className="space-y-4">
        {data.comparisons.map((comp) => (
          <div
            key={comp.benchmark_code}
            className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-4 border border-slate-200 dark:border-slate-700/50"
          >
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">{comp.benchmark_name}</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              <MetricCard label="Alpha" value={fmt(comp.alpha, 4)} good={num(comp.alpha) > 0} />
              <MetricCard label="Strategy Return" value={pct(comp.strategy_return)} good={num(comp.strategy_return) > 0} />
              <MetricCard label="Benchmark Return" value={pct(comp.benchmark_return)} />
              <MetricCard label="Excess Return" value={pct(comp.excess_return)} good={num(comp.excess_return) > 0} />
              <MetricCard label="Strategy CAGR" value={pct(comp.cagr)} good={num(comp.cagr) > 0} />
              <MetricCard label="Benchmark CAGR" value={pct(comp.benchmark_cagr)} />
              <MetricCard label="Relative Perf" value={pct(comp.relative_performance)} good={num(comp.relative_performance) > 0} />
              <MetricCard label="Ann. Return" value={pct(comp.annualized_return)} good={num(comp.annualized_return) > 0} />
            </div>
          </div>
        ))}
        <div className="flex flex-wrap gap-4 text-xs text-slate-500">
          <span>
            Best Alpha: <span className="text-emerald-600 dark:text-emerald-400 font-mono">{fmt(data.best_alpha, 4)}</span>
          </span>
          <span>
            Worst Alpha: <span className="text-rose-600 dark:text-rose-400 font-mono">{fmt(data.worst_alpha, 4)}</span>
          </span>
          <span>
            Avg Alpha: <span className="text-slate-700 dark:text-slate-300 font-mono">{fmt(data.avg_alpha, 4)}</span>
          </span>
        </div>
      </div>
    </Card>
  );
}

function RulesSection({ data }: { data: RuleEffectivenessResponse | null }) {
  if (!data) return null;

  // S6: is_weak / is_redundant / is_high_value are return-derived verdicts. With
  // no forward returns they are null, and a rule must never be added, removed or
  // reweighted on the strength of a null. The panel is withheld, not zero-filled.
  if (!data.measurability.forward_returns_available) {
    return (
      <Card title="Rule Effectiveness" subtitle={`${data.total_runs_analyzed} runs analyzed`}>
        <MeasurabilityNotice measurability={data.measurability} />
        <p className="mt-3 text-xs text-slate-500">{data.summary}</p>
      </Card>
    );
  }

  return (
    <Card title="Rule Effectiveness" subtitle={`${data.total_runs_analyzed} runs analyzed`}>
      <div className="space-y-4">
        {data.high_value_rules.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider mb-2">
              High-Value Rules ({data.high_value_rules.length})
            </h4>
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                    <th className="text-left py-2 px-3">Rule</th>
                    <th className="text-right py-2 px-3">Engine</th>
                    <th className="text-right py-2 px-3">Pass Rate</th>
                    <th className="text-right py-2 px-3">Return Delta</th>
                    <th className="text-right py-2 px-3">Significance</th>
                  </tr>
                </thead>
                <tbody>
                  {data.high_value_rules.map((r) => (
                    <tr key={r.rule_id} className="border-b border-slate-200 dark:border-slate-800/50">
                      <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">{r.rule_name}</td>
                      <td className="py-2 px-3 text-right text-slate-600 dark:text-slate-400">{r.engine_id}</td>
                      <td className="py-2 px-3 text-right text-slate-700 dark:text-slate-300">{pct(r.pass_rate)}</td>
                      <td className="py-2 px-3 text-right text-emerald-600 dark:text-emerald-400">{fmt(r.return_delta)}</td>
                      <td className="py-2 px-3 text-right text-slate-700 dark:text-slate-300">{fmt(r.significance_score)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {data.redundant_rules.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-2">
              Redundant Rules ({data.redundant_rules.length})
            </h4>
            <div className="flex flex-wrap gap-2">
              {data.redundant_rules.map((r) => (
                <span key={r.rule_id} className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-1 rounded">
                  {r.rule_name}
                </span>
              ))}
            </div>
          </div>
        )}

        {data.weak_rules.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider mb-2">
              Weak Rules ({data.weak_rules.length})
            </h4>
            <div className="flex flex-wrap gap-2">
              {data.weak_rules.map((r) => (
                <span key={r.rule_id} className="text-xs bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 px-2 py-1 rounded">
                  {r.rule_name}
                </span>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs text-slate-500 italic">{data.summary}</p>
      </div>
    </Card>
  );
}

function EnginesSection({ data }: { data: EngineEffectivenessResponse | null }) {
  if (!data || data.engines.length === 0) return null;

  if (!data.measurability.forward_returns_available) {
    return (
      <Card title="Engine Effectiveness" subtitle={`${data.total_runs_analyzed} runs analyzed`}>
        <MeasurabilityNotice measurability={data.measurability} />
        <p className="mt-3 text-xs text-slate-500">{data.summary}</p>
      </Card>
    );
  }

  return (
    <Card title="Engine Effectiveness" subtitle={`${data.total_runs_analyzed} runs analyzed`}>
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
              <th className="text-left py-2 px-3">Engine</th>
              <th className="text-right py-2 px-3">Avg Score</th>
              <th className="text-right py-2 px-3">Pass Rate</th>
              <th className="text-right py-2 px-3">Contribution</th>
              <th className="text-right py-2 px-3">Correlation</th>
              <th className="text-right py-2 px-3">Avg Fwd Return (engine scores &gt; 0)</th>
              <th className="text-right py-2 px-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.engines.map((e) => (
              <tr key={e.engine_id} className="border-b border-slate-200 dark:border-slate-800/50">
                <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">{e.engine_name}</td>
                <td className="py-2 px-3 text-right text-slate-700 dark:text-slate-300">{fmt(e.avg_score, 4)}</td>
                <td className="py-2 px-3 text-right text-slate-700 dark:text-slate-300">{pct(e.avg_pass_rate)}</td>
                <td className="py-2 px-3 text-right text-slate-700 dark:text-slate-300">{fmt(e.contribution_to_final_score, 4)}</td>
                <td className="py-2 px-3 text-right text-slate-700 dark:text-slate-300">{fmt(e.correlation_with_outcome, 2)}</td>
                <td className="py-2 px-3 text-right">
                  <span className={e.improves_performance ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}>
                    {pct(e.avg_forward_return_when_engine_scores_high)}
                  </span>
                </td>
                <td className="py-2 px-3 text-right">
                  {e.improves_performance ? (
                    <span className="text-emerald-600 dark:text-emerald-400">Pass</span>
                  ) : (
                    <span className="text-rose-600 dark:text-rose-400">Review</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.recommended_exclusions.length > 0 && (
        <div className="mt-3 p-3 bg-rose-50 dark:bg-rose-950/50 rounded-lg border border-rose-200 dark:border-rose-800/50">
          <p className="text-xs text-rose-700 dark:text-rose-300">
            Recommended exclusions: {data.recommended_exclusions.join(', ')}
          </p>
        </div>
      )}

      <p className="mt-3 text-xs text-slate-500 italic">{data.summary}</p>
    </Card>
  );
}

function ValidationSection({ data }: { data: HistoricalValidationResponse | null }) {
  if (!data) return null;

  return (
    <Card title="Historical Validation" subtitle={`${data.total_trading_days} trading days across ${data.windows.length} windows`}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {data.windows.map((w) => (
          <div
            key={w.window.label}
            className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-4 border border-slate-200 dark:border-slate-700/50"
          >
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">{w.window.label} Window</h4>
            <div className="space-y-1 text-xs">
              <p className="text-slate-500">
                {w.window.start_date} → {w.window.end_date}
              </p>
              <p className="text-slate-600 dark:text-slate-400">
                Trading days: <span className="text-slate-800 dark:text-slate-200">{w.window.trading_days}</span>
              </p>
              <p className="text-slate-600 dark:text-slate-400">
                Runs: <span className="text-slate-800 dark:text-slate-200">{w.total_runs}</span>
              </p>
              <p className="text-slate-600 dark:text-slate-400">
                Successful: <span className="text-emerald-600 dark:text-emerald-400">{w.successful_runs}</span>
              </p>
              <p className="text-slate-600 dark:text-slate-400">
                Failed: <span className="text-rose-600 dark:text-rose-400">{w.failed_runs}</span>
              </p>
              <p className="text-slate-600 dark:text-slate-400">
                Pass Rate:{' '}
                <span className="text-slate-800 dark:text-slate-200">{pct(w.successful_runs / (w.total_runs || 1))}</span>
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
        <span>
          Overall Pass Rate: <span className="text-emerald-600 dark:text-emerald-400 font-mono">{pct(data.overall_pass_rate)}</span>
        </span>
        <span>Generated: {data.generated_at}</span>
      </div>
    </Card>
  );
}

function QualityMetric({ title, value, good }: { title: string; value: string | null; good: boolean }) {
  const unmeasured = value === null || value === undefined;
  return (
    <Card title={title}>
      <div
        className={`text-2xl font-bold font-mono ${
          unmeasured
            ? 'text-slate-400 dark:text-slate-500'
            : good
              ? 'text-emerald-600 dark:text-emerald-400'
              : 'text-rose-600 dark:text-rose-400'
        }`}
      >
        {pct(value)}
      </div>
      {unmeasured && <p className="mt-1 text-xs text-slate-500">Not yet measurable</p>}
    </Card>
  );
}

function QualityMetrics({
  stability,
  fpr,
  fnr,
}: {
  stability: string | null;
  fpr: string | null;
  fnr: string | null;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <QualityMetric title="Ranking Stability" value={stability} good={num(stability) > 0.7} />
      <QualityMetric title="False Positive Rate" value={fpr} good={num(fpr) < 0.1} />
      <QualityMetric title="False Negative Rate" value={fnr} good={num(fnr) < 0.1} />
    </div>
  );
}

export default function ValidationPage() {
  const [strategy, setStrategy] = useState('minervini_trend_template');
  const [windowYears, setWindowYears] = useState(1);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['research-dashboard', strategy, windowYears],
    queryFn: () => getResearchDashboard({ strategy_name: strategy, window_years: windowYears }),
  });

  return (
    <div className="min-h-screen bg-white dark:bg-slate-900">
      <PageHeader
        title="Strategy Validation & Alpha Research"
        subtitle="Replace intuition with measurable evidence"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className={`bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-700 dark:text-slate-300 ${focusRing}`}
          >
            <option value="minervini_trend_template">Minervini Trend Template</option>
          </select>
          <select
            value={windowYears}
            onChange={(e) => setWindowYears(Number(e.target.value))}
            className={`bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-700 dark:text-slate-300 ${focusRing}`}
          >
            <option value={1}>1 Year Window</option>
            <option value={3}>3 Year Window</option>
            <option value={5}>5 Year Window</option>
            <option value={10}>10 Year Window</option>
          </select>
          <button
            onClick={() => refetch()}
            className={`px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition-colors ${focusRing}`}
          >
            Refresh
          </button>
        </div>
      </PageHeader>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {isLoading && <LoadingSpinner />}
        {error && <ErrorMessage message={(error as Error).message} />}

        {data && (
          <div className="space-y-6">
            <QualityMetrics stability={data.ranking_stability} fpr={data.false_positive_rate} fnr={data.false_negative_rate} />
            <ScorecardSection data={data.scorecard} />
            <AlphaSection data={data.alpha_analysis} />
            <ValidationSection data={data.historical_validation} />
            <RulesSection data={data.rule_effectiveness} />
            <EnginesSection data={data.engine_effectiveness} />
          </div>
        )}
      </div>
    </div>
  );
}
