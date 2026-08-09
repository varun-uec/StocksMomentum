'use client';

/**
 * Phase 6.2 — price chart bound to `GET /securities/{symbol}/ohlcv`.
 *
 * Every plotted value comes from a real bar (`open/high/low/close/volume`).
 * The MA overlays are plain rolling means over the *fetched close series* —
 * the backend exposes only a single latest value for sma50/150/200, and a
 * chart needs a full series, so the mean is computed here from backend bars
 * rather than invented. No pivots, no targets, no signal annotations.
 *
 * Phase 9 adds three groups of *optional* capabilities, all additive:
 *   • indicator sub-panes (RSI/MACD/ADX) fed by the backend's real indicator
 *     series — no indicator is computed in the browser,
 *   • a synced crosshair readout over the price bar and the open sub-pane
 *     values at the hovered date,
 *   • drawing tools rendered by the pane-primitive layer in
 *     `chart-drawings.ts`.
 * None of the pre-Phase-9 props (markers/overlayLine/overlayLines/priceZone)
 * change; Elliott Wave (Phase 7) and pattern geometry (Phase 8) render exactly
 * as before when the new props are omitted.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPaneApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { OHLCVBarDTO } from '@/lib/types';
import { focusRing } from '@/lib/theme';
import {
  DRAWING_COLOR,
  DRAWING_KINDS,
  DRAWING_LABELS,
  DRAWING_REQUIRED_POINTS,
  attachDrawingsLayer,
  drawingId,
  fromTime,
  toTime,
  type ChartDrawing,
  type DrawingKind,
  type DrawingPoint,
} from '@/components/stock/chart-drawings';

export const TIMEFRAMES = [
  { id: '1W', label: '1W', days: 7 },
  { id: '1M', label: '1M', days: 30 },
  { id: '3M', label: '3M', days: 91 },
  { id: '6M', label: '6M', days: 182 },
  { id: '1Y', label: '1Y', days: 365 },
  { id: 'MAX', label: 'MAX', days: null },
] as const;

export type TimeframeId = (typeof TIMEFRAMES)[number]['id'];

/** Phase 9 — the available indicator sub-panes, in their fixed chart order. */
export type PaneId = 'rsi' | 'macd' | 'adx';
const PANE_ORDER: PaneId[] = ['rsi', 'macd', 'adx'];
export const PANE_LABELS: Record<PaneId, string> = {
  rsi: 'RSI (14)',
  macd: 'MACD (12,26,9)',
  adx: 'ADX (14)',
};

const PANE_COLORS: Record<PaneId, string> = {
  rsi: '#f59e0b',
  macd: '#6366f1',
  adx: '#a855f7',
};

const MACD_SIGNAL_COLOR = '#f59e0b';
const MACD_HIST_POSITIVE = 'rgba(16,185,129,0.45)';
const MACD_HIST_NEGATIVE = 'rgba(239,68,68,0.45)';

/** One bar of the backend indicator series (Phase 9); every field optional. */
export interface IndicatorSeriesBar {
  date: string;
  rsi14?: number | null;
  atr14?: number | null;
  adx14?: number | null;
  macd_line?: number | null;
  macd_signal?: number | null;
  macd_histogram?: number | null;
}

const MA_PERIODS = [10, 20, 50, 100, 200] as const;
const MA_COLORS: Record<number, string> = {
  10: '#f59e0b',
  20: '#10b981',
  50: '#6366f1',
  100: '#ec4899',
  200: '#94a3b8',
};

/** Rolling simple mean of `closes`; `null` until the window is full. */
function rollingMean(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < closes.length; i += 1) {
    sum += closes[i];
    if (i >= period) sum -= closes[i - period];
    out.push(i >= period - 1 ? sum / period : null);
  }
  return out;
}

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`px-2 py-1 rounded-md text-xs font-medium transition-colors ${focusRing} ${
        active
          ? 'bg-indigo-100 dark:bg-indigo-600/25 text-indigo-700 dark:text-indigo-300'
          : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
      }`}
    >
      {children}
    </button>
  );
}

