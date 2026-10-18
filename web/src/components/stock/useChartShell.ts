/**
 * The shared chart shell (audit 2026-08-09, U3).
 *
 * Every chart-bearing route gets the same bars, the same indicator sub-panes,
 * the same moving averages and the same drawing tools, persisted per symbol via
 * `chart-preferences`. Previously only `/stock/[symbol]` wired these up, so a
 * reader lost their indicators and drawings one click later on the Elliott Wave
 * route. Annotation props (markers, overlays) stay per-route: the shell owns the
 * chart, not what a given view labels on it.
 */

import { useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getIndicatorSeries, getOhlcv } from '@/lib/api-client';
import { useChartPreferences } from '@/lib/chart-preferences';
import { toChartPrices, toTradedPrices, type PeriodBars } from '@/lib/traded-prices';
import type { ChartInterval } from '@/lib/types';
import { TIMEFRAMES, type TimeframeId } from '@/components/stock/PriceChart';

/** ISO date `days` before today, for the chart's `from` query param. */
function fromDateFor(timeframe: TimeframeId): string | undefined {
  const days = TIMEFRAMES.find((t) => t.id === timeframe)?.days;
  if (!days) return undefined;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

/** Trading days requested for analyses whose window must match the chart. */
export function lookbackDaysFor(timeframe: TimeframeId, fallback: number): number {
  return TIMEFRAMES.find((t) => t.id === timeframe)?.days ?? fallback;
}

/**
 * Indicator bars inside the price bars' span. Panes share the price pane's time
 * axis, so a value before the first price bar would stretch the axis past the
 * bars (M11 review). Daily panes keep the snapshot's bar window (their values
 * equal the rules' inputs), so on the longest ranges they start later.
 */
export function withinPriceSpan<T extends { date: string }>(indicatorBars: T[], firstPriceDate: string | undefined): T[] {
  return firstPriceDate ? indicatorBars.filter((b) => b.date >= firstPriceDate) : indicatorBars;
}

/**
 * `chartId` names this screen's chart slot in the saved workspace (ADR-013 §5).
 * `intervals` offers the daily / weekly / monthly switch. Screens that mark daily signals on the
 * chart leave it off, so they always show daily bars.
 */
export function useChartShell(symbol: string, strategyName: string, chartId: string, { intervals = false } = {}) {
  const [timeframe, setTimeframeState] = useState<TimeframeId>('1Y');
  const { preferences, ready, update } = useChartPreferences(symbol, chartId);
  const interval: ChartInterval = intervals ? preferences.interval : '1D';

  // Apply the persisted timeframe once prefs are loaded; callers render the
  // chart only after `ready`, so it mounts with final values.
  useEffect(() => {
    if (ready) setTimeframeState(preferences.timeframe);
  }, [ready, preferences.timeframe]);

  const setTimeframe = (id: TimeframeId) => {
    setTimeframeState(id);
    update({ timeframe: id });
  };

  const { data: ohlcv, isLoading, isPlaceholderData } = useQuery({
    queryKey: ['stock-ohlcv', symbol, timeframe, interval],
    queryFn: () => getOhlcv(symbol, fromDateFor(timeframe), undefined, interval),
    enabled: !!symbol,
    // Keep the current bars on screen while another range loads, so the chart
    // never blanks and a click during the load still lands on a bar.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === symbol ? keepPreviousData(previous) : undefined,
  });

  const { data: indicatorSeries } = useQuery({
    queryKey: ['stock-indicator-series', symbol, strategyName, interval],
    queryFn: () => getIndicatorSeries(symbol, strategyName, interval),
    enabled: !!symbol,
  });

  // Decode the backend's decimal-string bars into the chart's number-typed
  // series (values the backend did not produce are null).
  const firstPriceDate = ohlcv?.bars[0]?.date;
  const indicatorBars = useMemo(
    () =>
      withinPriceSpan(indicatorSeries?.bars ?? [], firstPriceDate).map((b) => ({
        date: b.date,
        rsi14: b.rsi14 === null ? null : parseFloat(b.rsi14),
        atr14: b.atr14 === null ? null : parseFloat(b.atr14),
        adx14: b.adx14 === null ? null : parseFloat(b.adx14),
        macd_line: b.macd_line === null ? null : parseFloat(b.macd_line),
        macd_signal: b.macd_signal === null ? null : parseFloat(b.macd_signal),
        macd_histogram: b.macd_histogram === null ? null : parseFloat(b.macd_histogram),
      })),
    [indicatorSeries, firstPriceDate]
  );

  // Drawings are saved at traded prices; the chart shows adjusted ones. Until
  // the schedule loads, no drawing can be placed, so none is shown.
  const adjustments = ohlcv?.adjustments;
  const periodBars = useMemo<PeriodBars | undefined>(
    () => (ohlcv && ohlcv.interval !== '1D' ? { interval: ohlcv.interval, dates: ohlcv.bars.map((b) => b.date) } : undefined),
    [ohlcv]
  );
  const chartDrawings = useMemo(
    () => (adjustments ? toChartPrices(preferences.drawings, adjustments, periodBars) : []),
    [preferences.drawings, adjustments, periodBars]
  );

  return {
    timeframe,
    ready,
    bars: ohlcv?.bars ?? [],
    /** Spread straight into `<PriceChart {...chartProps} />`. */
    chartProps: {
      bars: ohlcv?.bars ?? [],
      timeframe,
      onTimeframeChange: setTimeframe,
      interval,
      onIntervalChange: intervals ? (next: ChartInterval) => update({ interval: next }) : undefined,
      dataVersion: ohlcv?.data_version,
      chartType: preferences.chartType,
      onChartTypeChange: (chartType: typeof preferences.chartType) => update({ chartType }),
      scale: preferences.scale,
      onScaleChange: (scale: typeof preferences.scale) => update({ scale }),
      // Placeholder bars are the previous range: still loading.
      isLoading: isLoading || isPlaceholderData,
      indicatorSeries: indicatorBars,
      activePanes: preferences.activePanes,
      onActivePanesChange: (panes: typeof preferences.activePanes) =>
        update({ activePanes: panes }),
      activeMas: preferences.activeMas,
      onActiveMasChange: (mas: number[]) => update({ activeMas: mas }),
      drawingsEnabled: true,
      drawingsKey: symbol,
      drawings: chartDrawings,
      onDrawingsChange: (drawings: typeof preferences.drawings) => {
        if (adjustments) update({ drawings: toTradedPrices(drawings, preferences.drawings, adjustments, periodBars) });
      },
    },
  };
}
