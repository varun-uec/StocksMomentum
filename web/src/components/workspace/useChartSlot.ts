/**
 * Everything one chart slot of the workspace draws: the saved chart settings,
 * catalogue indicators and compare lines, as props for `PriceChart`. The single
 * chart and every grid cell use it, so a chart looks the same in any layout.
 */

import { factorAt } from '@/lib/traded-prices';
import { useAlerts } from '@/components/workspace/AlertsTab';
import { useMemo } from 'react';
import { DEFAULT_STRATEGY } from '@/app/strategy-context';
import { useChartShell } from '@/components/stock/useChartShell';
import { needsBenchmark, useBenchmarkCloses, useCatalogueIndicators } from '@/components/stock/useCatalogueIndicators';
import { useCompare } from '@/components/workspace/useCompare';
import { toBars } from '@/lib/indicators/overlays';
import { useOverlayPreferences } from '@/lib/overlay-preferences';
import type { ChartInterval } from '@/lib/types';
import { useWorkspaceChart } from '@/lib/workspace';

const NO_SYMBOLS: string[] = [];

export function useChartSlot(
  chartId: string,
  symbol: string,
  strategyName: string,
  /** A layout that syncs intervals shows the active chart's, and changes it there. */
  syncedInterval?: { interval: ChartInterval; onChange: (next: ChartInterval) => void },
) {
  const shell = useChartShell(symbol, DEFAULT_STRATEGY, chartId, { intervals: true, interval: syncedInterval?.interval });
  const chart = useWorkspaceChart(chartId);
  const { overlays, update: updateOverlays } = useOverlayPreferences(chartId);
  const bars = useMemo(() => toBars(shell.bars), [shell.bars]);
  const benchmark = useBenchmarkCloses(symbol, strategyName, needsBenchmark(overlays.indicators));
  const catalogue = useCatalogueIndicators(bars, overlays.indicators, shell.chartProps, benchmark, (indicators) =>
    updateOverlays({ indicators, presetEdited: true }),
    shell.chartProps.initialWindow?.from,
  );
  const alerts = useAlerts();
  const alertLevels = useMemo(() => alerts.data?.alerts.filter((a) => a.symbol === symbol && a.status === 'active' && a.source === 'close').flatMap((a) => a.drawing
    ? a.drawing.points.map((p, i) => ({ price: Number(p.price) * factorAt(shell.adjustments ?? [], p.date), title: `EOD #${a.id}${a.drawing!.points.length > 1 ? (i ? ' high/low' : ' low/high') : ''}` }))
    : [{ price: Number(a.threshold) * factorAt(shell.adjustments ?? [], a.armed_after), title: `EOD #${a.id} ${a.condition.replaceAll('_', ' ')}` }]) ?? [], [alerts.data, symbol, shell.adjustments]);
  const compareSymbols = chart.chart.compare ?? NO_SYMBOLS;
  const compare = useCompare(compareSymbols, bars, shell.chartProps.interval, shell.chartProps.initialWindow?.from);
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
      ...(syncedInterval ? { onIntervalChange: syncedInterval.onChange } : {}),
    },
  };
}
