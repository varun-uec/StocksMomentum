'use client';

/**
 * The unified analysis screen.
 *
 * One `PriceChart`, mounted once and never keyed or conditionally rendered.
 * The three modes — Chart, Patterns, Elliott Wave — swap annotation props on
 * that one chart; indicator overlays are mode-independent and always drawn.
 * That is what makes this one surface rather than three tools behind tabs.
 *
 * Presentation only. Nothing here writes to a screening run, and no number on
 * this page feeds the composite score, the ranking or the trend template.
 * Every target, verdict and signal is either a value the API returned or
 * arithmetic on the bars on screen, and each carries its basis in its label.
 */

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  Badge,
  Card,
  ErrorMessage,
  LoadingSpinner,
  MetricCard,
  PageHeader,
  StatusDot,
} from '@/components/shared/Card';
import { ScoreGauge } from '@/components/shared/ScoreGauge';
import { DEFAULT_STRATEGY } from '@/app/strategy-context';
import { getIndexCloses, getLiveStockAnalysis, getStockExplanation } from '@/lib/api-client';
import { num, strategyDisplayName } from '@/lib/format';
import { focusRing } from '@/lib/theme';
import {
  PriceChart,
  TIMEFRAMES,
  type ChartMarker,
  type ChartOverlayLine,
  type IndicatorSeriesBar,
  type PaneDef,
} from '@/components/stock/PriceChart';
import { useChartShell } from '@/components/stock/useChartShell';
import { useChartPatterns } from '@/components/stock/useChartPatterns';
import {
  CANDIDATE_COLORS,
  describe,
  useElliottWaveChart,
} from '@/components/stock/useElliottWaveChart';
import { CountSummary, WaveDetail } from '@/components/stock/elliott-wave-panels';
import { OverlayPicker, type LegendEntry } from '@/components/stock/OverlayPicker';
import { StrategyPanel } from '@/components/stock/StrategyPanel';
import { SymbolActionBar } from '@/components/stock/SymbolActionBar';
import { TrendTemplateCard } from '@/components/stock/TrendTemplateCard';
import { WhyItRanks } from '@/components/stock/WhyItRanks';
import { EngineContributionBars } from '@/components/stock/EngineContributionBars';
import { RulePassMatrix } from '@/components/stock/RulePassMatrix';
import { MomentumOverview } from '@/components/stock/MomentumOverview';
import { MomentumView } from '@/components/stock/MomentumView';
import { TechnicalWorkbench } from '@/components/stock/TechnicalWorkbench';
import { VolumeAccumulation } from '@/components/stock/VolumeAccumulation';
import { SuggestedStop } from '@/components/stock/SuggestedStop';
import { RelativeStrengthVsIndex } from '@/components/stock/RelativeStrengthVsIndex';
import { INDICATOR_BY_ID, type IndicatorDef } from '@/lib/indicators/catalogue';
import {
  atr,
  toBars,
  type Bar,
  type CloseBar,
  type OverlaySeries,
} from '@/lib/indicators/overlays';
import { useOverlayPreferences, newUid, type ActiveIndicator } from '@/lib/overlay-preferences';
import {
  PRESET_BY_ID,
  lastSwingLowDate,
  presetSignals,
  ruleStates,
  signalScore,
  type Signal,
} from '@/lib/strategies';
import { defaultParams } from '@/lib/indicators/catalogue';

// Stable identities: the chart's marker plugin and overlay effect rebuild on
// every prop identity change, so an empty literal per render would churn them.
const NO_MARKERS: ChartMarker[] = [];
const NO_LINES: ChartOverlayLine[] = [];
const NO_PANE_DEFS: PaneDef[] = [];

const MODES = [
  { id: 'chart', label: 'Chart' },
  { id: 'patterns', label: 'Patterns' },
  { id: 'elliott', label: 'Elliott Wave' },
] as const;
type Mode = (typeof MODES)[number]['id'];

/** Four sub-panes already leave the price pane short; that is the cap. */
const MAX_PANES = 4;

const SECTIONS = [
  { id: 'chart', label: 'Chart' },
  { id: 'overview', label: 'Overview' },
  { id: 'engines', label: 'Engines' },
  { id: 'live', label: 'Live analysis' },
];

const inr = (v: number) => `₹${v.toFixed(2)}`;

