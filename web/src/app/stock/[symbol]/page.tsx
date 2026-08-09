'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { useChartPreferences } from '@/lib/chart-preferences';
import { getIndicatorSeries, getLiveStockAnalysis, getOhlcv, getStockExplanation, getStockHistory } from '@/lib/api-client';
import { Card, MetricCard, Badge, StatusDot, LoadingSpinner, ErrorMessage, PageHeader } from '@/components/shared/Card';
import { HORIZONS, DEFAULT_HORIZON } from '@/lib/horizons';
import type { EngineExplanation, RuleExplanation, StockExplanation } from '@/lib/types';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import { useChartColors } from '@/lib/useChartColors';
import { ScoreGauge } from '@/components/shared/ScoreGauge';
import { RulePassMatrix } from '@/components/stock/RulePassMatrix';
import { TrendTemplateCard } from '@/components/stock/TrendTemplateCard';
import { EngineContributionBars } from '@/components/stock/EngineContributionBars';
import { focusRing, chartPalette } from '@/lib/theme';
import { num } from '@/lib/format';
import { PriceChart, TIMEFRAMES, type TimeframeId } from '@/components/stock/PriceChart';
import { MomentumOverview } from '@/components/stock/MomentumOverview';
import { MomentumView } from '@/components/stock/MomentumView';
import { TechnicalWorkbench } from '@/components/stock/TechnicalWorkbench';
import { VolumeAccumulation } from '@/components/stock/VolumeAccumulation';
import { PatternCard } from '@/components/stock/PatternCard';
import { WhyItRanks } from '@/components/stock/WhyItRanks';
import { SuggestedStop } from '@/components/stock/SuggestedStop';
import { RelativeStrengthVsIndex } from '@/components/stock/RelativeStrengthVsIndex';
import { WatchlistStar } from '@/components/stock/WatchlistStar';

/** ISO date `days` before today, for the chart's `from` query param. */
function fromDateFor(timeframe: TimeframeId): string | undefined {
  const days = TIMEFRAMES.find((t) => t.id === timeframe)?.days;
  if (!days) return undefined;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}


// ── Rule-level "what would improve this" guidance ──────────────────────
const IMPROVEMENT_HINTS: Record<string, string> = {
  tt_close_above_sma150_200: 'Needs to close back above its 150- and 200-day averages.',
  tt_sma150_above_sma200: 'Needs its 150-day average to close the gap over its 200-day average.',
  tt_sma200_uptrend: 'Needs its 200-day average to resume trending upward.',
  tt_sma_stack: 'Needs its 50-day average to move back above the 150- and 200-day averages.',
  tt_close_above_sma50: 'Needs to reclaim its 50-day average.',
  tt_above_52w_low: 'Needs to move further away from its 52-week low before it qualifies as genuine strength.',
  tt_near_52w_high: 'Needs to close the gap to its 52-week high.',
  tt_rs_rating_min: 'Needs stronger relative performance versus the universe (RS rating below 70).',
  rs_line_uptrend: 'Its relative-strength line needs to resume an uptrend versus the benchmark.',
  vol_breakout_confirm: 'Needs a volume surge (≥1.4x average) to confirm any breakout attempt.',
  vol_accumulation_days: 'Needs more institutional buying days than selling days over the recent window.',
  bo_pivot_breakout: 'Needs to move closer to the top of its recent trading range before a breakout is credible.',
  bo_followthrough: 'Needs its short-term averages to confirm the move.',
  bo_false_breakout: 'Its last breakout attempt reversed — needs to reclaim that level convincingly.',
  mq_trend_persistence: 'Needs more consistent time spent above its 50-day average.',
  mq_acceleration: 'Its move has decelerated — needs fresh momentum, not just an intact trend.',
  risk_extension: 'Is extended too far above its 50-day average — a pullback toward that average would improve the entry.',
  risk_atr: 'Is too volatile day-to-day for a favourable risk/reward setup at this size.',
  risk_rr: 'Needs a better estimated reward-to-risk ratio before this is an attractive entry.',
};

const SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'chart', label: 'Chart' },
  { id: 'trend', label: 'Trend Template' },
  { id: 'engines', label: 'Engines' },
  { id: 'rules', label: 'Rules' },
  { id: 'scores', label: 'Scores' },
  { id: 'history', label: 'History' },
  { id: 'live', label: 'Live Analysis' },
];

