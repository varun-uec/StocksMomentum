/**
 * Everything one chart slot of the workspace draws: the saved chart settings,
 * catalogue indicators and compare lines, as props for `PriceChart`. The single
 * chart and every grid cell use it, so a chart looks the same in any layout.
 */

import { alertPriceLevels } from '@/components/workspace/alert-levels';
import { useAlerts } from '@/components/workspace/AlertsTab';
import { useMemo } from 'react';
import { useChartShell } from '@/components/stock/useChartShell';
import { needsBenchmark, useBenchmarkCloses, useCatalogueIndicators } from '@/components/stock/useCatalogueIndicators';
import { useCompare } from '@/components/workspace/useCompare';
import { toBars } from '@/lib/indicators/overlays';
import { upTo } from '@/lib/replay';
import { useOverlayPreferences } from '@/lib/overlay-preferences';
import type { ChartInterval } from '@/lib/types';
import { useWorkspaceChart } from '@/lib/workspace';

const NO_SYMBOLS: string[] = [];

export function useChartSlot(
  chartId: string,
  symbol: string,
  strategyName: string,
  strategyHash?: string,
  /** A layout that syncs intervals shows the active chart's, and changes it there. */
  syncedInterval?: { interval: ChartInterval; onChange: (next: ChartInterval) => void },
  /** Bar replay: every series this slot draws stops at this date. */
  replayDate?: string,
) {
  const shell = useChartShell(symbol, strategyName, chartId, { intervals: true, interval: syncedInterval?.interval, asOf: replayDate, configHash: strategyHash });
  const chart = useWorkspaceChart(chartId);
  const { overlays, update: updateOverlays } = useOverlayPreferences(chartId);
  const bars = useMemo(() => toBars(shell.bars), [shell.bars]);
  const allBenchmark = useBenchmarkCloses(symbol, strategyName, needsBenchmark(overlays.indicators), strategyHash);
  const benchmark = useMemo(() => upTo(allBenchmark, replayDate), [allBenchmark, replayDate]);
  const catalogue = useCatalogueIndicators(bars, overlays.indicators, shell.chartProps, benchmark, (indicators) =>
    updateOverlays({ indicators, presetEdited: true }),
    shell.chartProps.initialWindow?.from,
  );
  const alerts = useAlerts();
  // Replay neither evaluates nor shows alerts: their levels were set later.
  const alertLevels = useMemo(
    () => (replayDate ? [] : alertPriceLevels(alerts.data?.alerts ?? [], symbol, shell.adjustments ?? [])),
    [alerts.data, symbol, shell.adjustments, replayDate],
  );
  const compareSymbols = chart.chart.compare ?? NO_SYMBOLS;
  const compare = useCompare(compareSymbols, bars, shell.chartProps.interval, shell.chartProps.initialWindow?.from, replayDate);
  const overlayLines = useMemo(
    () => [...catalogue.lines, ...compare.flatMap((c) => (c.line ? [c.line] : []))],
    [catalogue.lines, compare],
  );

  return {
    shell,
    chart,
    overlays,
    updateOverlays,
    catalogue,
    compare,
    compareSymbols,
    setCompare: (next: string[]) => chart.update({ compare: next }),
    chartProps: {
      ...shell.chartProps,
      ...catalogue.paneProps,
      overlayLines,
      studyLegend: catalogue.legend,
      alertLevels,
      replayDate,
      ...(syncedInterval ? { onIntervalChange: syncedInterval.onChange } : {}),
    },
  };
}