function SegmentedControl({
  value,
  onChange,
}: {
  value: Mode;
  onChange: (mode: Mode) => void;
}) {
  return (
    <div className="flex items-center gap-0.5 rounded-lg bg-slate-100 dark:bg-slate-800/60 p-0.5">
      {MODES.map((mode) => (
        <button
          key={mode.id}
          type="button"
          onClick={() => onChange(mode.id)}
          aria-pressed={value === mode.id}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${focusRing} ${
            value === mode.id
              ? 'bg-white dark:bg-slate-700 text-indigo-700 dark:text-indigo-300 shadow-sm'
              : 'text-slate-500 dark:text-slate-400'
          }`}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}

/** One price objective, always shown with the arithmetic that produced it. */
interface Target {
  label: string;
  price: number;
}

export default function UnifiedAnalysisPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const strategyQuery = searchParams.get('strategy');
  const strategyName = strategyQuery ?? DEFAULT_STRATEGY;
  const horizonLabel = strategyDisplayName(strategyName);

  // The mode lives in the URL so the action bar's Chart / Patterns / Elliott
  // Wave links can switch it; the segmented control below writes it back.
  const modeParam = searchParams.get('mode');
  const mode: Mode = MODES.some((m) => m.id === modeParam) ? (modeParam as Mode) : 'chart';
  const setMode = (next: Mode) => {
    const params = new URLSearchParams({ mode: next });
    if (strategyQuery) params.set('strategy', strategyQuery);
    router.replace(`/stock/${symbol}/analysis?${params.toString()}`, { scroll: false });
  };
  // Screen-level, never derived from mode: the chart calls `fitContent()`
  // whenever this is falsy, so a null/undefined flip on a mode switch would
  // silently throw away the reader's zoom.
  const [visibleRange, setVisibleRange] = useState<{ from: string; to: string } | null>(null);
  const [showPicker, setShowPicker] = useState(false);
  const [atrMultiple, setAtrMultiple] = useState(2);
  const [activeSection, setActiveSection] = useState('chart');

  const { timeframe, ready: chartReady, bars: barDtos, chartProps } = useChartShell(
    symbol ?? '',
    strategyName
  );
  const { overlays, ready: overlaysReady, update: updateOverlays } = useOverlayPreferences(
    symbol ?? ''
  );

  const { data: live, isLoading: liveLoading, error: liveError } = useQuery({
    queryKey: ['stock-live', symbol, strategyName],
    queryFn: () => getLiveStockAnalysis(symbol, false, strategyName),
    enabled: !!symbol,
  });

  const { data: runExplanation, isLoading: explLoading, error: explError } = useQuery({
    queryKey: ['stock-explanation', symbol, strategyName],
    queryFn: () => getStockExplanation(symbol, undefined, strategyName),
    enabled: !!symbol,
    // A symbol absent from the latest run is an expected 404, not a transient
    // failure — the on-demand fallback below serves those symbols instead.
    retry: false,
  });

  const benchmark = live?.benchmark_index ?? null;
  const { data: benchmarkCloses } = useQuery({
    queryKey: ['index-closes', benchmark],
    queryFn: () => getIndexCloses(benchmark!),
    enabled: !!benchmark,
  });

  const bars = useMemo<Bar[]>(() => toBars(barDtos), [barDtos]);
  const benchmarkBars = useMemo<CloseBar[]>(
    () =>
      (benchmarkCloses?.bars ?? []).map((b) => ({ date: b.date, close: parseFloat(b.close) })),
    [benchmarkCloses]
  );
  const lastClose = bars.length ? bars[bars.length - 1].close : null;

  const lookbackDays = TIMEFRAMES.find((t) => t.id === timeframe)?.days ?? 2000;
  const patterns = useChartPatterns(symbol ?? '', lookbackDays);
  const wave = useElliottWaveChart(symbol ?? '', timeframe, strategyName);

  // ── Indicators (mode-independent) ────────────────────────────────────

  const activeIndicators = overlays.indicators;

  const overlayResult = useMemo(() => {
    const lines: ChartOverlayLine[] = [];
    const legend: LegendEntry[] = [];
    if (bars.length === 0) return { lines, legend };
    for (const instance of activeIndicators) {
      const def = INDICATOR_BY_ID.get(instance.id);
      if (!def?.overlay) continue;
      let series: OverlaySeries[] = [];
      try {
        series = def.overlay(bars, instance.params);
      } catch {
        // A parameter combination the maths cannot serve (period longer than
        // the loaded range) drops that indicator, never the whole chart.
        series = [];
      }
      for (const s of series) {
        if (s.points.length === 0) continue;
        lines.push({
          points: s.points,
          color: s.color,
          lineWidth: 1,
          ...(s.dashed ? { lineStyle: 2 as unknown as ChartOverlayLine['lineStyle'] } : {}),
        });
        legend.push({
          label: s.label,
          color: s.color,
          value: s.points[s.points.length - 1].price.toFixed(2),
        });
      }
    }
    return { lines, legend };
  }, [activeIndicators, bars]);

  /** Browser-computed pane values merged into the backend indicator series. */
  const { indicatorSeries, extraPaneDefs, activePanes } = useMemo(() => {
    const byDate = new Map<string, IndicatorSeriesBar>();
    for (const bar of chartProps.indicatorSeries ?? []) byDate.set(bar.date, { ...bar });
    const defs: PaneDef[] = [];
    const panes: string[] = [];
    for (const instance of activeIndicators) {
      const def = INDICATOR_BY_ID.get(instance.id);
      if (!def?.pane) continue;
      defs.push(def.pane);
      panes.push(def.pane.id);
      if (!def.compute || bars.length === 0) continue;
      let values: Record<string, (number | null)[]> = {};
      try {
        values = def.compute(bars, instance.params, { benchmark: benchmarkBars });
      } catch {
        values = {};
      }
      for (const [key, series] of Object.entries(values)) {
        series.forEach((value, i) => {
          if (value === null || !Number.isFinite(value)) return;
          const date = bars[i].date;
          const entry = byDate.get(date) ?? { date };
          entry[key] = value;
          byDate.set(date, entry);
        });
      }
    }
    const merged = Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
    return {
      indicatorSeries: merged,
      extraPaneDefs: defs.length ? defs : NO_PANE_DEFS,
      activePanes: panes,
    };
  }, [activeIndicators, bars, benchmarkBars, chartProps.indicatorSeries]);

  const setIndicators = (next: ActiveIndicator[]) =>
    updateOverlays({ indicators: next, presetEdited: true });

  // Applying a preset writes its whole configuration in one action.
  const applyPreset = useMemo(
    () => (presetId: string) => {
      const preset = PRESET_BY_ID.get(presetId);
      if (!preset) return;
      const anchor = lastSwingLowDate(bars) ?? '';
      const indicators: ActiveIndicator[] = preset.indicators.flatMap((item) => {
        const def = INDICATOR_BY_ID.get(item.id);
        if (!def) return [];
        const params = { ...defaultParams(def), ...(item.params ?? {}) };
        if ('anchor' in params && !params.anchor) params.anchor = anchor;
        return [{ uid: newUid(item.id), id: item.id, params }];
      });
      updateOverlays({ presetId, indicators, presetEdited: false });
    },
    // `updateOverlays` is stable in behaviour; bars only feed the VWAP anchor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [bars]
  );

  // Seed the default preset's configuration the first time this symbol is seen.
  const [seeded, setSeeded] = useState(false);
  useEffect(() => {
    if (!overlaysReady || seeded || bars.length === 0) return;
    setSeeded(true);
    if (overlays.indicators.length === 0 && !overlays.presetEdited) applyPreset(overlays.presetId);
  }, [overlaysReady, seeded, bars, overlays, applyPreset]);

  // ── Signals ──────────────────────────────────────────────────────────

  const signals = useMemo(() => presetSignals(bars, overlays.presetId), [bars, overlays.presetId]);
  const rules = useMemo(() => ruleStates(bars, overlays.presetId), [bars, overlays.presetId]);
  const score = useMemo(() => signalScore(bars, overlays.presetId), [bars, overlays.presetId]);

  const signalMarkers = useMemo<ChartMarker[]>(() => {
    if (!overlays.showSignals) return NO_MARKERS;
    return signals.map((s) => ({
      date: s.date,
      text: s.direction === 'long' ? '▲' : s.direction === 'short' ? '▼' : '×',
      position: s.direction === 'long' ? 'belowBar' : 'aboveBar',
      color: s.direction === 'long' ? '#10b981' : s.direction === 'short' ? '#ef4444' : '#f59e0b',
      size: 0.7,
      shape: 'square',
    }));
  }, [signals, overlays.showSignals]);

  const zoomTo = (signal: Signal) => {
    const from = bars[Math.max(0, signal.index - 30)]?.date;
    const to = bars[Math.min(bars.length - 1, signal.index + 30)]?.date;
    if (from && to) setVisibleRange({ from, to });
  };

  // ── Mode-specific annotation ─────────────────────────────────────────

  const markers = useMemo<ChartMarker[]>(
    () => (mode === 'elliott' ? [...wave.markers, ...signalMarkers] : signalMarkers),
    [mode, wave.markers, signalMarkers]
  );

  const overlayLines = useMemo<ChartOverlayLine[]>(() => {
    const base = overlayResult.lines;
    if (mode === 'patterns') return [...base, ...patterns.overlayLines];
    if (mode === 'elliott') return [...base, ...wave.overlayLines];
    return base.length ? base : NO_LINES;
  }, [mode, overlayResult.lines, patterns.overlayLines, wave.overlayLines]);

  // ── Targets and risk / reward ────────────────────────────────────────

  const patternHeadline = useMemo(() => {
    const list = patterns.analysis?.patterns ?? [];
    return list.length
      ? [...list].sort((a, b) => b.completion_score - a.completion_score)[0]
      : null;
  }, [patterns.analysis]);

  const targets = useMemo<Target[]>(() => {
    const out: Target[] = [];
    // 1. Elliott Wave projections — the backend's own numbers, every degree.
    for (const candidate of wave.candidates) {
      if (!candidate.projection) continue;
      const low = parseFloat(candidate.projection.low);
      const high = parseFloat(candidate.projection.high);
      const tag = `${candidate.degree} degree ${describe({
        degree: candidate.degree,
        pattern: candidate.pattern,
        variant: candidate.variant,
        labels: candidate.labels,
        subdivisions: candidate.subdivisions,
      })}`;
      out.push({ label: `EW zone low — ${tag} (${candidate.projection.basis})`, price: low });
      out.push({ label: `EW zone midpoint — ${tag}`, price: (low + high) / 2 });
      out.push({ label: `EW zone high — ${tag} (${candidate.projection.basis})`, price: high });
    }
    // 2. Fibonacci extensions of the active count's last completed leg.
    const labels = wave.active?.labels ?? [];
    if (labels.length >= 3) {
      const a = parseFloat(labels[labels.length - 3].price);
      const b = parseFloat(labels[labels.length - 2].price);
      const c = parseFloat(labels[labels.length - 1].price);
      const legName = `${labels[labels.length - 3].label}→${labels[labels.length - 2].label}`;
      for (const ratio of [1.0, 1.272, 1.618, 2.618]) {
        out.push({
          label: `${ratio} extension of the ${legName} leg from ${labels[labels.length - 1].label}`,
          price: c + ratio * (b - a),
        });
      }
    }
    // 3. Pattern measured move: the formation's own height from its break point.
    if (patternHeadline) {
      const prices = patternHeadline.geometry.flatMap((line) =>
        line.points.map((p) => parseFloat(p.price))
      );
      if (prices.length > 1) {
        const height = Math.max(...prices) - Math.min(...prices);
        const breakPoint = parseFloat(
          patternHeadline.geometry[0].points[patternHeadline.geometry[0].points.length - 1].price
        );
        out.push({
          label: `${patternHeadline.display_name} measured move — ${height.toFixed(2)} of pattern height from ${breakPoint.toFixed(2)}`,
          price: breakPoint + height,
        });
      }
    }
    // 4. ATR objective from the displayed bars.
    const a14 = atr(bars, 14);
    const latestAtr = [...a14].reverse().find((v): v is number => v !== null);
    if (latestAtr !== undefined && lastClose !== null) {
      out.push({
        label: `${atrMultiple}× ATR(14) ${latestAtr.toFixed(2)} above the last close`,
        price: lastClose + atrMultiple * latestAtr,
      });
    }
    return out;
  }, [wave.candidates, wave.active, patternHeadline, bars, lastClose, atrMultiple]);

  const stop = live?.suggested_stop?.level ? parseFloat(live.suggested_stop.level) : null;

  // ── Section scroll-spy ───────────────────────────────────────────────

  const ready = chartReady && overlaysReady;
  useEffect(() => {
    if (!ready) return;
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
  }, [ready]);

  if (!symbol) return <ErrorMessage message="No symbol supplied." />;

  const explanation = runExplanation ?? live?.explanation ?? null;
  const usingLiveFallback = !runExplanation && !!explanation;

  if (!chartReady || !overlaysReady || explLoading || (!runExplanation && liveLoading)) {
    return <LoadingSpinner text="Loading the analysis…" />;
  }
  if (!explanation) {
    const unreachable = (liveError ?? explError) instanceof TypeError;
    return (
      <ErrorMessage
        message={
          unreachable
            ? 'Cannot reach the Momentum25 API. Check that the backend is running and reachable, then reload.'
            : `No ${horizonLabel} analysis available for ${symbol}. It was not in the most recent screening run and could not be evaluated on demand either — it may have insufficient price history, or the symbol may not exist.`
        }
      />
    );
  }

  const backHref = `/stock/${symbol}${strategyQuery ? `?strategy=${strategyQuery}` : ''}`;
  const waveHeadline = wave.candidates[0] ?? null;

  const footnote =
    mode === 'patterns'
      ? patterns.shown
        ? `${patterns.shown.display_name} geometry: ${patterns.shown.geometry.map((g) => g.name).join(', ')}. Indicator overlays and signal markers stay drawn.`
        : `${bars.length} daily bars. Pattern geometry appears once you run detection in the rail.`
      : mode === 'elliott'
        ? wave.active
          ? `${describe(wave.active)} at ${wave.active.degree} degree, ${wave.active.labels[0].bar_date} to ${wave.active.labels[wave.active.labels.length - 1].bar_date}, within ${wave.analysis?.bars_analyzed ?? 0} bars analysed at a ${wave.analysis?.top_degree_threshold_pct ?? wave.thresholdPct}% top-degree reversal threshold. Parenthesised labels are the next finer degree. Dashed bounds mark the projected completion zone.`
          : `${wave.analysis?.pivots.length ?? 0} confirmed pivots at a ${wave.thresholdPct}% reversal threshold.`
        : `${bars.length} daily bars to ${bars.length ? bars[bars.length - 1].date : '—'}. Overlays are computed in this browser from these bars; sub-pane sources are named in the picker. Signal markers: ▲ long, ▼ short, × exit.`;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader title={`${symbol} — Analysis`} subtitle={`${horizonLabel} horizon · one chart, three readings`}>
        {explanation?.rank && <Badge color="indigo">Rank #{explanation.rank}</Badge>}
        {explanation && (
          <Badge color={explanation.overall_passed ? 'emerald' : 'rose'}>
            Trend Template {explanation.overall_passed ? 'PASS' : 'FAIL'}
          </Badge>
        )}
        {explanation && <Badge color="indigo">Momentum {num(explanation.momentum_score, 0)}</Badge>}
        <SymbolActionBar symbol={symbol} strategyName={strategyQuery} current="analysis" />
        <Link
          href={backHref}
          className={`text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}
        >
          ← Back to research
        </Link>
      </PageHeader>

      {usingLiveFallback && (
        <div className="mx-auto max-w-7xl px-4 pt-4">
          <div className="rounded-xl border border-amber-200 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-950/20 px-4 py-3 text-xs text-amber-800 dark:text-amber-300">
            {symbol} was not part of the latest {horizonLabel} screening run, so there is no rank,
            percentile or score history for it. Everything below was evaluated on demand just now
            using the same rules, against data as of {live?.data_as_of ?? '—'}.
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="sticky top-[4.5rem] z-30 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-2 mb-4 bg-white/95 dark:bg-slate-900/95 border-b border-slate-200 dark:border-slate-800 backdrop-blur-md">
          <div className="flex flex-wrap items-center gap-3">
            <SegmentedControl value={mode} onChange={setMode} />
            <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
              {SECTIONS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => {
                    setActiveSection(s.id);
                    document.getElementById(s.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }}
                  aria-current={activeSection === s.id ? 'true' : undefined}
                  className={`px-2 py-1 rounded-md text-xs font-medium whitespace-nowrap ${focusRing} ${
                    activeSection === s.id
                      ? 'bg-indigo-100 dark:bg-indigo-600/20 text-indigo-700 dark:text-indigo-300'
                      : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <div className="ml-auto flex items-center gap-2">
              {visibleRange && (
                <button
                  type="button"
                  onClick={() => setVisibleRange(null)}
                  className={`px-2 py-1 rounded-md text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
                >
                  Show full range
                </button>
              )}
              <span className="text-[11px] text-slate-500">
                {activeIndicators.length} indicator{activeIndicators.length === 1 ? '' : 's'} ·{' '}
                {activePanes.length}/{MAX_PANES} panes
              </span>
              <button
                type="button"
                onClick={() => setShowPicker((v) => !v)}
                aria-expanded={showPicker}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-500 ${focusRing}`}
              >
                {showPicker ? 'Close indicators' : 'Indicators'}
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Chart — one instance, mounted once, for all three modes. */}
          <section id="chart" className="lg:col-span-2 scroll-mt-32 space-y-6">
            <Card>
              <PriceChart
                {...chartProps}
                height={560}
                indicatorSeries={indicatorSeries}
                extraPaneDefs={extraPaneDefs}
                activePanes={[...chartProps.activePanes, ...activePanes].filter(
                  (id, i, all) => all.indexOf(id) === i
                )}
                onActivePanesChange={(panes) => {
                  // The built-in row owns the backend panes; catalogue panes
                  // are added and removed through the picker.
                  chartProps.onActivePanesChange(
                    panes.filter((id) => !activePanes.includes(id))
                  );
                }}
                markers={markers}
                overlayLine={mode === 'elliott' ? wave.overlayLine : undefined}
                overlayLines={overlayLines}
                priceZone={mode === 'elliott' ? wave.priceZone : null}
                visibleRange={visibleRange}
                footnote={footnote}
              />
            </Card>

            {showPicker && (
              <Card title="Indicators" subtitle="Always drawn, in every mode">
                <OverlayPicker
                  active={activeIndicators}
                  onChange={setIndicators}
                  legend={overlayResult.legend}
                  paneCount={activePanes.length}
                  maxPanes={MAX_PANES}
                />
              </Card>
            )}

            <Card
              title="Targets and risk / reward"
              subtitle="Each level states the arithmetic that produced it"
            >
              <div className="flex items-center gap-2 mb-3 text-xs text-slate-500">
                <label className="flex items-center gap-1">
                  ATR objective multiple
                  <input
                    type="number"
                    min={0.5}
                    max={10}
                    step={0.5}
                    value={atrMultiple}
                    onChange={(e) => setAtrMultiple(Number(e.target.value))}
                    className={`w-16 px-1 py-0.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 tabular-nums ${focusRing}`}
                  />
                </label>
                <span>
                  Stop: {stop === null ? 'not available' : `${inr(stop)} · ${live?.suggested_stop?.method}`}
                </span>
              </div>
              {targets.length === 0 && (
                <p className="text-xs text-slate-500">
                  No projection is available yet. Elliott Wave zones arrive with the wave analysis,
                  the measured move after you run pattern detection.
                </p>
              )}
              <ul className="space-y-1">
                {targets.map((target) => {
                  const move = lastClose === null ? null : ((target.price - lastClose) / lastClose) * 100;
                  const rr =
                    lastClose === null || stop === null || lastClose - stop <= 0
                      ? null
                      : (target.price - lastClose) / (lastClose - stop);
                  return (
                    <li
                      key={target.label}
                      className="flex flex-wrap items-baseline justify-between gap-2 text-xs border-b border-slate-100 dark:border-slate-800 pb-1"
                    >
                      <span className="text-slate-600 dark:text-slate-400">{target.label}</span>
                      <span className="tabular-nums text-slate-800 dark:text-slate-200">
                        {inr(target.price)}
                        {move !== null && (
                          <span className="text-slate-500"> · {move >= 0 ? '+' : ''}{move.toFixed(1)}%</span>
                        )}
                        {rr !== null && <span className="text-slate-500"> · R:R {rr.toFixed(2)}</span>}
                      </span>
                    </li>
                  );
                })}
              </ul>
              <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-2">
                R:R = (target − last close {lastClose === null ? '' : inr(lastClose)}) ÷ (last close −
                suggested stop). The stop is the live endpoint&apos;s own `suggested_stop`.
              </p>
            </Card>
          </section>

          {/* Right rail. */}
          <aside className="lg:col-span-1 space-y-6 lg:sticky lg:top-32 lg:self-start lg:max-h-[calc(100vh-9rem)] lg:overflow-y-auto">
            {explanation && (
              <TrendTemplateCard
                rules={explanation.rule_explanations.filter((r) => r.engine_name === 'trend_template')}
                strategyName={strategyName}
              />
            )}

            <Card title="Strategy">
              <StrategyPanel
                presetId={overlays.presetId}
                edited={overlays.presetEdited}
                onPresetChange={applyPreset}
                score={score}
                rules={rules}
                signals={signals}
                showSignals={overlays.showSignals}
                onShowSignalsChange={(on) => updateOverlays({ showSignals: on })}
                onSignalClick={zoomTo}
              />
            </Card>

            {mode === 'patterns' && (
              <Card title="Chart patterns" subtitle="Detected only when you ask">
                <div className="space-y-3">
                  <button
                    type="button"
                    onClick={() => patterns.detection.mutate()}
                    disabled={patterns.detection.isPending}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-60 ${focusRing}`}
                  >
                    {patterns.detection.isPending ? 'Detecting…' : 'Detect patterns'}
                  </button>
                  {patternHeadline && (
                    <div className="rounded-lg border border-indigo-300 dark:border-indigo-700 p-3">
                      <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                        {patternHeadline.display_name} — {patternHeadline.completion_score}% complete
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Highest completion score of {patterns.analysis?.patterns.length ?? 0}{' '}
                        candidates, ranked by the backend, {patternHeadline.starts_on} →{' '}
                        {patternHeadline.ends_on}.
                      </div>
                      <ul className="mt-2 space-y-1">
                        {patternHeadline.criteria.map((c) => (
                          <li key={c.label} className="flex items-start gap-2 text-[11px]">
                            <span className={c.met ? 'text-emerald-500' : 'text-slate-400'}>
                              {c.met ? '✓' : '✗'}
                            </span>
                            <span className="text-slate-600 dark:text-slate-400">
                              {c.label}
                              {c.required && <span className="text-slate-400"> (required)</span>} —{' '}
                              {c.detail}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(patterns.analysis?.patterns.length ?? 0) > 1 && (
                    <p className="text-[11px] text-amber-600 dark:text-amber-400">
                      More than one formation fits these bars. They are alternative readings, not
                      confirmations of each other.
                    </p>
                  )}
                  <ul className="space-y-1">
                    {(patterns.analysis?.patterns ?? []).map((pattern, i) => (
                      <li key={`${pattern.pattern}-${pattern.starts_on}`}>
                        <button
                          type="button"
                          onClick={() => patterns.setSelected(i)}
                          aria-pressed={i === patterns.selected}
                          className={`w-full text-left px-2 py-1 rounded-md text-xs ${focusRing} ${
                            i === patterns.selected
                              ? 'bg-indigo-50 dark:bg-indigo-600/20'
                              : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                          }`}
                        >
                          {pattern.display_name}
                          <span className="text-slate-500"> · {pattern.completion_score}/100</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {patterns.analysis && patterns.analysis.patterns.length === 0 && (
                    <p className="text-xs text-slate-500">No clear pattern detected.</p>
                  )}
                </div>
              </Card>
            )}

            {mode === 'elliott' && (
              <Card title="Elliott Wave">
                <div className="space-y-3">
                  {waveHeadline && (
                    <div className="rounded-lg border border-indigo-300 dark:border-indigo-700 p-3">
                      <div className="text-sm font-semibold" style={{ color: CANDIDATE_COLORS[0] }}>
                        {waveHeadline.current_position}
                      </div>
                      <div className="text-xs text-slate-500">
                        Top-ranked count · labelling confidence{' '}
                        {parseFloat(waveHeadline.labelling_confidence).toFixed(0)}% ·{' '}
                        {waveHeadline.labelling_confidence_basis}
                      </div>
                      <ul className="mt-2 space-y-0.5">
                        {(wave.analysis?.ranking_rationale ?? []).map((linetext) => (
                          <li key={linetext} className="text-[11px] text-slate-500">
                            · {linetext}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <label
                    className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400"
                    title="The smallest reversal that confirms a pivot, and so the finest degree labelled. The top degree is coarsened away from it automatically."
                  >
                    Finest degree
                    <input
                      type="number"
                      min={2}
                      max={20}
                      step={1}
                      value={wave.thresholdPct}
                      onChange={(e) => {
                        wave.setThresholdPct(Number(e.target.value));
                        wave.selectCount(0);
                      }}
                      className={`w-16 px-1 py-0.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 tabular-nums ${focusRing}`}
                    />
                    %
                  </label>

                  {wave.candidates.length > 1 && (
                    <div className="flex flex-wrap gap-1">
                      {wave.candidates.map((candidate, index) => (
                        <button
                          key={`${candidate.pattern}-${candidate.labels[0].bar_date}`}
                          type="button"
                          onClick={() => wave.selectCount(index)}
                          aria-pressed={index === wave.candidateIndex}
                          className={`px-2 py-1 rounded-md text-[11px] border ${focusRing} ${
                            index === wave.candidateIndex
                              ? 'border-current'
                              : 'border-slate-300 dark:border-slate-700 text-slate-500'
                          }`}
                          style={
                            index === wave.candidateIndex
                              ? { color: CANDIDATE_COLORS[Math.min(index, CANDIDATE_COLORS.length - 1)] }
                              : undefined
                          }
                        >
                          {index === 0 ? 'Top count' : `Alternate ${index}`} ·{' '}
                          {parseFloat(candidate.labelling_confidence).toFixed(0)}
                        </button>
                      ))}
                    </div>
                  )}

                  {wave.path.length > 0 && (
                    <nav className="flex flex-wrap items-center gap-1 text-[11px]" aria-label="Wave degree">
                      {wave.path.map((node, level) => (
                        <span key={`${node.degree}-${level}`} className="flex items-center gap-1">
                          {level > 0 && <span className="text-slate-400">▸</span>}
                          <button
                            type="button"
                            onClick={() => {
                              wave.setDegreePath(wave.degreePath.slice(0, level));
                              wave.setSelectedWave(null);
                            }}
                            className={`px-1.5 py-0.5 rounded-md ${focusRing} ${
                              level === wave.path.length - 1
                                ? 'bg-indigo-100 dark:bg-indigo-600/25 text-indigo-700 dark:text-indigo-300'
                                : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
                            }`}
                          >
                            {node.degree} · {describe(node)}
                          </button>
                        </span>
                      ))}
                    </nav>
                  )}

                  {wave.active && (
                    <ul className="space-y-0.5">
                      {wave.active.labels.map((label, index) => {
                        if (index === 0) return null;
                        return (
                          <li key={`${label.label}-${label.bar_date}`}>
                            <button
                              type="button"
                              onClick={() => {
                                wave.setSelectedWave(wave.selectedWave === index ? null : index);
                                const from = wave.active!.labels[index - 1].bar_date;
                                setVisibleRange(
                                  wave.selectedWave === index
                                    ? null
                                    : { from, to: label.bar_date }
                                );
                              }}
                              aria-pressed={wave.selectedWave === index}
                              className={`w-full text-left px-2 py-1 rounded-md text-[11px] ${focusRing} ${
                                wave.selectedWave === index
                                  ? 'bg-indigo-50 dark:bg-indigo-600/20'
                                  : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                              }`}
                            >
                              <span className="font-semibold" style={{ color: wave.color }}>
                                Wave {label.label}
                              </span>{' '}
                              <span className="text-slate-500 tabular-nums">
                                {label.bar_date} · {parseFloat(label.price).toFixed(2)}
                              </span>
                            </button>
                            {wave.selectedWave === index && wave.count && wave.degreePath.length === 0 && (
                              <div className="mt-2 mb-3 ml-2 pl-3 border-l border-slate-200 dark:border-slate-800">
                                <WaveDetail count={wave.count} label={label.label} color={wave.color} />
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}

                  {wave.count && <CountSummary count={wave.count} color={wave.color} />}

                  <Link
                    href={`/stock/${symbol}/elliott-wave${strategyQuery ? `?strategy=${strategyQuery}` : ''}`}
                    className={`text-[11px] font-medium text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}
                  >
                    Full ranking panel and pivot table →
                  </Link>
                </div>
              </Card>
            )}

            {explanation && <WhyItRanks explanation={explanation} />}
          </aside>
        </div>

        {/* Everything below the chart is lifted from the detail page as-is. */}
        <div className="mt-6 space-y-6">
          {explanation && (
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
                <MetricCard label="Momentum Score" value={num(explanation.momentum_score, 1)} />
                <MetricCard label="Buy Setup Score" value={num(explanation.buy_setup_score, 1)} />
                <MetricCard label="Composite Score" value={num(explanation.composite_score, 1)} />
                <MetricCard label="RS Rating" value={num(live?.indicators.rs_rating, 0)} />
              </div>
            </section>
          )}

          {explanation && (
            <section id="engines" className="scroll-mt-32">
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
          )}

          <section id="live" className="scroll-mt-32 space-y-6">
            {live && <MomentumOverview live={live} bars={barDtos} />}
            {live?.explanation && (
              <>
                <MomentumView explanation={live.explanation} />
                <TechnicalWorkbench indicators={live.indicators} />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <VolumeAccumulation explanation={live.explanation} indicators={live.indicators} />
                  <SuggestedStop
                    stop={live.suggested_stop}
                    trailingStop={live.trailing_stop}
                    latestClose={lastClose}
                  />
                </div>
                <RelativeStrengthVsIndex
                  points={live.relative_strength_vs_index ?? []}
                  benchmarkIndex={live.benchmark_index}
                />
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