function engineRules(explanation: StockExplanation, engineId: string): RuleExplanation[] {
  return explanation.rule_explanations.filter((r) => r.engine_name === engineId);
}

function engineFor(explanation: StockExplanation, engineId: string): EngineExplanation | undefined {
  return explanation.engine_explanations.find((e) => e.engine_name === engineId);
}

function AnalysisSection({
  title,
  engine,
  rules,
}: {
  title: string;
  engine: EngineExplanation | undefined;
  rules: RuleExplanation[];
}) {
  if (rules.length === 0) {
    return (
      <Card title={title}>
        <p className="text-xs text-slate-500 italic">Not evaluated for this stock.</p>
      </Card>
    );
  }
  return (
    <Card
      title={title}
      subtitle={engine ? `${engine.rules_passed}/${engine.rule_count} rules passed · score ${num(engine.score)}` : undefined}
    >
      <div className="space-y-2">
        {rules.map((rule) => (
          <div key={rule.rule_id} className="flex items-start gap-2 text-xs">
            <div className="mt-0.5"><StatusDot passed={rule.passed} /></div>
            <div className="flex-1">
              <div className="text-slate-700 dark:text-slate-300">{rule.explanation}</div>
              {!rule.passed && IMPROVEMENT_HINTS[rule.rule_id] && (
                <div className="text-amber-600 dark:text-amber-400/90 mt-0.5">{IMPROVEMENT_HINTS[rule.rule_id]}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function investmentReadiness(explanation: StockExplanation): { label: string; color: 'emerald' | 'amber' | 'rose' } {
  if (!explanation.overall_passed) {
    return { label: 'Not Qualified', color: 'rose' };
  }
  const buySetup = parseFloat(explanation.buy_setup_score);
  if (buySetup >= 60) {
    return { label: 'Qualified — Actionable Now', color: 'emerald' };
  }
  return { label: 'Qualified — Not Actionable Yet', color: 'amber' };
}

function SectionNav({ active, onSelect }: { active: string; onSelect: (id: string) => void }) {
  const go = (id: string) => {
    onSelect(id);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  return (
    <div className="sticky top-[4.5rem] z-30 bg-white/95 dark:bg-slate-900/95 border-b border-slate-200 dark:border-slate-800 backdrop-blur-md -mx-6 px-6 py-2 mb-6">
      <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => go(s.id)}
            aria-current={active === s.id ? 'true' : undefined}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${focusRing} ${
              active === s.id
                ? 'bg-indigo-100 dark:bg-indigo-600/20 text-indigo-700 dark:text-indigo-300'
                : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function StockResearchPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const searchParams = useSearchParams();
  const strategyName = searchParams.get('strategy') || DEFAULT_HORIZON.strategyName;
  const horizonLabel = HORIZONS.find((h) => h.strategyName === strategyName)?.label ?? 'default';
  const chartColors = useChartColors();
  const [activeSection, setActiveSection] = useState('overview');
  const [timeframe, setTimeframeState] = useState<TimeframeId>('1Y');
  const { preferences, ready: prefsReady, update: updatePreferences } = useChartPreferences(symbol ?? '');

  // Phase 9.5 — apply the persisted timeframe once prefs are loaded; the chart
  // itself is only rendered after `prefsReady`, so it always mounts with final
  // values (no defaults-then-sync flash).
  useEffect(() => {
    if (prefsReady) setTimeframeState(preferences.timeframe);
  }, [prefsReady, preferences.timeframe]);

  const setTimeframe = (id: TimeframeId) => {
    setTimeframeState(id);
    updatePreferences({ timeframe: id });
  };

  const { data: live, isLoading: liveLoading, error: liveError } = useQuery({
    queryKey: ['stock-live', symbol, strategyName],
    queryFn: () => getLiveStockAnalysis(symbol, false, strategyName),
    enabled: !!symbol,
  });

  const { data: ohlcv, isLoading: ohlcvLoading } = useQuery({
    queryKey: ['stock-ohlcv', symbol, timeframe],
    queryFn: () => getOhlcv(symbol, fromDateFor(timeframe)),
    enabled: !!symbol,
  });

  const { data: indicatorSeries } = useQuery({
    queryKey: ['stock-indicator-series', symbol, strategyName],
    queryFn: () => getIndicatorSeries(symbol, strategyName),
    enabled: !!symbol,
  });

  // Decode the backend's decimal-string bars into the chart's number-typed
  // series (values the backend did not produce are null).
  const indicatorBars = useMemo(
    () =>
      (indicatorSeries?.bars ?? []).map((b) => ({
        date: b.date,
        rsi14: b.rsi14 === null ? null : parseFloat(b.rsi14),
        adx14: b.adx14 === null ? null : parseFloat(b.adx14),
        macd_line: b.macd_line === null ? null : parseFloat(b.macd_line),
        macd_signal: b.macd_signal === null ? null : parseFloat(b.macd_signal),
        macd_histogram: b.macd_histogram === null ? null : parseFloat(b.macd_histogram),
      })),
    [indicatorSeries]
  );

  const { data: runExplanation, isLoading: explLoading } = useQuery({
    queryKey: ['stock-explanation', symbol, strategyName],
    queryFn: () => getStockExplanation(symbol, undefined, strategyName),
    enabled: !!symbol,
    // A symbol absent from the latest run is an expected 404, not a transient
    // failure — retrying it only delays the on-demand fallback.
    retry: false,
  });

  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ['stock-history', symbol, strategyName],
    queryFn: () => getStockHistory(symbol, strategyName, 90),
    enabled: !!symbol,
  });

  // Keep the section tabs in sync with what is actually on screen.
  const sectionsReady = prefsReady && !explLoading && !histLoading && !liveLoading;
  useEffect(() => {
    if (!sectionsReady) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length === 0) return;
        visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        setActiveSection(visible[0].target.id);
      },
      { rootMargin: '-140px 0px -55% 0px' }
    );
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [sectionsReady]);

  // A symbol that was not in the latest run (not evaluated, or evaluated but
  // not persisted) still has a full on-demand evaluation available. Fall back
  // to it rather than blanking the whole page: everything below is identical
  // apart from rank/percentile, which only a ranked run can provide.
  const explanation = runExplanation ?? live?.explanation ?? undefined;
  const usingLiveFallback = !runExplanation && !!explanation;

  if (!prefsReady || explLoading || histLoading || (!runExplanation && liveLoading)) {
    return <LoadingSpinner text="Loading stock research…" />;
  }
  if (!explanation) {
    return (
      <ErrorMessage
        message={`No ${horizonLabel} analysis available for ${symbol}. It was not in the most recent screening run and could not be evaluated on demand either — it may have insufficient price history, or the symbol may not exist.`}
      />
    );
  }

  const chartData = (history?.score_history ?? []).map((p) => ({
    date: p.run_date.slice(0, 10),
    momentum: parseFloat(p.momentum_score),
    buySetup: parseFloat(p.buy_setup_score),
    rank: p.rank,
  }));

  const passedRules = explanation.rule_explanations.filter((r) => r.passed);
  const failedRules = explanation.rule_explanations.filter((r) => !r.passed);
  const readiness = investmentReadiness(explanation);

  const strengths = [...passedRules]
    .sort((a, b) => parseFloat(b.contribution) - parseFloat(a.contribution))
    .slice(0, 5);
  const weaknesses = [...failedRules]
    .sort((a, b) => {
      const aGate = explanation.hard_filter_failures.includes(a.rule_id) ? 1 : 0;
      const bGate = explanation.hard_filter_failures.includes(b.rule_id) ? 1 : 0;
      return bGate - aGate;
    })
    .slice(0, 5);

  const trendEngine = engineFor(explanation, 'trend_template');
  const rsEngine = engineFor(explanation, 'relative_strength');
  const patternEngine = engineFor(explanation, 'pattern');
  const breakoutEngine = engineFor(explanation, 'breakout');
  const riskEngine = engineFor(explanation, 'risk');

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title={symbol}
        subtitle={`${horizonLabel} horizon · ${explanation.overall_passed ? 'Passes' : 'Fails'} the Trend Template gate`}
      >
        {explanation.rank && <Badge color="indigo">Rank #{explanation.rank}</Badge>}
        <Badge color={explanation.overall_passed ? 'emerald' : 'rose'}>
          Trend Template {explanation.overall_passed ? 'PASS' : 'FAIL'}
        </Badge>
        <Badge color={readiness.color}>{readiness.label}</Badge>
        <Link
          href={`/stock/${symbol}/elliott-wave?strategy=${strategyName}`}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
        >
          Elliott Wave Analysis →
        </Link>
        <WatchlistStar symbol={symbol} />
      </PageHeader>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        <SectionNav active={activeSection} onSelect={setActiveSection} />

        {usingLiveFallback && (
          <div className="mb-6 rounded-xl border border-amber-200 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-950/20 px-4 py-3 text-xs text-amber-800 dark:text-amber-300">
            {symbol} was not part of the latest {horizonLabel} screening run, so there is no rank,
            percentile or score history for it. Everything below was evaluated on demand just now
            using the same rules, against data as of {live?.data_as_of ?? '—'}.
          </div>
        )}

        <div className="space-y-6">
          {/* Overview */}
          <section id="overview" className="scroll-mt-32 space-y-6">
            <div className="flex flex-col lg:flex-row items-stretch gap-6 rounded-xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/50 p-6 shadow-sm">
              <div className="flex items-center justify-center gap-8 lg:gap-10 shrink-0">
                <ScoreGauge label="Momentum" value={parseFloat(explanation.momentum_score)} />
                <ScoreGauge label="Buy Setup" value={parseFloat(explanation.buy_setup_score)} />
              </div>
              <div className="flex-1 min-w-0 border-t lg:border-t-0 lg:border-l border-slate-200 dark:border-slate-700/60 pt-4 lg:pt-0 lg:pl-6">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3">
                  Rule Pass Matrix
                </div>
                <RulePassMatrix
                  rules={explanation.rule_explanations}
                  gateFailures={explanation.hard_filter_failures}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard
                label="Momentum Score"
                value={num(explanation.momentum_score, 1)}
                color={parseFloat(explanation.momentum_score) >= 50 ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-800 dark:text-slate-200'}
              />
              <MetricCard label="Buy Setup Score" value={num(explanation.buy_setup_score, 1)} />
              <MetricCard label="Composite Score" value={num(explanation.composite_score, 1)} />
              <MetricCard label="RS Rating" value={num(live?.indicators.rs_rating, 0)} />
              <MetricCard label="Rank" value={explanation.rank ? `#${explanation.rank}` : '—'} />
              <MetricCard label="Percentile" value={explanation.percentile ? `${explanation.percentile}%` : '—'} />
              <MetricCard
                label="Hard Filters"
                value={`${explanation.hard_filter_failures.length} failures`}
                color={explanation.overall_passed ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}
              />
              {/* Risk-only. Deliberately carries no reward/target counterpart. */}
              <MetricCard
                label="Suggested Stop (risk only)"
                value={num(live?.suggested_stop?.level, 2)}
                changeLabel={live?.suggested_stop?.method}
              />
            </div>

            <Card title="Executive Summary">
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {symbol} {explanation.overall_passed ? 'currently qualifies' : 'does not currently qualify'} as
                a Stage 2 momentum candidate under the {horizonLabel} methodology, with a Momentum Score of{' '}
                {num(explanation.momentum_score, 1)} and a Buy Setup Score of{' '}
                {num(explanation.buy_setup_score, 1)}.{' '}
                {explanation.overall_passed
                  ? readiness.label === 'Qualified — Actionable Now'
                    ? 'Its breakout and volume signals also confirm this as an actionable setup today, not just a qualifying trend.'
                    : 'However, its breakout/volume signals are not yet confirming a fresh, actionable entry point today.'
                  : `It fails ${explanation.hard_filter_failures.length} of the mandatory Trend Template / liquidity gate condition(s), which is why it is excluded from the ranked universe regardless of its other scores.`}
              </p>
            </Card>

            <Card title="Momentum Thesis">
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{explanation.overall_rationale}</p>
            </Card>
          </section>

          {/* Chart — the analyst's primary working surface, so it sits directly
              under the overview rather than at the foot of the page. */}
          <section id="chart" className="scroll-mt-32">
            <Card title="Price history">
              <PriceChart
                bars={ohlcv?.bars ?? []}
                timeframe={timeframe}
                onTimeframeChange={setTimeframe}
                isLoading={ohlcvLoading}
                indicatorSeries={indicatorBars}
                activePanes={preferences.activePanes}
                onActivePanesChange={(panes) => updatePreferences({ activePanes: panes })}
                initialActiveMas={preferences.activeMas}
                onActiveMasChange={(mas) => updatePreferences({ activeMas: mas })}
                drawingsEnabled
                initialDrawings={preferences.drawings}
                onDrawingsChange={(drawings) => updatePreferences({ drawings })}
              />
            </Card>
          </section>

          {/* Trend Template — the hard gate, grouped by what each rule asks. */}
          <section id="trend" className="scroll-mt-32">
            <TrendTemplateCard
              rules={engineRules(explanation, 'trend_template')}
              strategyName={strategyName}
              hints={IMPROVEMENT_HINTS}
            />
          </section>

          {/* Scores */}
          <section id="scores" className="scroll-mt-32">
            {chartData.length > 1 && (
              <Card title="Historical Scores" subtitle={`Last 90 days · ${horizonLabel} horizon`}>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
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
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                      <Line type="monotone" dataKey="momentum" stroke={chartPalette.info} name="Momentum" dot={false} strokeWidth={2} />
                      <Line type="monotone" dataKey="buySetup" stroke={chartPalette.secondary} name="Buy Setup" dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}
          </section>

          {/* Engines */}
          <section id="engines" className="scroll-mt-32 space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <AnalysisSection title="Relative Strength Analysis" engine={rsEngine} rules={engineRules(explanation, 'relative_strength')} />
              <AnalysisSection title="Pattern Analysis" engine={patternEngine} rules={engineRules(explanation, 'pattern')} />
              <AnalysisSection title="Breakout Readiness" engine={breakoutEngine} rules={engineRules(explanation, 'breakout')} />
              <AnalysisSection title="Risk Assessment" engine={riskEngine} rules={engineRules(explanation, 'risk')} />
              <AnalysisSection
                title="Volume & Accumulation"
                engine={engineFor(explanation, 'volume_accumulation')}
                rules={engineRules(explanation, 'volume_accumulation')}
              />
            </div>

            <Card title="Engine Contributions">
              <div className="mb-4">
                <EngineContributionBars engines={explanation.engine_explanations} />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {explanation.engine_explanations.map((engine) => (
                  <div
                    key={engine.engine_name}
                    className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700/40"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <StatusDot passed={engine.passed} />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate capitalize">
                          {engine.engine_name.replace(/_/g, ' ')}
                        </div>
                        <div className="text-xs text-slate-500">
                          {engine.rules_passed}/{engine.rule_count} rules passed
                        </div>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-bold text-slate-800 dark:text-slate-200 tabular-nums">{num(engine.score)}</div>
                      <div className="text-xs text-slate-500">score</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </section>

          {/* Rules */}
          <section id="rules" className="scroll-mt-32 space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card title="Strengths" badge={{ text: `${passedRules.length} rules`, color: 'bg-emerald-900/50 text-emerald-300' }}>
                <div className="space-y-1.5">
                  {strengths.map((r) => (
                    <div key={r.rule_id} className="flex items-start gap-2 text-xs">
                      <StatusDot passed />
                      <span className="text-slate-700 dark:text-slate-300">{r.explanation}</span>
                    </div>
                  ))}
                  {strengths.length === 0 && <div className="text-xs text-slate-400 dark:text-slate-600">No passing rules.</div>}
                </div>
              </Card>
              <Card title="Weaknesses" badge={{ text: `${failedRules.length} rules`, color: 'bg-rose-900/50 text-rose-300' }}>
                <div className="space-y-1.5">
                  {weaknesses.map((r) => (
                    <div key={r.rule_id} className="flex items-start gap-2 text-xs">
                      <StatusDot passed={false} />
                      <span className="text-slate-700 dark:text-slate-300">{r.explanation}</span>
                      {explanation.hard_filter_failures.includes(r.rule_id) && <Badge color="rose">gate</Badge>}
                    </div>
                  ))}
                  {weaknesses.length === 0 && <div className="text-xs text-slate-400 dark:text-slate-600">No failing rules.</div>}
                </div>
              </Card>
            </div>

            {failedRules.length > 0 && (
              <Card title="What Would Improve This Ranking">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {failedRules
                    .filter((r) => IMPROVEMENT_HINTS[r.rule_id])
                    .map((r) => (
                      <div key={r.rule_id} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                        <span className="text-amber-500 mt-0.5">→</span>
                        {IMPROVEMENT_HINTS[r.rule_id]}
                      </div>
                    ))}
                </div>
              </Card>
            )}

            <Card title="Complete Rule Evaluation" subtitle={`${explanation.rule_explanations.length} rules evaluated`}>
              <div className="space-y-2">
                {explanation.rule_explanations.map((rule) => (
                  <div
                    key={rule.rule_id}
                    className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-700/30"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <StatusDot passed={rule.passed} />
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">{rule.explanation}</div>
                        <div className="text-xs text-slate-500 truncate">
                          {rule.engine_name} · {num(rule.actual_value, 2)} {rule.threshold ? `(threshold ${num(rule.threshold, 2)})` : ''}
                        </div>
                      </div>
                    </div>
                    <div className="text-right shrink-0 ml-3">
                      <div className="text-xs font-bold text-slate-800 dark:text-slate-200 tabular-nums">{num(rule.contribution)}</div>
                      <div className="text-xs text-slate-500">contrib</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </section>

          {/* History */}
          <section id="history" className="scroll-mt-32">
            {chartData.length > 1 && (
              <Card title="Historical Rankings" subtitle={`Last 90 days · ${horizonLabel} horizon`}>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: chartColors.tick }} angle={-45} textAnchor="end" height={60} />
                      <YAxis reversed tick={{ fontSize: 10, fill: chartColors.tick }} domain={['dataMin - 5', 'dataMax + 5']} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: chartColors.tooltipBg,
                          border: `1px solid ${chartColors.tooltipBorder}`,
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                      <Line type="monotone" dataKey="rank" stroke={chartPalette.warning} name="Rank" dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}
          </section>

          {/* Live on-demand analysis (Phase 6) */}
          <section id="live" className="scroll-mt-32 space-y-6">
            <Card
              title="On-demand analysis"
              subtitle={
                live
                  ? `Freshly evaluated as of ${live.data_as_of}${live.refreshed ? ` · ${live.bars_fetched} new bars fetched` : ' · stored bars (not refreshed)'}`
                  : 'Evaluating this symbol through the live strategy engine…'
              }
              badge={
                live
                  ? {
                      text: live.verdict,
                      color:
                        live.verdict === 'PASSED'
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300'
                          : live.verdict === 'FAILED'
                            ? 'bg-rose-100 text-rose-700 dark:bg-rose-900/50 dark:text-rose-300'
                            : 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300',
                    }
                  : undefined
              }
            >
              {liveLoading && <LoadingSpinner text="Evaluating this symbol on demand…" />}
              {liveError && (
                <p className="text-xs text-rose-600 dark:text-rose-400">
                  The live evaluation for {symbol} could not be completed. The historical run data
                  above is unaffected.
                </p>
              )}
              {live && (
                <div className="space-y-2 text-xs text-slate-600 dark:text-slate-400">
                  {!live.data_sufficient && (
                    <p className="text-amber-600 dark:text-amber-400">
                      Insufficient price history to evaluate every rule — the figures below are
                      partial.
                    </p>
                  )}
                  {live.indeterminate_rules.length > 0 && (
                    <p className="text-amber-600 dark:text-amber-400">
                      Could not be measured for this symbol: {live.indeterminate_rules.join(', ')}.
                      This is reported as {live.verdict}, not as a failure.
                    </p>
                  )}
                  <p>
                    Verdict {live.verdict} · relative strength measured against{' '}
                    {String(live.rs_basis.universe_size ?? '—')} symbols
                    {live.rs_basis.as_of ? ` as of ${String(live.rs_basis.as_of)}` : ''}.
                  </p>
                </div>
              )}
            </Card>

            {live && <MomentumOverview live={live} bars={ohlcv?.bars ?? []} />}

            {live?.explanation && (
              <>
                <MomentumView explanation={live.explanation} />
                <TechnicalWorkbench indicators={live.indicators} />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <VolumeAccumulation
                    explanation={live.explanation}
                    indicators={live.indicators}
                  />
                  <SuggestedStop
                    stop={live.suggested_stop}
                    trailingStop={live.trailing_stop}
                    latestClose={
                      ohlcv?.bars.length ? parseFloat(ohlcv.bars[ohlcv.bars.length - 1].close) : null
                    }
                  />
                </div>
                <RelativeStrengthVsIndex
                  points={live.relative_strength_vs_index ?? []}
                  benchmarkIndex={live.benchmark_index}
                />
                <PatternCard
                  explanation={live.explanation}
                  symbol={symbol}
                  bars={ohlcv?.bars ?? []}
                  timeframe={timeframe}
                  onTimeframeChange={setTimeframe}
                  lookbackDays={TIMEFRAMES.find((t) => t.id === timeframe)?.days ?? 2000}
                />
                <WhyItRanks explanation={live.explanation} />
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
