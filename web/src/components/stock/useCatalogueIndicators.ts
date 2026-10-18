/**
 * Catalogue indicators on a chart: overlay lines, the legend, and browser
 * panes merged into the backend's indicator series. The analysis screen and
 * the chart workspace share it, so one indicator draws the same on both.
 *
 * Display only (NFR-1a): nothing here feeds a score, gate or rank.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getIndexCloses, getLiveStockAnalysis } from '@/lib/api-client';
import { INDICATOR_BY_ID } from '@/lib/indicators/catalogue';
import type { Bar, CloseBar, OverlaySeries } from '@/lib/indicators/overlays';
import type { ActiveIndicator } from '@/lib/overlay-preferences';
import type { LegendEntry } from '@/components/stock/OverlayPicker';
import type { ChartOverlayLine, IndicatorSeriesBar, PaneDef, PaneId } from '@/components/stock/PriceChart';

/** Four sub-panes already leave the price pane short; that is the cap. */
export const MAX_PANES = 4;

// Stable identities: the chart rebuilds a pane or overlay on every identity change.
const NO_PANE_DEFS: PaneDef[] = [];
const NO_CLOSES: CloseBar[] = [];

/** The indicators that need the benchmark index's closes. */
const NEEDS_BENCHMARK = new Set(['relstrength']);

/**
 * Daily closes of the benchmark index the live endpoint names for the symbol.
 * Loads only when `enabled`; the query keys match the stock screens, so the
 * cache serves all of them.
 */
export function useBenchmarkCloses(symbol: string, strategy: string, enabled: boolean): CloseBar[] {
  const { data: live } = useQuery({
    queryKey: ['stock-live', symbol, strategy],
    queryFn: () => getLiveStockAnalysis(symbol, false, strategy),
    enabled: enabled && !!symbol,
  });
  const benchmark = live?.benchmark_index ?? null;
  const { data } = useQuery({
    queryKey: ['index-closes', benchmark],
    queryFn: () => getIndexCloses(benchmark!),
    enabled: enabled && !!benchmark,
  });
  return useMemo(
    () => (data ? data.bars.map((b) => ({ date: b.date, close: parseFloat(b.close) })) : NO_CLOSES),
    [data],
  );
}

export function needsBenchmark(indicators: ActiveIndicator[]): boolean {
  return indicators.some((i) => NEEDS_BENCHMARK.has(i.id));
}

interface PaneProps {
  indicatorSeries: IndicatorSeriesBar[];
  extraPaneDefs: PaneDef[];
  activePanes: PaneId[];
  onActivePanesChange: (panes: PaneId[]) => void;
}

export function useCatalogueIndicators(
  bars: Bar[],
  indicators: ActiveIndicator[],
  base: Pick<PaneProps, 'indicatorSeries' | 'activePanes' | 'onActivePanesChange'>,
  benchmark: CloseBar[],
): { lines: ChartOverlayLine[]; legend: LegendEntry[]; paneCount: number; paneProps: PaneProps } {
  const overlays = useMemo(() => {
    const lines: ChartOverlayLine[] = [];
    const legend: LegendEntry[] = [];
    if (bars.length === 0) return { lines, legend };
    for (const instance of indicators) {
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
  }, [indicators, bars]);

  // Browser-computed pane values merged into the backend indicator series.
  const panes = useMemo(() => {
    const byDate = new Map<string, IndicatorSeriesBar>();
    for (const bar of base.indicatorSeries) byDate.set(bar.date, { ...bar });
    const defs: PaneDef[] = [];
    const ids: string[] = [];
    for (const instance of indicators) {
      const def = INDICATOR_BY_ID.get(instance.id);
      if (!def?.pane) continue;
      defs.push(def.pane);
      ids.push(def.pane.id);
      if (!def.compute || bars.length === 0) continue;
      let values: Record<string, (number | null)[]> = {};
      try {
        values = def.compute(bars, instance.params, { benchmark });
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
    return {
      indicatorSeries: Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date)),
      defs: defs.length ? defs : NO_PANE_DEFS,
      ids,
    };
  }, [indicators, bars, benchmark, base.indicatorSeries]);

  return {
    lines: overlays.lines,
    legend: overlays.legend,
    paneCount: panes.ids.length,
    paneProps: {
      indicatorSeries: panes.indicatorSeries,
      extraPaneDefs: panes.defs,
      activePanes: [...base.activePanes, ...panes.ids].filter((id, i, all) => all.indexOf(id) === i),
      // The chart's pane row owns the backend panes; catalogue panes are added
      // and removed through the picker.
      onActivePanesChange: (next) => base.onActivePanesChange(next.filter((id) => !panes.ids.includes(id))),
    },
  };
}
