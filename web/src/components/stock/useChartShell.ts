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

/** `chartId` names this screen's chart slot in the saved workspace (ADR-013 §5). */
export function useChartShell(symbol: string, strategyName: string, chartId: string) {
  const [timeframe, setTimeframeState] = useState<TimeframeId>('1Y');
  const { preferences, ready, update } = useChartPreferences(symbol, chartId);

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
    queryKey: ['stock-ohlcv', symbol, timeframe],
    queryFn: () => getOhlcv(symbol, fromDateFor(timeframe)),
    enabled: !!symbol,
    // Keep the current bars on screen while another range loads, so the chart
    // never blanks and a click during the load still lands on a bar.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === symbol ? keepPreviousData(previous) : undefined,
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
        atr14: b.atr14 === null ? null : parseFloat(b.atr14),
        adx14: b.adx14 === null ? null : parseFloat(b.adx14),
        macd_line: b.macd_line === null ? null : parseFloat(b.macd_line),
        macd_signal: b.macd_signal === null ? null : parseFloat(b.macd_signal),
        macd_histogram: b.macd_histogram === null ? null : parseFloat(b.macd_histogram),
      })),
    [indicatorSeries]
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
      // Placeholder bars are the previous range: still loading.
      isLoading: isLoading || isPlaceholderData,
      indicatorSeries: indicatorBars,
      activePanes: preferences.activePanes,
      onActivePanesChange: (panes: typeof preferences.activePanes) =>
        update({ activePanes: panes }),
      initialActiveMas: preferences.activeMas,
      onActiveMasChange: (mas: number[]) => update({ activeMas: mas }),
      drawingsEnabled: true,
      drawings: preferences.drawings,
      onDrawingsChange: (drawings: typeof preferences.drawings) => update({ drawings }),
    },
  };
}
