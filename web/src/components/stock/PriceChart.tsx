'use client';

/**
 * Phase 6.2 — price chart bound to `GET /securities/{symbol}/ohlcv`.
 *
 * Every plotted value comes from a real bar (`open/high/low/close/volume`).
 * The MA overlays are plain rolling means over the *fetched close series* —
 * the backend exposes only a single latest value for sma50/150/200, and a
 * chart needs a full series, so the mean is computed here from backend bars
 * rather than invented. No pivots, no targets, no signal annotations.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { OHLCVBarDTO } from '@/lib/types';
import { focusRing } from '@/lib/theme';

export const TIMEFRAMES = [
  { id: '1W', label: '1W', days: 7 },
  { id: '1M', label: '1M', days: 30 },
  { id: '3M', label: '3M', days: 91 },
  { id: '6M', label: '6M', days: 182 },
  { id: '1Y', label: '1Y', days: 365 },
  { id: 'MAX', label: 'MAX', days: null },
] as const;

export type TimeframeId = (typeof TIMEFRAMES)[number]['id'];

const MA_PERIODS = [10, 20, 50, 100, 200] as const;
const MA_COLORS: Record<number, string> = {
  10: '#f59e0b',
  20: '#10b981',
  50: '#6366f1',
  100: '#ec4899',
  200: '#94a3b8',
};

function toTime(isoDate: string): UTCTimestamp {
  return (Date.parse(`${isoDate}T00:00:00Z`) / 1000) as UTCTimestamp;
}

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

export function PriceChart({
  bars,
  timeframe,
  onTimeframeChange,
  isLoading = false,
  height = 380,
  footnote,
  markers,
  overlayLine,
  priceZone,
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
  priceZone?: ChartPriceZone | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const priceSeriesRef = useRef<ISeriesApi<'Candlestick'> | ISeriesApi<'Line'> | null>(null);
  const maSeriesRef = useRef<Map<number, ISeriesApi<'Line'>>>(new Map());
  const overlaySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const zoneLinesRef = useRef<IPriceLine[]>([]);
  const [candlestick, setCandlestick] = useState(true);
  const [activeMas, setActiveMas] = useState<number[]>([50, 200]);

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
    const resize = () => chart.applyOptions({ width: container.clientWidth });
    resize();
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('resize', resize);
      chart.remove();
      chartRef.current = null;
      priceSeriesRef.current = null;
      maSeries.clear();
    };
    // Chart instance is created once; `height` is applied by the effect below
    // so a height change never tears down (and blanks) the series.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // Overlay polyline (e.g. a wave count connecting pivot to pivot).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (overlaySeriesRef.current) {
      chart.removeSeries(overlaySeriesRef.current);
      overlaySeriesRef.current = null;
    }
    if (!overlayLine?.length) return;
    const series = chart.addSeries(LineSeries, {
      color: overlayLine[0].color ?? '#a855f7',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    series.setData(overlayLine.map((p) => ({ time: toTime(p.date), value: p.price })));
    overlaySeriesRef.current = series;
  }, [overlayLine]);

  // Wave-label markers pinned to their pivot bars.
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
                onChange={(e) =>
                  setActiveMas((prev) =>
                    e.target.checked ? [...prev, period] : prev.filter((p) => p !== period)
                  )
                }
                className="w-3 h-3 accent-indigo-500"
              />
              <span style={{ color: MA_COLORS[period] }}>MA{period}</span>
            </label>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="w-full" />
      <p className="text-xs text-slate-500 mt-2">
        {isLoading
          ? 'Loading price series…'
          : (footnote ??
            `${bars.length} daily bars from the stored NSE series. Moving averages are simple rolling means of the closes shown.`)}
      </p>
    </div>
  );
}
