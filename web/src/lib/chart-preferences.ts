import { useMemo } from 'react';
import {
  DRAWING_KINDS,
  type ChartDrawing,
  type DrawingKind,
} from '@/components/stock/chart-drawings';
import { TIMEFRAMES, type PaneId, type TimeframeId } from '@/components/stock/PriceChart';
import type { ChartType, PriceScale } from '@/components/stock/chart-types';
import type { ChartInterval } from '@/lib/types';
import { useSymbolDrawings, useWorkspaceChart, type ChartSettings } from '@/lib/workspace';

/**
 * Chart preferences, stored on the server since M11 (ADR-013 §5).
 *
 * Phase 9.5 kept them per symbol in `localStorage` under `chart-prefs:<symbol>`.
 * `parseLegacyPreferences` still reads that shape, once, for the import in
 * `local-import.ts`.
 */

export interface ChartPreferences {
  timeframe: TimeframeId;
  interval: ChartInterval;
  chartType: ChartType;
  scale: PriceScale;
  activeMas: number[];
  activePanes: PaneId[];
  drawings: ChartDrawing[];
}

const VALID_TIMEFRAMES: readonly string[] = TIMEFRAMES.map((t) => t.id);
const VALID_PANES: readonly string[] = ['rsi', 'macd', 'adx'];

export const LEGACY_KEY_PREFIX = 'chart-prefs:';

/**
 * Parse an untrusted stored JSON blob into a fully-validated preferences
 * object. Anything unknown is dropped back to the defaults so a stale or
 * hand-edited payload can never crash the chart.
 */
export function parseLegacyPreferences(raw: string | null): ChartPreferences {
  const base: ChartPreferences = {
    timeframe: '1Y',
    interval: '1D',
    chartType: 'candles',
    scale: 'normal',
    activeMas: [50, 200],
    activePanes: [],
    drawings: [],
  };
  if (!raw) return base;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return base;
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return base;
  const input = parsed as Record<string, unknown>;

  const timeframe = VALID_TIMEFRAMES.includes(String(input.timeframe))
    ? (input.timeframe as TimeframeId)
    : base.timeframe;

  const activeMas = Array.isArray(input.activeMas)
    ? input.activeMas.filter(
        (p): p is number => typeof p === 'number' && p >= 0 && Number.isInteger(p)
      )
    : base.activeMas;

  const activePanes = Array.isArray(input.activePanes)
    ? input.activePanes.filter((p): p is PaneId => VALID_PANES.includes(String(p)))
    : base.activePanes;

  const drawings = Array.isArray(input.drawings)
    ? input.drawings.filter(isValidDrawing)
    : base.drawings;

  return { timeframe, interval: '1D', chartType: 'candles', scale: 'normal', activeMas, activePanes, drawings };
}

export function isValidDrawing(value: unknown): value is ChartDrawing {
  if (typeof value !== 'object' || value === null) return false;
  const d = value as Record<string, unknown>;
  if (typeof d.id !== 'string' || typeof d.color !== 'string') return false;
  if (!DRAWING_KINDS.includes(d.kind as DrawingKind)) return false;
  if (!Array.isArray(d.points) || d.points.length === 0) return false;
  return d.points.every(
    (p) =>
      typeof p === 'object' &&
      p !== null &&
      typeof (p as Record<string, unknown>).date === 'string' &&
      typeof (p as Record<string, unknown>).price === 'number'
  );
}

/**
 * One chart's preferences. Range, moving averages and panes belong to the chart
 * (`chartId`); drawings belong to the symbol. Both live on the server (ADR-013
 * §5). `ready` is true once both have loaded, so consumers render with final
 * values instead of a defaults-then-sync flash.
 */
export function useChartPreferences(
  symbol: string,
  chartId: string,
): {
  preferences: ChartPreferences;
  ready: boolean;
  update: (patch: Partial<ChartPreferences>) => void;
} {
  const chart = useWorkspaceChart(chartId);
  const drawings = useSymbolDrawings(symbol);

  const preferences = useMemo<ChartPreferences>(
    () => ({
      timeframe: VALID_TIMEFRAMES.includes(chart.chart.range) ? (chart.chart.range as TimeframeId) : '1Y',
      interval: chart.chart.interval ?? '1D',
      chartType: chart.chart.chart_type ?? 'candles',
      scale: chart.chart.scale ?? 'normal',
      activeMas: chart.chart.mas,
      activePanes: chart.chart.panes.filter((p) => VALID_PANES.includes(p)),
      drawings: (drawings.drawings as unknown[]).filter(isValidDrawing),
    }),
    [chart.chart, drawings.drawings],
  );

  const update = (patch: Partial<ChartPreferences>) => {
    if (patch.drawings) drawings.update(patch.drawings);
    const settings: Partial<ChartSettings> = {};
    if (patch.timeframe) settings.range = patch.timeframe;
    if (patch.interval) settings.interval = patch.interval;
    if (patch.chartType) settings.chart_type = patch.chartType;
    if (patch.scale) settings.scale = patch.scale;
    if (patch.activeMas) settings.mas = patch.activeMas;
    if (patch.activePanes) settings.panes = patch.activePanes;
    if (Object.keys(settings).length > 0) chart.update({ ...settings, symbol: symbol || null });
  };

  return { preferences, ready: chart.ready && drawings.ready, update };
}