/** A text marker pinned to one bar (Phase 7 — Elliott Wave labels). */
export interface ChartMarker {
  date: string;
  text: string;
  position: 'aboveBar' | 'belowBar';
  color: string;
}

/** A horizontal price band drawn as two dashed bounds (Phase 7 — projection zone). */
export interface ChartPriceZone {
  low: number;
  high: number;
  title: string;
  color: string;
}

/** A named polyline overlay (Phase 8 — pattern geometry). */
export interface ChartOverlayLine {
  points: { date: string; price: number }[];
  color?: string;
}

interface PaneRecord {
  pane: IPaneApi<Time>;
  series: ISeriesApi<'Line' | 'Histogram'>[];
}

/** Values shown in the crosshair readout at the hovered bar. */
interface CrosshairReadout {
  date: string;
  bar: { open: number; high: number; low: number; close: number } | null;
  panes: { id: PaneId; value: number }[];
}

export function PriceChart({
  bars,
  timeframe,
  onTimeframeChange,
  isLoading = false,
  height = 380,
  footnote,
  markers,
  overlayLine,
  overlayLines,
  priceZone,
  indicatorSeries,
  activePanes,
  onActivePanesChange,
  initialActiveMas,
  onActiveMasChange,
  drawingsEnabled = false,
  initialDrawings,
  onDrawingsChange,
}: {
  bars: OHLCVBarDTO[];
  timeframe: TimeframeId;
  onTimeframeChange: (id: TimeframeId) => void;
  isLoading?: boolean;
  /** Chart height in px; the Elliott Wave screen renders a much taller chart. */
  height?: number;
  footnote?: string;
  markers?: ChartMarker[];
  /** Polyline through arbitrary (date, price) points, e.g. a wave count. */
  overlayLine?: { date: string; price: number; color?: string }[];
  /** Several independent polylines, e.g. the two trendlines of a triangle. */
  overlayLines?: ChartOverlayLine[];
  priceZone?: ChartPriceZone | null;
  // ── Phase 9: indicator sub-panes, crosshair readout, drawing tools ─────
  /** Backend-provided per-bar indicator values (never computed browser-side). */
  indicatorSeries?: IndicatorSeriesBar[];
  /**
   * Sub-panes to render (`activePanes` is controlled by the parent so the
   * selection survives navigation via Phase 9.5 preferences). When omitted the
   * chart keeps an internal default of none — identical to pre-Phase-9.
   */
  activePanes?: PaneId[];
  onActivePanesChange?: (panes: PaneId[]) => void;
  /** Initial MA toggles for the Phase 9.5 persisted preferences. */
  initialActiveMas?: number[];
  onActiveMasChange?: (mas: number[]) => void;
  /** Show the drawing toolbar and accept clicks while a tool is active. */
  drawingsEnabled?: boolean;
  /** Persisted drawings (Phase 9.5); read once on mount. */
  initialDrawings?: ChartDrawing[];
  onDrawingsChange?: (drawings: ChartDrawing[]) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const priceSeriesRef = useRef<ISeriesApi<'Candlestick'> | ISeriesApi<'Line'> | null>(null);
  const maSeriesRef = useRef<Map<number, ISeriesApi<'Line'>>>(new Map());
  const overlaySeriesRef = useRef<ISeriesApi<'Line'>[]>([]);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const zoneLinesRef = useRef<IPriceLine[]>([]);
  const paneSeriesRef = useRef<Map<PaneId, PaneRecord>>(new Map());
  const [candlestick, setCandlestick] = useState(true);
  const [activeMas, setActiveMas] = useState<number[]>(initialActiveMas ?? [50, 200]);
  const [drawingTool, setDrawingTool] = useState<DrawingKind | null>(null);
  const [draftPoints, setDraftPoints] = useState<DrawingPoint[]>([]);
  const [cursorPoint, setCursorPoint] = useState<DrawingPoint | null>(null);
  const [drawings, setDrawings] = useState<ChartDrawing[]>(initialDrawings ?? []);
  const [readout, setReadout] = useState<CrosshairReadout | null>(null);

  // Displayed panes: parent-controlled when `activePanes` is supplied, else a
  // private default of none (Phase 7/8 consumers pass neither prop).
  const [internalPanes, setInternalPanes] = useState<PaneId[]>([]);
  const displayedPanes = activePanes ?? internalPanes;
  const setDisplayedPanes = (next: PaneId[]) => {
    if (onActivePanesChange) onActivePanesChange(next);
    else setInternalPanes(next);
  };

  // Refs mirroring interaction state, so the mount-time event subscriptions
  // always read the latest render without re-subscribing.
  const drawingsEnabledRef = useRef(drawingsEnabled);
  const drawingToolRef = useRef(drawingTool);
  const draftPointsRef = useRef(draftPoints);
  const onDrawingsChangeRef = useRef(onDrawingsChange);
  useEffect(() => {
    drawingsEnabledRef.current = drawingsEnabled;
    drawingToolRef.current = drawingTool;
    draftPointsRef.current = draftPoints;
    onDrawingsChangeRef.current = onDrawingsChange;
  });

  const parsed = useMemo(
    () =>
      bars.map((b) => ({
        time: toTime(b.date),
        open: parseFloat(b.open),
        high: parseFloat(b.high),
        low: parseFloat(b.low),
        close: parseFloat(b.close),
      })),
    [bars]
  );

  const maSeriesData = useMemo(() => {
    const closes = parsed.map((p) => p.close);
    const result = new Map<number, { time: UTCTimestamp; value: number }[]>();
    for (const period of MA_PERIODS) {
      const means = rollingMean(closes, period);
      result.set(
        period,
        parsed
          .map((p, i) => ({ time: p.time, value: means[i] }))
          .filter((p): p is { time: UTCTimestamp; value: number } => p.value !== null)
      );
    }
    return result;
  }, [parsed]);

  /** Per-pane line data, mapped onto the price bars' timestamps. */
  const paneData = useMemo(() => {
    const out: Record<
      PaneId,
      { line: { time: UTCTimestamp; value: number }[]; signal?: { time: UTCTimestamp; value: number }[]; hist?: { time: UTCTimestamp; value: number; color?: string }[] }
    > = {
      rsi: { line: [] },
      macd: { line: [], signal: [], hist: [] },
      adx: { line: [] },
    };
    for (const bar of indicatorSeries ?? []) {
      const time = toTime(bar.date);
      if (bar.rsi14 != null) out.rsi.line.push({ time, value: bar.rsi14 });
      if (bar.adx14 != null) out.adx.line.push({ time, value: bar.adx14 });
      if (bar.macd_line != null) out.macd.line.push({ time, value: bar.macd_line });
      if (bar.macd_signal != null) out.macd.signal!.push({ time, value: bar.macd_signal });
      if (bar.macd_histogram != null)
        out.macd.hist!.push({
          time,
          value: bar.macd_histogram,
          color: bar.macd_histogram >= 0 ? MACD_HIST_POSITIVE : MACD_HIST_NEGATIVE,
        });
    }
    return out;
  }, [indicatorSeries]);

  /** Lookups for the crosshair readout, keyed by ISO bar date. */
  const readoutMaps = useMemo(() => {
    const barByDate = new Map<string, { open: number; high: number; low: number; close: number }>();
    for (const b of bars) {
      barByDate.set(b.date, {
        open: parseFloat(b.open),
        high: parseFloat(b.high),
        low: parseFloat(b.low),
        close: parseFloat(b.close),
      });
    }
    const indByDate = new Map<string, Partial<Record<PaneId, number>>>();
    for (const bar of indicatorSeries ?? []) {
      const entry: Partial<Record<PaneId, number>> = {};
      if (bar.rsi14 != null) entry.rsi = bar.rsi14;
      if (bar.adx14 != null) entry.adx = bar.adx14;
      if (bar.macd_line != null) entry.macd = bar.macd_line;
      indByDate.set(bar.date, entry);
    }
    return { barByDate, indByDate };
  }, [bars, indicatorSeries]);

  const readoutMapsRef = useRef(readoutMaps);
  useEffect(() => {
    readoutMapsRef.current = readoutMaps;
  });

  // Create the chart once; series are (re)built when the render mode changes.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const chart = createChart(container, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: 'rgba(148,163,184,0.12)' },
        horzLines: { color: 'rgba(148,163,184,0.12)' },
      },
      rightPriceScale: { borderColor: 'rgba(148,163,184,0.25)' },
      timeScale: { borderColor: 'rgba(148,163,184,0.25)' },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;
    const maSeries = maSeriesRef.current;
    const paneSeries = paneSeriesRef.current;

    // Phase 9 — the drawings primitive lives on pane 0, so it survives the
    // candlestick/line series rebuilds below untouched.
    const drawingsLayer = attachDrawingsLayer(chart, () => priceSeriesRef.current);
    drawingsLayerRef.current = drawingsLayer;

    const resize = () => chart.applyOptions({ width: container.clientWidth });
    resize();
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('resize', resize);
      drawingsLayerRef.current = null;
      drawingsLayer.detach();
      // `chart.remove()` tears down every series/pane on it in one call. The
      // other effects' series refs (overlay lines, markers, price lines,
      // indicator panes) are otherwise only cleared at the top of their own
      // next run -- in dev, React's double-invoke can re-run this cleanup and
      // remount before that happens, leaving those refs pointing at series
      // that belonged to the now-destroyed chart. Clearing them here too
      // means the next mount starts from a clean slate instead of trying to
      // `removeSeries` an object the (new) chart never created.
      chart.remove();
      chartRef.current = null;
      priceSeriesRef.current = null;
      maSeries.clear();
      overlaySeriesRef.current = [];
      markersRef.current = null;
      zoneLinesRef.current = [];
      paneSeries.clear();
    };
    // Chart instance is created once; `height` is applied by the effect below
    // so a height change never tears down (and blanks) the series.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Click-to-place drawing anchors and the crosshair readout/cursor preview.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const onCrosshairMove = (param: MouseEventParams<Time>) => {
      const tool = drawingToolRef.current;
      const draft = draftPointsRef.current;
      if (drawingsEnabledRef.current && tool && param.point) {
        if (draft.length > 0 && draft.length < DRAWING_REQUIRED_POINTS[tool]) {
          const time = (param.time ?? chart.timeScale().coordinateToTime(param.point.x)) as
            | UTCTimestamp
            | undefined;
          const price = priceSeriesRef.current?.coordinateToPrice(param.point.y);
          if (time != null && price != null) {
            setCursorPoint({ date: fromTime(time), price });
          } else {
            setCursorPoint(null);
          }
        } else {
          setCursorPoint(null);
        }
      } else {
        setCursorPoint(null);
      }

      if (!param.time) {
        setReadout(null);
        return;
      }
      const date = fromTime(param.time as UTCTimestamp);
      const { barByDate, indByDate } = readoutMapsRef.current;
      const bar = barByDate.get(date);
      const inds = indByDate.get(date) ?? {};
      const active = new Set(activePanesRef.current);
      const panes = PANE_ORDER.filter((id) => active.has(id) && inds[id] != null).map(
        (id) => ({ id, value: inds[id]! })
      );
      setReadout(panes.length > 0 || bar ? { date, bar: bar ?? null, panes } : null);
    };

    const onClick = (param: MouseEventParams<Time>) => {
      if (!drawingsEnabledRef.current) return;
      const tool = drawingToolRef.current;
      if (!tool || param.paneIndex !== 0 || !param.point) return;
      const time = (param.time ?? chart.timeScale().coordinateToTime(param.point.x)) as
        | UTCTimestamp
        | undefined;
      const price = priceSeriesRef.current?.coordinateToPrice(param.point.y);
      if (time == null || price == null) return;
      const point: DrawingPoint = { date: fromTime(time), price };

      const next = [...draftPointsRef.current, point];
      if (next.length >= DRAWING_REQUIRED_POINTS[tool]) {
        const drawing: ChartDrawing = {
          id: drawingId(),
          kind: tool,
          points: next,
          color: DRAWING_COLOR,
        };
        setDrawings((prev) => {
          const updated = [...prev, drawing];
          onDrawingsChangeRef.current?.(updated);
          return updated;
        });
        setDrawingTool(null);
        setDraftPoints([]);
        setCursorPoint(null);
      } else {
        setDraftPoints(next);
      }
    };

    chart.subscribeCrosshairMove(onCrosshairMove);
    chart.subscribeClick(onClick);
    return () => {
      chart.unsubscribeCrosshairMove(onCrosshairMove);
      chart.unsubscribeClick(onClick);
    };
    // Mounted once; everything stateful is read through the mirroring refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push the latest drawing/draft state into the pane primitive.
  const drawingsLayerRef = useRef<ReturnType<typeof attachDrawingsLayer> | null>(null);
  useEffect(() => {
    drawingsLayerRef.current?.update({
      drawings,
      draft: drawingTool && draftPoints.length ? draftPoints : null,
      cursor:
        drawingTool && draftPoints.length > 0 && draftPoints.length < DRAWING_REQUIRED_POINTS[drawingTool]
          ? cursorPoint
          : null,
    });
  }, [drawings, drawingTool, draftPoints, cursorPoint, height]);

  useEffect(() => {
    chartRef.current?.applyOptions({ height });
  }, [height]);

  // Price series (candlestick or close line).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (priceSeriesRef.current) {
      chart.removeSeries(priceSeriesRef.current);
      priceSeriesRef.current = null;
    }
    if (candlestick) {
      const series = chart.addSeries(CandlestickSeries, {
        upColor: '#10b981',
        downColor: '#ef4444',
        borderUpColor: '#10b981',
        borderDownColor: '#ef4444',
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
      });
      series.setData(parsed);
      priceSeriesRef.current = series;
    } else {
      const series = chart.addSeries(LineSeries, { color: '#6366f1', lineWidth: 2 });
      series.setData(parsed.map((p) => ({ time: p.time, value: p.close })));
      priceSeriesRef.current = series;
    }
    chart.timeScale().fitContent();
  }, [candlestick, parsed]);

  // MA overlays.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    for (const [period, series] of Array.from(maSeriesRef.current.entries())) {
      if (!activeMas.includes(period)) {
        chart.removeSeries(series);
        maSeriesRef.current.delete(period);
      }
    }
    for (const period of activeMas) {
      let series = maSeriesRef.current.get(period);
      if (!series) {
        series = chart.addSeries(LineSeries, {
          color: MA_COLORS[period],
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        maSeriesRef.current.set(period, series);
      }
      series.setData(maSeriesData.get(period) ?? []);
    }
  }, [activeMas, maSeriesData]);

  // Overlay polylines: a wave count connecting pivot to pivot (Phase 7), or the
  // several lines of a pattern's geometry (Phase 8).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    for (const series of overlaySeriesRef.current) chart.removeSeries(series);
    overlaySeriesRef.current = [];
    const lines: ChartOverlayLine[] = [
      ...(overlayLine?.length ? [{ points: overlayLine, color: overlayLine[0].color }] : []),
      ...(overlayLines ?? []),
    ].filter((line) => line.points.length > 1);
    overlaySeriesRef.current = lines.map((line) => {
      const series = chart.addSeries(LineSeries, {
        color: line.color ?? '#a855f7',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      const sorted = line.points
        .map((p) => ({ time: toTime(p.date), value: p.price }))
        .sort((a, b) => (a.time as number) - (b.time as number));
      // A single volatile bar can produce two pivots (its high and its low)
      // on the same calendar day, e.g. a wave count's swing labels -- the
      // chart can only place one point per day, so the later pivot (the
      // bar's more decisive extreme) wins and the series stays strictly
      // ascending, which lightweight-charts requires.
      const deduped = sorted.filter((p, i) => i === sorted.length - 1 || p.time !== sorted[i + 1].time);
      series.setData(deduped);
      return series;
    });
  }, [overlayLine, overlayLines]);

  // Wave-label markers pinned to the bar at their date.
  useEffect(() => {
    const series = priceSeriesRef.current;
    if (!series) return;
    const plugin = markersRef.current ?? createSeriesMarkers(series);
    markersRef.current = plugin;
    plugin.setMarkers(
      (markers ?? []).map((m) => ({
        time: toTime(m.date),
        position: m.position,
        color: m.color,
        shape: 'circle' as const,
        text: m.text,
      }))
    );
    return () => {
      markersRef.current?.detach();
      markersRef.current = null;
    };
  }, [markers, candlestick, parsed]);

  // Projection zone: dashed upper/lower bounds delimiting a range, never a
  // single price line — the projection is a range and is drawn as one.
  useEffect(() => {
    const series = priceSeriesRef.current;
    if (!series) return;
    for (const line of zoneLinesRef.current) series.removePriceLine(line);
    zoneLinesRef.current = [];
    if (!priceZone) return;
    zoneLinesRef.current = [
      { price: priceZone.high, title: `${priceZone.title} high` },
      { price: priceZone.low, title: `${priceZone.title} low` },
    ].map((bound) =>
      series.createPriceLine({
        price: bound.price,
        color: priceZone.color,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: bound.title,
      })
    );
  }, [priceZone, candlestick, parsed]);

  // Phase 9 — indicator sub-panes: create/remove panes and refresh their data.
  const activePanesRef = useRef<PaneId[]>(displayedPanes);
  useEffect(() => {
    activePanesRef.current = displayedPanes;
  });
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // Remove pane(s) that are no longer requested: dropping the last series on
    // a non-preserved pane removes the pane itself.
    for (const [id, record] of Array.from(paneSeriesRef.current.entries())) {
      if (!displayedPanes.includes(id)) {
        for (const series of record.series) chart.removeSeries(series);
        paneSeriesRef.current.delete(id);
      }
    }
    // Create the missing ones in canonical order so pane positions are stable.
    for (const id of PANE_ORDER) {
      if (!displayedPanes.includes(id) || paneSeriesRef.current.has(id)) continue;
      const pane = chart.addPane(false);
      const record: PaneRecord = { pane, series: [] };
      if (id === 'rsi') {
        const line = pane.addSeries(LineSeries, {
          color: PANE_COLORS.rsi,
          lineWidth: 1,
          priceLineVisible: false,
        });
        for (const level of [30, 70]) {
          line.createPriceLine({
            price: level,
            color: 'rgba(148,163,184,0.45)',
            lineStyle: LineStyle.Dashed,
            lineWidth: 1,
            title: '',
          });
        }
        record.series.push(line);
      } else if (id === 'macd') {
        record.series.push(
          pane.addSeries(HistogramSeries, {
            priceLineVisible: false,
            lastValueVisible: false,
            priceFormat: { type: 'volume' },
            priceScaleId: 'right',
            base: 0,
          })
        );
        record.series.push(
          pane.addSeries(LineSeries, {
            color: PANE_COLORS.macd,
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
          })
        );
        record.series.push(
          pane.addSeries(LineSeries, {
            color: MACD_SIGNAL_COLOR,
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
          })
        );
      } else {
        record.series.push(
          pane.addSeries(LineSeries, {
            color: PANE_COLORS.adx,
            lineWidth: 1,
            priceLineVisible: false,
          })
        );
      }
      paneSeriesRef.current.set(id, record);
    }
    // Re-balance pane heights (price dominates, sub-panes share the rests).
    chart.panes().forEach((p, index) => p.setStretchFactor(index === 0 ? 3 : 1));

    // Refresh each pane's data.
    for (const [id, record] of Array.from(paneSeriesRef.current.entries())) {
      if (id === 'rsi' || id === 'adx') {
        record.series[0]?.setData(paneData[id].line);
      } else {
        record.series[0]?.setData(paneData.macd.hist ?? []);
        record.series[1]?.setData(paneData.macd.line);
        record.series[2]?.setData(paneData.macd.signal ?? []);
      }
    }
  }, [displayedPanes, paneData]);

  const toggleMas = (period: number, on: boolean) => {
    const next = on
      ? [...activeMas, period].sort((a, b) => a - b)
      : activeMas.filter((p) => p !== period);
    setActiveMas(next);
    onActiveMasChange?.(next);
  };

  const togglePane = (id: PaneId) => {
    const next = displayedPanes.includes(id)
      ? displayedPanes.filter((p) => p !== id)
      : [...displayedPanes, id].sort((a, b) => PANE_ORDER.indexOf(a) - PANE_ORDER.indexOf(b));
    setDisplayedPanes(next);
  };

  const toggleDrawingTool = (kind: DrawingKind) => {
    setDrawingTool((prev) => (prev === kind ? null : kind));
    setDraftPoints([]);
    setCursorPoint(null);
  };

  const clearDrawings = () => {
    setDrawings((prev) => {
      onDrawingsChangeRef.current?.([]);
      return [];
    });
    setDraftPoints([]);
    setCursorPoint(null);
  };

  const showPaneControls = drawingsEnabled || indicatorSeries?.length;
  const activePaneSet = new Set(displayedPanes);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <div className="flex items-center gap-0.5 rounded-lg bg-slate-100 dark:bg-slate-800/60 p-0.5">
          {TIMEFRAMES.map((tf) => (
            <ToggleButton
              key={tf.id}
              active={timeframe === tf.id}
              onClick={() => onTimeframeChange(tf.id)}
            >
              {tf.label}
            </ToggleButton>
          ))}
        </div>
        <div className="flex items-center gap-0.5 rounded-lg bg-slate-100 dark:bg-slate-800/60 p-0.5">
          <ToggleButton active={candlestick} onClick={() => setCandlestick(true)}>
            Candles
          </ToggleButton>
          <ToggleButton active={!candlestick} onClick={() => setCandlestick(false)}>
            Line
          </ToggleButton>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-500">Moving averages</span>
          {MA_PERIODS.map((period) => (
            <label
              key={period}
              className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={activeMas.includes(period)}
                onChange={(e) => toggleMas(period, e.target.checked)}
                className="w-3 h-3 accent-indigo-500"
              />
              <span style={{ color: MA_COLORS[period] }}>MA{period}</span>
            </label>
          ))}
        </div>
        {showPaneControls && (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate-500">Indicators</span>
              {PANE_ORDER.map((id) => (
                <label
                  key={id}
                  className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={activePaneSet.has(id)}
                    disabled={!indicatorSeries?.length}
                    onChange={() => togglePane(id)}
                    className="w-3 h-3 accent-indigo-500"
                  />
                  <span style={{ color: PANE_COLORS[id] }}>{PANE_LABELS[id]}</span>
                </label>
              ))}
            </div>
            {drawingsEnabled && (
              <div className="flex items-center gap-1 flex-wrap">
                <span className="text-xs text-slate-500">Draw</span>
                {DRAWING_KINDS.map((kind) => (
                  <ToggleButton
                    key={kind}
                    active={drawingTool === kind}
                    onClick={() => toggleDrawingTool(kind)}
                  >
                    {DRAWING_LABELS[kind]}
                  </ToggleButton>
                ))}
                {drawings.length > 0 && (
                  <button
                    type="button"
                    onClick={clearDrawings}
                    className={`px-2 py-1 rounded-md text-xs font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 ${focusRing}`}
                  >
                    Clear
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
      <div className="relative">
        <div ref={containerRef} className="w-full" />
        {readout && (
          <div className="pointer-events-none absolute top-2 right-2 rounded-md border border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 px-2 py-1.5 text-[10px] leading-4 shadow-sm">
            <div className="font-medium text-slate-700 dark:text-slate-300">{readout.date}</div>
            {readout.bar && (
              <div className="text-slate-500 dark:text-slate-400 tabular-nums">
                O {readout.bar.open.toFixed(2)} · H {readout.bar.high.toFixed(2)} · L{' '}
                {readout.bar.low.toFixed(2)} · C {readout.bar.close.toFixed(2)}
              </div>
            )}
            {readout.panes.map((p) => (
              <div
                key={p.id}
                className="tabular-nums"
                style={{ color: PANE_COLORS[p.id] }}
              >
                {PANE_LABELS[p.id]}: {p.value.toFixed(p.id === 'macd' ? 3 : 2)}
              </div>
            ))}
          </div>
        )}
      </div>
      <p className="text-xs text-slate-500 mt-2">
        {isLoading
          ? 'Loading price series…'
          : (footnote ??
            `${bars.length} daily bars from the stored NSE series. Moving averages are simple rolling means of the closes shown.`)}
      </p>
    </div>
  );
}