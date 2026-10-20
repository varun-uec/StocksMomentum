/**
 * Phase 6.2 — price chart bound to `GET /securities/{symbol}/ohlcv`.
 *
 * Every plotted value comes from a real bar (`open/high/low/close/volume`).
 * The MA overlays are plain rolling means over the stored closes (`maWarmup`
 * carries the closes before the range, so MA200 spans a 1Y chart) —
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

import { InspectorDisclosure } from '@/components/workspace/InspectorDisclosure';
import { useTheme } from '@/app/theme-provider';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  AreaSeries,
  BarSeries,
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  PriceScaleMode,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPaneApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type LineWidth,
  type MouseEventParams,
  type IRange,
  type BarPrice,
  type SeriesType,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { ChartInterval, OHLCVBarDTO } from '@/lib/types';
import { CHART_TYPES, heikinAshi, type ChartType, type PriceScale } from '@/components/stock/chart-types';
import { ChartMenu, DrawingMenu } from '@/components/stock/DrawingMenu';
import { barAtOrAfter, type CrosshairSync } from '@/lib/crosshair-sync';
import { focusRing } from '@/lib/theme';
import {
  DRAWING_COLOR,
  DRAWING_KINDS,
  DRAWING_LABELS,
  DRAWING_REQUIRED_POINTS,
  TEXT_KINDS,
  applyDrawingChanges,
  attachDrawingsLayer,
  diffDrawings,
  type DrawingChange,
  type PriceSeries,
  HANDLE_RADIUS,
  drawingId,
  fromTime,
  hitTestAll,
  moveDrawing,
  toTime,
  type ChartDrawing,
  type DrawingKind,
  type DrawingPart,
  type DrawingPoint,
  type ScreenPoint,
} from '@/components/stock/chart-drawings';
import type { LegendEntry } from '@/components/stock/OverlayPicker';
import { sma } from '@/lib/indicators/overlays';

export const TIMEFRAMES = [
  { id: '1W', label: '1W', days: 7 },
  { id: '1M', label: '1M', days: 30 },
  { id: '3M', label: '3M', days: 91 },
  { id: '6M', label: '6M', days: 182 },
  { id: '1Y', label: '1Y', days: 365 },
  { id: 'MAX', label: 'MAX', days: null },
] as const;

export type TimeframeId = (typeof TIMEFRAMES)[number]['id'];

/**
 * Page-level places for this chart's chrome (plan 2026-10-19, "chart chrome
 * slots"). The workspace passes them to the active chart only, so one rail acts
 * on the active chart. State stays in the chart; only the rendering moves.
 */
export interface ChartChrome {
  /** The page's drawing-rail column. */
  rail: HTMLElement | null;
  /** The toolbar place for the interval. */
  toolbar?: HTMLElement | null;
  /** The toolbar place for the chart type. */
  chartType?: HTMLElement | null;
  /** The toolbar place for undo, redo and the drawing objects. */
  history?: HTMLElement | null;
  /** The toolbar place for the settings gear: volume, moving averages, panes. */
  settings?: HTMLElement | null;
  /** The bottom range bar: ranges, scale and Fit. */
  rangeBar?: HTMLElement | null;
  /** The Object tree panel tab: the drawings list with show/hide and lock. */
  objects?: HTMLElement | null;
  /** A change (a new layout) cancels an armed tool. */
  resetKey?: string;
}

/** A temporary "Show on chart" layer from the Assessment: moving averages, never saved. */
export interface EvidenceLayer {
  /** The criterion it shows, e.g. "tt_sma200_uptrend". */
  id: string;
  label: string;
  periods: number[];
}

const UNDO_ICON = (
  <svg viewBox="0 0 20 20" className="w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 5L3 9l4 4M3 9h9a5 5 0 010 10h-2" />
  </svg>
);
const UNDO_ICON_REDO = (
  <svg viewBox="0 0 20 20" className="w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M13 5l4 4-4 4M17 9H8a5 5 0 000 10h2" />
  </svg>
);

const SETTINGS_ICON = (
  <svg viewBox="0 0 20 20" className="w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="10" cy="10" r="2.5" />
    <path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4" strokeLinecap="round" />
  </svg>
);

/** Evidence layers share one colour, so they read as one temporary kind. */
const EVIDENCE_COLOR = '#d97706';

/** Counts chart instances, so a test can prove activation never rebuilds one. */
let chartGeneration = 0;

/** Drawing-tool shortcuts, by `KeyboardEvent.code` (letters stay the same on any layout and with Alt on macOS). */
const TOOL_KEYS: Record<string, DrawingKind> = {
  KeyT: 'trendline',
  KeyH: 'horizontal',
  KeyV: 'vline',
  'Shift+KeyR': 'rectangle',
  KeyF: 'fib',
};

/** Shortcut hint shown on the rail buttons that have one. */
const TOOL_HINT: Partial<Record<DrawingKind, string>> = {
  trendline: 'Alt+T',
  horizontal: 'Alt+H',
  rectangle: 'Alt+Shift+R',
  fib: 'Alt+F',
  vline: 'Alt+V',
};

const RAIL_ICONS: Record<DrawingKind | 'select' | 'clear', React.ReactNode> = {
  select: <path d="M5 3l10 6-4.5 1.2L13 16l-2 1-2.5-5.8L5 14z" fill="currentColor" />,
  trendline: <path d="M4 16L16 4M4 16h0M16 4h0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  ray: <path d="M4 16L18 2M4 16h0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  extended: <path d="M2 18L18 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  horizontal: <path d="M3 10h14M6 10h0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  hline: <path d="M1 10h18" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  vline: <path d="M10 1v18" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  crossline: <path d="M1 10h18M10 1v18" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />,
  channel: <path d="M3 12L15 4M5 17L17 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />,
  price_range: <path d="M10 3v14M6 6l4-3 4 3M6 14l4 3 4-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />,
  text: <path d="M4 5h12M10 5v11M7 16h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  rectangle: <rect x="4" y="5" width="12" height="10" rx="1" fill="none" stroke="currentColor" strokeWidth="1.6" />,
  fib: <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />,
  arrow: <path d="M4 16L16 4M16 4h-6M16 4v6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />,
  date_range: <path d="M3 4v12M17 4v12M5 10h10M8 7l-3 3 3 3M12 7l3 3-3 3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  date_price_range: <path d="M3 3h14v14H3zM5 10h10M10 5v10" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />,
  ellipse: <ellipse cx="10" cy="10" rx="7" ry="5" fill="none" stroke="currentColor" strokeWidth="1.6" />,
  triangle: <path d="M10 3l7 13H3z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />,
  fib_extension: <path d="M3 16L8 6l4 6M12 4h6M12 8h6M12 12h6M12 16h6" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />,
  pitchfork: <path d="M2 14L18 6M6 18L18 12M2 8l14-6M6 18L2 8" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />,
  callout: <path d="M3 17l4-5M7 4h10v8H7z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />,
  price_label: <path d="M3 10l4-5h10v10H7z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />,
  clear: <path d="M6 6l1 11h6l1-11M4 6h12M8 6V4h4v2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />,
};

/** The rail's tool groups, in TradingView's order (plan 2026-10-19, step 4). */
const TOOL_GROUPS: { name: string; tools: DrawingKind[] }[] = [
  { name: 'Lines', tools: ['trendline', 'ray', 'extended', 'hline', 'horizontal', 'vline', 'crossline', 'channel', 'pitchfork'] },
  { name: 'Fibonacci', tools: ['fib', 'fib_extension'] },
  { name: 'Shapes', tools: ['rectangle', 'ellipse', 'triangle'] },
  { name: 'Annotation', tools: ['text', 'callout', 'price_label', 'arrow'] },
  { name: 'Measure', tools: ['price_range', 'date_range', 'date_price_range'] },
];

/** Each group's last-used tool. Shared by every chart, so it survives a change of active chart. */
const lastTool: Record<string, DrawingKind> = Object.fromEntries(TOOL_GROUPS.map((g) => [g.name, g.tools[0]]));

/**
 * The drawing tools as a column left of the chart (design record D6). Each
 * group button shows its last-used tool; its corner arrow opens a flyout of the
 * group. `collapsible` turns the rail into one "Draw" button below 640 px.
 */
function DrawingRail({
  tool,
  onTool,
  canClear,
  onClear,
  collapsible = false,
}: {
  tool: DrawingKind | null;
  onTool: (kind: DrawingKind | null) => void;
  canClear: boolean;
  onClear: () => void;
  collapsible?: boolean;
}) {
  const [flyout, setFlyout] = useState<{ group: string; left: number; top: number } | null>(null);
  const [drawOpen, setDrawOpen] = useState(false);
  const flyoutRef = useRef<HTMLDivElement>(null);
  const arrowRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  if (tool) for (const g of TOOL_GROUPS) if (g.tools.includes(tool)) lastTool[g.name] = tool;

  useEffect(() => {
    if (!flyout) return;
    flyoutRef.current?.querySelector<HTMLElement>('[aria-pressed="true"], button')?.focus();
    const close = (e: PointerEvent) => {
      if (!flyoutRef.current?.contains(e.target as Node) && !arrowRefs.current[flyout.group]?.contains(e.target as Node)) setFlyout(null);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [flyout]);

  const pick = (kind: DrawingKind | null) => {
    setFlyout(null);
    setDrawOpen(false);
    onTool(kind);
  };
  const toolTitle = (kind: DrawingKind) => (TOOL_HINT[kind] ? `${DRAWING_LABELS[kind]} (${TOOL_HINT[kind]})` : DRAWING_LABELS[kind]);
  const iconClass = (active: boolean, danger = false) =>
    `w-8 h-8 flex items-center justify-center rounded-md transition-colors ${focusRing} ${
      active
        ? 'bg-indigo-100 dark:bg-indigo-600/25 text-indigo-700 dark:text-indigo-300'
        : danger
          ? 'text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40'
          : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
    }`;
  const icon = (key: keyof typeof RAIL_ICONS) => (
    <svg viewBox="0 0 20 20" className="w-4 h-4" aria-hidden="true">
      {RAIL_ICONS[key]}
    </svg>
  );
  const openFlyout = (group: string) => {
    if (flyout?.group === group) return setFlyout(null);
    const box = arrowRefs.current[group]!.getBoundingClientRect();
    // Keep the flyout on screen: the phone sheet sits at the bottom edge.
    const height = TOOL_GROUPS.find((g) => g.name === group)!.tools.length * 32 + 10;
    setFlyout({ group, left: Math.min(box.right + 4, window.innerWidth - 208), top: Math.max(8, Math.min(box.top - 4, window.innerHeight - 8 - height)) });
  };
  const onFlyoutKey = (e: React.KeyboardEvent) => {
    const items = [...(flyoutRef.current?.querySelectorAll<HTMLElement>('button') ?? [])];
    const at = items.indexOf(document.activeElement as HTMLElement);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      items[(at + (e.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length]?.focus();
    } else if (e.key === 'Escape') {
      e.stopPropagation();
      const group = flyout!.group;
      setFlyout(null);
      arrowRefs.current[group]?.focus();
    }
  };
  const open = TOOL_GROUPS.find((g) => g.name === flyout?.group);
  // The open phone sheet leaves the rail's stacking context, so it sits above the bottom nav.
  const sheet = (toolbar: React.ReactNode) => (collapsible && drawOpen ? createPortal(toolbar, document.body) : toolbar);

  return (
    <>
      {collapsible && (
        <button type="button" aria-expanded={drawOpen} onClick={() => setDrawOpen((v) => !v)} className={`chart-draw-button sm:hidden ${iconClass(drawOpen || tool !== null)}`} title="Drawing tools">
          <span className="sr-only">Draw</span>
          {icon('trendline')}
        </button>
      )}
      {sheet(
      <div
        role="toolbar"
        aria-label="Drawing tools"
        aria-orientation="vertical"
        className={`flex-col gap-1 pt-1 ${collapsible ? (drawOpen ? 'chart-draw-sheet flex' : 'hidden sm:flex') : 'flex'}`}
      >
        <button type="button" onClick={() => pick(null)} aria-label="Select" aria-pressed={tool === null} title="Select (Esc)" className={iconClass(tool === null)}>
          {icon('select')}
        </button>
        {TOOL_GROUPS.map((group) => {
          const shown = lastTool[group.name];
          return (
            <span key={group.name} className="relative inline-flex">
              <button type="button" onClick={() => pick(shown === tool ? null : shown)} aria-label={DRAWING_LABELS[shown]} aria-pressed={tool === shown} title={toolTitle(shown)} className={iconClass(tool === shown)}>
                {icon(shown)}
              </button>
              {group.tools.length > 1 && (
                <button
                  ref={(el) => { arrowRefs.current[group.name] = el; }}
                  type="button"
                  aria-label={`${group.name} tools`}
                  aria-expanded={flyout?.group === group.name}
                  aria-haspopup="true"
                  onClick={() => openFlyout(group.name)}
                  className={`chart-rail-arrow ${focusRing}`}
                >
                  <svg viewBox="0 0 6 6" aria-hidden="true"><path d="M6 0v6H0z" fill="currentColor" /></svg>
                </button>
              )}
            </span>
          );
        })}
        {canClear && (
          <>
            <span aria-hidden="true" className="chart-rail-sep" />
            <button type="button" onClick={() => { setDrawOpen(false); onClear(); }} aria-label="Remove objects" title="Remove objects" className={iconClass(false, true)}>
              {icon('clear')}
            </button>
          </>
        )}
      </div>,
      )}
      {open && flyout && createPortal(
        <div ref={flyoutRef} role="group" aria-label={`${open.name} tools`} onKeyDown={onFlyoutKey} className="chart-rail-flyout" style={{ left: flyout.left, top: flyout.top }}>
          {open.tools.map((kind) => (
            <button key={kind} type="button" aria-label={DRAWING_LABELS[kind]} aria-keyshortcuts={TOOL_HINT[kind]} aria-pressed={tool === kind} onClick={() => pick(kind)} className={`chart-rail-flyout-item ${focusRing}`}>
              {icon(kind)}
              <span className="flex-1 text-left">{DRAWING_LABELS[kind]}</span>
              {TOOL_HINT[kind] && <kbd className="text-[10px] text-slate-500">{TOOL_HINT[kind]}</kbd>}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </>
  );
}

/** The bar interval, separate from the visible range (M11b). */
const INTERVALS: { id: ChartInterval; label: string; name: string }[] = [
  { id: '1D', label: 'D', name: 'Daily bars' },
  { id: '1W', label: 'W', name: 'Weekly bars' },
  { id: '1M', label: 'M', name: 'Monthly bars' },
];

/**
 * Phase 9 — indicator sub-panes.
 *
 * A pane is data: which fields of `indicatorSeries` it draws, in which order,
 * with which colours and guide lines. The pane effect below loops the registry
 * instead of branching per pane, so a new pane is one `PaneDef`, not a fourth
 * `else if`. Callers may pass extra defs through `extraPaneDefs`; the built-in
 * checkbox row still lists only the three backend-fed panes.
 */
export type PaneId = string;

export interface PaneSeriesDef {
  /** Field of `IndicatorSeriesBar` this series draws. */
  key: string;
  type: 'line' | 'histogram';
  color?: string;
  /** Default is the library default (`true`); MACD's lines set it false. */
  lastValueVisible?: boolean;
  /**
   * Histogram bar colouring by sign. `key` defaults to the series' own field,
   * so MACD colours its histogram by its own value.
   */
  sign?: { key?: string; positive: string; negative: string };
}

export interface PaneDef {
  id: PaneId;
  label: string;
  series: PaneSeriesDef[];
  /** Dashed horizontal levels, e.g. RSI's 30 / 70. */
  guides?: { value: number; label?: string }[];
  /** Crosshair-readout formatting of the pane's first line series. */
  format?: (v: number) => string;
}

const MACD_SIGNAL_COLOR = '#b45309';
const MACD_HIST_POSITIVE = 'rgba(16,185,129,0.45)';
const MACD_HIST_NEGATIVE = 'rgba(239,68,68,0.45)';

const GUIDE_COLOR = 'rgba(148,163,184,0.45)';
const fixed2 = (v: number) => v.toFixed(2);

/** The three backend-fed panes, in their fixed chart order. */
export const PANE_DEFS: PaneDef[] = [
  {
    id: 'rsi',
    label: 'RSI (14)',
    series: [{ key: 'rsi14', type: 'line', color: '#b45309' }],
    guides: [{ value: 30 }, { value: 70 }],
    format: fixed2,
  },
  {
    id: 'macd',
    label: 'MACD (12,26,9)',
    series: [
      {
        key: 'macd_histogram',
        type: 'histogram',
        sign: { positive: MACD_HIST_POSITIVE, negative: MACD_HIST_NEGATIVE },
      },
      { key: 'macd_line', type: 'line', color: '#4f46e5', lastValueVisible: false },
      { key: 'macd_signal', type: 'line', color: MACD_SIGNAL_COLOR, lastValueVisible: false },
    ],
    format: (v) => v.toFixed(3),
  },
  {
    id: 'adx',
    label: 'ADX (14)',
    series: [{ key: 'adx14', type: 'line', color: '#7e22ce' }],
    format: fixed2,
  },
];

/**
 * Volume is read off `bars`, not off `indicatorSeries`, so it is registered
 * separately from the three backend-fed panes and never appears in their
 * checkbox row.
 */
const VOLUME_PANE: PaneDef = {
  id: 'volume',
  label: 'Volume',
  series: [
    {
      key: 'volume',
      type: 'histogram',
      sign: { key: 'volume_direction', positive: 'rgba(16,185,129,0.45)', negative: 'rgba(239,68,68,0.45)' },
    },
  ],
  format: (v) => v.toLocaleString(),
};

/** The colour a pane is identified by (its first line series). */
export function paneColor(def: PaneDef): string {
  return def.series.find((s) => s.type === 'line')?.color ?? '#94a3b8';
}

/** Half the 17 px last-price label, half the 12 px tick font and a 2.5 px gap: tick label centres nearer than this are hidden. */
const LAST_PRICE_LABEL_CLEARANCE = 17;

/**
 * Blank the price-axis tick labels the last-price label would cover, as
 * TradingView does. The library draws every tick label and paints the label
 * over them, so a near tick showed half its digits. Tick positions and every
 * other label keep the library's own formatting.
 */
function hideTicksUnderLastPrice(series: ISeriesApi<SeriesType>): void {
  const base = series.priceFormatter();
  series.applyOptions({
    priceFormat: {
      type: 'custom',
      minMove: 0.01,
      formatter: (price: BarPrice) => base.format(price),
      tickmarksFormatter: (prices: BarPrice[]) => {
        const last = series.lastValueData(true);
        const labelY = last.noData ? null : series.priceToCoordinate(last.price);
        return prices.map((price) => {
          const y = series.priceToCoordinate(price);
          const covered = labelY !== null && y !== null && Math.abs(y - labelY) < LAST_PRICE_LABEL_CLEARANCE;
          return covered ? '' : base.format(price);
        });
      },
    },
  });
}

/** The field whose value the crosshair readout shows for a pane. */
function paneReadoutKey(def: PaneDef): string | null {
  return def.series.find((s) => s.type === 'line')?.key ?? null;
}

export const PANE_LABELS: Record<PaneId, string> = Object.fromEntries(
  PANE_DEFS.map((d) => [d.id, d.label])
);

/**
 * One bar of the indicator series (Phase 9). The named fields are what the
 * backend supplies; the index signature lets a caller merge extra per-bar
 * values for its own `extraPaneDefs` into the same array.
 */
export interface IndicatorSeriesBar {
  date: string;
  rsi14?: number | null;
  atr14?: number | null;
  adx14?: number | null;
  macd_line?: number | null;
  macd_signal?: number | null;
  macd_histogram?: number | null;
  [key: string]: number | string | null | undefined;
}

const MA_PERIODS = [10, 20, 50, 100, 200] as const;
const MA_COLORS: Record<number, string> = {
  10: '#b45309',
  20: '#047857',
  50: '#4f46e5',
  100: '#be185d',
  200: '#475569',
};

function ToggleButton({
  active,
  onClick,
  children,
  ariaLabel,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  ariaLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={ariaLabel}
      title={ariaLabel}
      className={`px-2 py-1 rounded-md text-xs font-medium transition-colors ${focusRing} ${
        active
          ? 'bg-indigo-100 dark:bg-indigo-600/25 text-indigo-700 dark:text-indigo-300'
          : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
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
  /** Marker radius relative to the default (subwave markers are smaller). */
  size?: number;
  shape?: 'circle' | 'square';
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
  /** Comparison returns may use independent percentage bases; price studies may not. */
  percentSafe?: boolean;
  points: { date: string; price: number }[];
  color?: string;
  /** Overrides the default 2px overlay stroke (subwave lines are thinner). */
  lineWidth?: LineWidth;
  lineStyle?: LineStyle;
}

interface PaneRecord {
  pane: IPaneApi<Time>;
  series: ISeriesApi<'Line' | 'Histogram'>[];
}

/** Values shown in the crosshair readout at the hovered bar. */
interface CrosshairReadout {
  date: string;
  bar: { open: number; high: number; low: number; close: number } | null;
  panes: { id: PaneId; label: string; color: string; value: string }[];
}

export function PriceChart({
  bars,
  maWarmup,
  timeframe,
  onTimeframeChange,
  interval = '1D',
  onIntervalChange,
  dataVersion,
  chartType: chartTypeProp,
  onChartTypeChange,
  scale: scaleProp,
  onScaleChange,
  onOpenIndicators,
  onAlertAtPrice,
  onAlertOnDrawing,
  replayDate,
  chrome,
  legendTitle,
  legendChip,
  evidenceLayers,
  onRemoveEvidence,
  bare = false,
  compact = false,
  chartLabel,
  crosshairSync,
  isLoading = false,
  height: requestedHeight = 380,
  autoHeight = false,
  footnote,
  markers,
  overlayLine,
  overlayLines,
  studyLegend,
  alertLevels,
  priceZone,
  visibleRange,
  initialWindow,
  indicatorSeries,
  activePanes,
  onActivePanesChange,
  extraPaneDefs,
  activeMas: activeMasProp,
  onActiveMasChange,
  drawingsEnabled = false,
  toolRail = true,
  drawingsKey,
  drawings: drawingsProp,
  onDrawingsChange,
}: {
  bars: OHLCVBarDTO[];
  /** Closes just before `bars`, so a moving average starts on the first bar shown. */
  maWarmup?: number[];
  timeframe: TimeframeId;
  onTimeframeChange: (id: TimeframeId) => void;
  /** Daily, weekly or monthly bars. The switch shows only when `onIntervalChange` is given. */
  interval?: ChartInterval;
  onIntervalChange?: (interval: ChartInterval) => void;
  /** The series' data version, shown in the footnote (ADR-013 §4). */
  dataVersion?: string;
  /** Candles, bars, line, area or Heikin-Ashi; controlled when the handler is given. */
  chartType?: ChartType;
  onChartTypeChange?: (type: ChartType) => void;
  /** Normal, log or percent price scale; controlled when the handler is given. */
  scale?: PriceScale;
  onScaleChange?: (scale: PriceScale) => void;
  /** Adds "Indicators…" to the chart's context menu. */
  onOpenIndicators?: () => void;
  /** Adds "Alert at this price…" to the chart's context menu (M15). */
  onAlertAtPrice?: (price: number) => void;
  /** "Alert on this line…" from a drawing's menu: arm an EOD alert on the saved drawing. */
  onAlertOnDrawing?: (drawingId: string) => void;
  /**
   * Bar replay (plan B2): the bars already stop at this date. While it is set the
   * newest bar stays in view; clearing it restores the viewport from before replay.
   */
  replayDate?: string;
  /** Render the chrome into page slots instead of inline (the active workspace chart). */
  chrome?: ChartChrome;
  /** No controls of its own: the workspace toolbar acts on it when it is active (grid cells). */
  bare?: boolean;
  /** A Momentum25 chip after the legend title, e.g. "#3 · Qualified". */
  legendChip?: React.ReactNode;
  /** Temporary evidence layers (never saved); a saved MA of the same period is highlighted instead. */
  evidenceLayers?: EvidenceLayer[];
  onRemoveEvidence?: (id: string) => void;
  /** The overlay legend's first words, e.g. "RELIANCE · 1D · NSE" (workstation only). */
  legendTitle?: string;
  /** Compact grid toolbar; optional active-cell drawing rail; no legend or footnote. */
  compact?: boolean;
  chartLabel?: React.ReactNode;
  /** Shares the crosshair date with the other charts of a layout. */
  crosshairSync?: CrosshairSync;
  isLoading?: boolean;
  /** Chart height in px; the Elliott Wave screen renders a much taller chart. */
  height?: number;
  /** Fit the plot to its `[data-plot-cell]` ancestor, after the chart's own controls and footnote. */
  autoHeight?: boolean;
  footnote?: string;
  markers?: ChartMarker[];
  /** Polyline through arbitrary (date, price) points, e.g. a wave count. */
  overlayLine?: { date: string; price: number; color?: string }[];
  /** Several independent polylines, e.g. the two trendlines of a triangle. */
  overlayLines?: ChartOverlayLine[];
  studyLegend?: LegendEntry[];
  alertLevels?: { price: number; title: string }[];
  /** Dashed bounds delimiting a projected range (Elliott Wave research only). */
  priceZone?: ChartPriceZone | null;
  /**
   * Date window to scroll the chart to, e.g. the span of one selected wave.
   * Setting it back to `null` returns the chart to the full loaded range.
   */
  visibleRange?: { from: string; to: string } | null;
  /** Preset viewport over full history; panning remains unrestricted. */
  initialWindow?: { from: string; to: string };
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
  /**
   * Panes beyond the three backend-fed ones. Their series read the same
   * `indicatorSeries` array, so the caller merges its own per-bar values in.
   * They are never listed in this toolbar's checkbox row — the caller owns
   * their on/off UI.
   */
  extraPaneDefs?: PaneDef[];
  /**
   * Moving averages to show. Controlled by the parent when supplied, so a merge
   * from another window shows up; else the chart keeps its own default.
   */
  activeMas?: number[];
  onActiveMasChange?: (mas: number[]) => void;
  /** Show the drawing toolbar and accept clicks while a tool is active. */
  drawingsEnabled?: boolean;
  /** Put the drawing tools in a rail left of the chart instead of the toolbar row (M12). */
  toolRail?: boolean;
  /** Whose drawings these are (the symbol). Undo history starts afresh when it changes. */
  drawingsKey?: string;
  /** The saved drawings. The chart follows this prop, so merges from another window show up. */
  drawings?: ChartDrawing[];
  onDrawingsChange?: (drawings: ChartDrawing[]) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const navigationRangeRef = useRef<{ from: number; to: number } | null>(null);
  const priceSeriesRef = useRef<PriceSeries | null>(null);
  const maSeriesRef = useRef<Map<number, ISeriesApi<'Line'>>>(new Map());
  const evidenceSeriesRef = useRef<Map<number, ISeriesApi<'Line'>>>(new Map());
  const overlaySeriesRef = useRef<ISeriesApi<'Line'>[]>([]);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const zoneLinesRef = useRef<IPriceLine[]>([]);
  const paneSeriesRef = useRef<Map<PaneId, PaneRecord>>(new Map());
  const [internalType, setInternalType] = useState<ChartType>('candles');
  const chartType = chartTypeProp ?? internalType;
  const setChartType = (type: ChartType) => (onChartTypeChange ? onChartTypeChange(type) : setInternalType(type));
  const [internalScale, setInternalScale] = useState<PriceScale>('normal');
  const scale = scaleProp ?? internalScale;
  const setScale = (next: PriceScale) => (onScaleChange ? onScaleChange(next) : setInternalScale(next));
  const [internalMas, setInternalMas] = useState<number[]>([50, 200]);
  const activeMas = activeMasProp ?? internalMas;
  const barWord = { '1D': 'daily', '1W': 'weekly', '1M': 'monthly' }[interval];
  const { resolvedTheme } = useTheme();
  const maColors = useMemo(() => resolvedTheme === 'dark' ? { 10: '#fbbf24', 20: '#34d399', 50: '#a5b4fc', 100: '#f9a8d4', 200: '#b6c5d0' } as Record<number, string> : MA_COLORS, [resolvedTheme]);
  const [fittedHeight, setFittedHeight] = useState(requestedHeight);
  const height = autoHeight ? fittedHeight : requestedHeight;
  const [drawingTool, setDrawingTool] = useState<DrawingKind | null>(null);
  const [draftPoints, setDraftPoints] = useState<DrawingPoint[]>([]);
  const [cursorPoint, setCursorPoint] = useState<DrawingPoint | null>(null);
  // Rendered drawings: the prop, or a live preview while one is being dragged.
  const [drawings, setDrawings] = useState<ChartDrawing[]>(drawingsProp ?? []);
  useEffect(() => setDrawings(drawingsProp ?? []), [drawingsProp]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => { if (drawings.find((d) => d.id === selectedId)?.hidden) setSelectedId(null); }, [drawings, selectedId]);
  const [readout, setReadout] = useState<CrosshairReadout | null>(null);
  const [noteEditor, setNoteEditor] = useState<{ drawing: ChartDrawing; x: number; y: number } | null>(null);
  const [showVolume, setShowVolume] = useState(false);

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
  const drawingsRef = useRef(drawings);
  const barDatesRef = useRef<string[]>([]);
  const crosshairSyncRef = useRef(crosshairSync);
  useEffect(() => {
    drawingsEnabledRef.current = drawingsEnabled;
    crosshairSyncRef.current = crosshairSync;
    drawingToolRef.current = drawingTool;
    draftPointsRef.current = draftPoints;
    onDrawingsChangeRef.current = onDrawingsChange;
    drawingsRef.current = drawings;
    barDatesRef.current = bars.map((b) => b.date);
  });

  /** Show and save a new drawing list. The ref moves at once, so an event that
   * arrives before React re-renders still sees the new list. */
  // Undo history: per-drawing changes, so undo never reverts another window's edit.
  const historyRef = useRef<{ past: DrawingChange[][]; future: DrawingChange[][] }>({ past: [], future: [] });
  useEffect(() => {
    historyRef.current = { past: [], future: [] };
    drawingToolRef.current = null;
    draftPointsRef.current = [];
    setDrawingTool(null);
    setDraftPoints([]);
    setCursorPoint(null);
    setSelectedId(null);
    setNoteEditor(null);
    setMenu(null);
  }, [drawingsKey]);

  const commitDrawings = (next: ChartDrawing[], record = true) => {
    if (record) {
      const changes = diffDrawings(drawingsRef.current, next);
      if (changes.length) historyRef.current = { past: [...historyRef.current.past.slice(-99), changes], future: [] };
    }
    drawingsRef.current = next;
    setDrawings(next);
    onDrawingsChangeRef.current?.(next);
  };

  /** Step back ('before') or forward ('after') through this window's drawing edits. */
  const stepHistory = (side: 'before' | 'after') => {
    const { past, future } = historyRef.current;
    const changes = side === 'before' ? past.at(-1) : future.at(-1);
    if (!changes) return;
    historyRef.current =
      side === 'before'
        ? { past: past.slice(0, -1), future: [...future, changes] }
        : { past: [...past, changes], future: future.slice(0, -1) };
    commitDrawings(applyDrawingChanges(drawingsRef.current, changes, side), false);
  };

  /** An open context menu: a drawing's (`id`) or the chart's (`id` null). */
  const [menu, setMenu] = useState<{ id: string | null; x: number; y: number } | null>(null);

  /** Arm or disarm a drawing tool, dropping any half-placed anchors. */
  const selectTool = (tool: DrawingKind | null) => {
    drawingToolRef.current = tool;
    draftPointsRef.current = [];
    setDrawingTool(tool);
    setDraftPoints([]);
    setCursorPoint(null);
  };

  // A chart that loses the page's rail, or whose layout changes, drops its armed tool.
  const railSlot = chrome?.rail ?? null;
  useEffect(() => { selectTool(null); }, [railSlot, chrome?.resetKey]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const evidenceKey = (evidenceLayers ?? []).flatMap((l) => l.periods).sort((a, b) => a - b).join(',');
  const evidencePeriods = useMemo(() => new Set(evidenceKey ? evidenceKey.split(',').map(Number) : []), [evidenceKey]);

  const maSeriesData = useMemo(() => {
    const warmup = maWarmup ?? [];
    const closes = [...warmup, ...parsed.map((p) => p.close)];
    const result = new Map<number, { time: UTCTimestamp; value: number }[]>();
    for (const period of MA_PERIODS) {
      const means = sma(closes, period).slice(warmup.length);
      result.set(
        period,
        parsed
          .map((p, i) => ({ time: p.time, value: means[i] }))
          .filter((p): p is { time: UTCTimestamp; value: number } => p.value !== null)
      );
    }
    return result;
  }, [parsed, maWarmup]);

  // One definition per pane id: the indicator dialog also offers the built-in panes.
  const paneDefs = useMemo(
    () =>
      [...(extraPaneDefs ?? []), ...PANE_DEFS, ...(showVolume ? [VOLUME_PANE] : [])].filter(
        (def, i, all) => all.findIndex((d) => d.id === def.id) === i
      ),
    [extraPaneDefs, showVolume]
  );

  /**
   * Pane input: the backend indicator bars, with each bar's volume and its
   * up/down direction merged in from `bars` so the volume pane needs no
   * separate plumbing.
   */
  const paneSourceBars = useMemo<IndicatorSeriesBar[]>(() => {
    const byDate = new Map<string, IndicatorSeriesBar>();
    for (const bar of indicatorSeries ?? []) byDate.set(bar.date, { ...bar });
    bars.forEach((bar, i) => {
      const entry = byDate.get(bar.date) ?? { date: bar.date };
      entry.volume = bar.volume;
      const prev = i > 0 ? parseFloat(bars[i - 1].close) : parseFloat(bar.open);
      entry.volume_direction = parseFloat(bar.close) >= prev ? 1 : -1;
      byDate.set(bar.date, entry);
    });
    return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [bars, indicatorSeries]);

  /** Per-series data for every registered pane, keyed `${paneId}:${seriesKey}`. */
  const paneData = useMemo(() => {
    const out = new Map<string, { time: UTCTimestamp; value: number; color?: string }[]>();
    for (const def of paneDefs) {
      for (const series of def.series) {
        const points: { time: UTCTimestamp; value: number; color?: string }[] = [];
        for (const bar of paneSourceBars) {
          const raw = bar[series.key];
          if (typeof raw !== 'number' || !Number.isFinite(raw)) continue;
          const point: { time: UTCTimestamp; value: number; color?: string } = {
            time: toTime(bar.date),
            value: raw,
          };
          if (series.sign) {
            const source = bar[series.sign.key ?? series.key];
            const signed = typeof source === 'number' ? source : raw;
            point.color = signed >= 0 ? series.sign.positive : series.sign.negative;
          }
          points.push(point);
        }
        out.set(`${def.id}:${series.key}`, points);
      }
    }
    return out;
  }, [paneSourceBars, paneDefs]);

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
    const indByDate = new Map<string, Record<PaneId, number>>();
    for (const bar of paneSourceBars) {
      const entry: Record<PaneId, number> = {};
      for (const def of paneDefs) {
        const key = paneReadoutKey(def);
        const raw = key ? bar[key] : undefined;
        if (typeof raw === 'number' && Number.isFinite(raw)) entry[def.id] = raw;
      }
      indByDate.set(bar.date, entry);
    }
    return { barByDate, indByDate };
  }, [bars, paneSourceBars, paneDefs]);

  const readoutMapsRef = useRef(readoutMaps);
  const paneDefsRef = useRef(paneDefs);
  useEffect(() => {
    readoutMapsRef.current = readoutMaps;
    paneDefsRef.current = paneDefs;
  });

  // The plot takes the height its cell (`[data-plot-cell]`) leaves after this
  // chart's own controls above it and its footnote below it.
  useLayoutEffect(() => {
    if (!autoHeight || !containerRef.current) return;
    const container = containerRef.current;
    const cell = container.closest('[data-plot-cell]');
    const root = container.closest('.price-workstation');
    if (!cell || !root) return;
    const measure = () => {
      const top = container.getBoundingClientRect().top;
      const below = root.getBoundingClientRect().bottom - container.getBoundingClientRect().bottom;
      const bottom = cell.getBoundingClientRect().bottom - parseFloat(getComputedStyle(cell).paddingBottom);
      setFittedHeight(Math.max(compact ? 48 : 128, Math.floor(bottom - top - below)));
    };
    let frame = 0;
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(measure); };
    const observer = new ResizeObserver(schedule);
    observer.observe(cell);
    observer.observe(root);
    measure();
    return () => { observer.disconnect(); cancelAnimationFrame(frame); };
  }, [autoHeight, compact]);

  // Create the chart once; series are (re)built when the render mode changes.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.dataset.chartGeneration = String(++chartGeneration);
    const chart = createChart(container, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
        attributionLogo: false,
        // The library's default separator is white, harsh in the dark theme.
        panes: { separatorColor: 'rgba(148,163,184,0.25)', separatorHoverColor: 'rgba(148,163,184,0.45)' },
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
    const rememberRange = (range: { from: number; to: number } | null) => { navigationRangeRef.current = range; };
    chart.timeScale().subscribeVisibleLogicalRangeChange(rememberRange);
    // The visible dates, on the element, for tests and tools that cannot read the canvas.
    const dateOf = (time: Time) => new Date((time as number) * 1000).toISOString().slice(0, 10);
    const showDates = (range: IRange<Time> | null) => {
      container.dataset.visibleFrom = range ? dateOf(range.from) : '';
      container.dataset.visibleTo = range ? dateOf(range.to) : '';
    };
    chart.timeScale().subscribeVisibleTimeRangeChange(showDates);
    // The drawing primitive belongs to pane 0 for its entire lifetime.
    chart.panes()[0]?.setPreserveEmptyPane(true);
    const maSeries = maSeriesRef.current;
    const paneSeries = paneSeriesRef.current;

    // Phase 9 — the drawings primitive lives on pane 0, so it survives the
    // candlestick/line series rebuilds below untouched.
    const drawingsLayer = attachDrawingsLayer(chart, () => priceSeriesRef.current);
    drawingsLayerRef.current = drawingsLayer;

    // Follow the container, not the window: a side panel can open beside the chart.
    const resizer = new ResizeObserver(() => chart.applyOptions({ width: container.clientWidth }));
    resizer.observe(container);
    return () => {
      resizer.disconnect();
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(rememberRange);
      chart.timeScale().unsubscribeVisibleTimeRangeChange(showDates);
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

  useEffect(() => {
    chartRef.current?.applyOptions({ layout: { textColor: resolvedTheme === 'dark' ? '#95a5b0' : '#5f7280' } });
  }, [resolvedTheme]);

  // Crosshair readout and the cursor preview of an in-progress drawing.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const onCrosshairMove = (param: MouseEventParams<Time>) => {
      crosshairSyncRef.current?.publish(chart, param.time ? fromTime(param.time as UTCTimestamp) : null);
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
      const panes = paneDefsRef.current
        .filter((def) => active.has(def.id) && inds[def.id] != null)
        .map((def) => ({
          id: def.id,
          label: def.label,
          color: paneColor(def),
          value: (def.format ?? fixed2)(inds[def.id]),
        }));
      setReadout(panes.length > 0 || bar ? { date, bar: bar ?? null, panes } : null);
    };

    chart.subscribeCrosshairMove(onCrosshairMove);
    return () => chart.unsubscribeCrosshairMove(onCrosshairMove);
    // Mounted once; everything stateful is read through the mirroring refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Follow the crosshair of the other charts in the layout.
  useEffect(() => {
    const chart = chartRef.current;
    if (!crosshairSync || !chart) return;
    return crosshairSync.subscribe(chart, (date) => {
      const at = date ? barAtOrAfter(barDatesRef.current, date) : undefined;
      const bar = at ? readoutMapsRef.current.barByDate.get(at) : undefined;
      const series = priceSeriesRef.current;
      if (at && bar && series) chart.setCrosshairPosition(bar.close, toTime(at), series);
      else {
        // Clearing from code fires no crosshair move, so the readout clears here.
        chart.clearCrosshairPosition();
        setReadout(null);
      }
    });
  }, [crosshairSync]);

  // Push the latest drawing/draft state into the pane primitive.
  const drawingsLayerRef = useRef<ReturnType<typeof attachDrawingsLayer> | null>(null);
  useEffect(() => {
    drawingsLayerRef.current?.update({
      drawings,
      draft: drawingTool && draftPoints.length ? draftPoints : null,
      draftKind: drawingTool,
      cursor:
        drawingTool && draftPoints.length > 0 && draftPoints.length < DRAWING_REQUIRED_POINTS[drawingTool]
          ? cursorPoint
          : null,
      selectedId,
    });
  }, [drawings, drawingTool, draftPoints, cursorPoint, height, selectedId]);

  // Select, drag and delete drawings (M11). Pointer events are taken in the
  // capture phase, before the chart's own pan handling, and only when the
  // pointer is on a drawing; anywhere else the chart pans as usual.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const toScreen = (point: DrawingPoint): ScreenPoint | null => {
      const chart = chartRef.current;
      const series = priceSeriesRef.current;
      if (!chart || !series) return null;
      const x = chart.timeScale().timeToCoordinate(toTime(point.date));
      const y = series.priceToCoordinate(point.price);
      return x == null || y == null ? null : { x, y };
    };
    const localPoint = (e: MouseEvent): ScreenPoint => {
      const rect = container.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };

    let drag: { id: string; part: DrawingPart; start: ScreenPoint; origin: ChartDrawing; moved: boolean } | null = null;
    let touchAnchor: { id: number; start: ScreenPoint; moved: boolean } | null = null;
    let lastTouchAnchor = 0;

    const dragged = (current: ScreenPoint): ChartDrawing | null => {
      const chart = chartRef.current;
      const series = priceSeriesRef.current;
      if (!drag || !chart || !series) return null;
      const startLogical = chart.timeScale().coordinateToLogical(drag.start.x);
      const nowLogical = chart.timeScale().coordinateToLogical(current.x);
      const barShift = startLogical == null || nowLogical == null ? 0 : Math.round(nowLogical - startLogical);
      const dy = current.y - drag.start.y;
      const prices = drag.origin.points.map((p) => {
        const y = series.priceToCoordinate(p.price);
        const price = y == null ? null : series.coordinateToPrice(y + dy);
        return price ?? p.price;
      });
      return moveDrawing(drag.origin, drag.part, barShift, prices, barDatesRef.current);
    };

    /** The bar date and price under a pane point; bars clamp to the loaded range. */
    const toData = (p: ScreenPoint): DrawingPoint | null => {
      const chart = chartRef.current;
      const series = priceSeriesRef.current;
      const dates = barDatesRef.current;
      if (!chart || !series || dates.length === 0 || p.y > chart.panes()[0].getHeight()) return null;
      const logical = chart.timeScale().coordinateToLogical(p.x);
      const price = series.coordinateToPrice(p.y);
      if (logical == null || price == null) return null;
      return { date: dates[Math.max(0, Math.min(dates.length - 1, Math.round(logical)))], price };
    };

    // Anchors are placed from native clicks, not the library's click event: the
    // library drops a second click that comes inside its double-click window,
    // which loses a fast user's second anchor.
    const onPlace = (e: MouseEvent) => {
      if (e.type === 'click' && Date.now() - lastTouchAnchor < 600) return;
      const tool = drawingToolRef.current;
      if (!drawingsEnabledRef.current || !tool || e.button !== 0) return;
      const at = localPoint(e);
      const point = toData(at);
      if (!point) return;
      // The second click of a double-click lands on the previous anchor; a
      // drawing needs distinct points, so wait for the next real one.
      const previous = draftPointsRef.current.at(-1);
      const previousAt = previous && toScreen(previous);
      if (previousAt && Math.hypot(previousAt.x - at.x, previousAt.y - at.y) < HANDLE_RADIUS) return;
      const next = [...draftPointsRef.current, point];
      draftPointsRef.current = next;
      if (next.length >= DRAWING_REQUIRED_POINTS[tool]) {
        const writes = TEXT_KINDS.has(tool);
        // Every field the server stores, so the saved copy and this one compare equal.
        const drawing: ChartDrawing = { id: drawingId(), kind: tool, points: next, color: DRAWING_COLOR, width: 2, text: writes ? '' : null };
        if (writes) { setNoteEditor({ drawing, x: at.x, y: at.y }); selectTool(null); return; }
        commitDrawings([...drawingsRef.current, drawing]);
        setSelectedId(drawing.id);
        selectTool(null);
      } else {
        setDraftPoints(next);
      }
    };

    const onPointerDown = (e: PointerEvent) => {
      if (drawingsEnabledRef.current && drawingToolRef.current && e.pointerType === 'touch') {
        touchAnchor = touchAnchor ? null : { id: e.pointerId, start: localPoint(e), moved: false };
        return;
      }
      if (!drawingsEnabledRef.current || drawingToolRef.current || e.button !== 0) return;
      const at = localPoint(e);
      const hit = hitTestAll(
        drawingsRef.current.filter((d) => !d.hidden).map((d) => ({ id: d.id, kind: d.kind, points: d.points.map(toScreen), text: d.text ?? '' })),
        at,
      );
      if (!hit) {
        setSelectedId(null);
        return;
      }
      // Keep the chart from panning, and suppress the compatibility mouse events.
      e.stopPropagation();
      e.preventDefault();
      container.focus();
      setSelectedId(hit.id);
      const origin = drawingsRef.current.find((d) => d.id === hit.id)!;
      if (origin.locked) return;
      drag = { id: hit.id, part: hit.part, start: at, origin, moved: false };
      chartRef.current?.applyOptions({ handleScroll: false, handleScale: false });
      window.addEventListener('pointermove', onPointerMove);
      window.addEventListener('pointerup', onPointerUp, { once: true });
    };

    const onPointerMove = (e: PointerEvent) => {
      const next = dragged(localPoint(e));
      if (!drag || !next) return;
      drag.moved = true;
      setDrawings(drawingsRef.current.map((d) => (d.id === drag!.id ? next : d)));
    };

    const onPointerUp = (e: PointerEvent) => {
      window.removeEventListener('pointermove', onPointerMove);
      chartRef.current?.applyOptions({ handleScroll: true, handleScale: true });
      const next = drag?.moved ? dragged(localPoint(e)) : null;
      if (drag && next) commitDrawings(drawingsRef.current.map((d) => (d.id === drag!.id ? next : d)));
      drag = null;
    };

    const onContextMenu = (e: MouseEvent) => {
      if (!drawingsEnabledRef.current) return;
      const at = localPoint(e);
      const hit = hitTestAll(
        drawingsRef.current.filter((d) => !d.hidden).map((d) => ({ id: d.id, kind: d.kind, points: d.points.map(toScreen), text: d.text ?? '' })),
        at,
      );
      e.preventDefault();
      setSelectedId(hit?.id ?? null);
      setMenu({ id: hit?.id ?? null, x: at.x, y: at.y });
    };

    // Lightweight Charts suppresses compatibility clicks after a touch. A tap
    // still places one anchor; a swipe or cancelled gesture never places one.
    const onTouchMove = (e: PointerEvent) => {
      if (!touchAnchor || e.pointerId !== touchAnchor.id) return;
      const at = localPoint(e);
      if (Math.hypot(at.x - touchAnchor.start.x, at.y - touchAnchor.start.y) > 8) touchAnchor.moved = true;
    };
    const onTouchEnd = (e: PointerEvent) => {
      if (!touchAnchor || e.pointerId !== touchAnchor.id) return;
      const place = e.type === 'pointerup' && !touchAnchor.moved;
      touchAnchor = null;
      if (place) { onPlace(e); lastTouchAnchor = Date.now(); }
    };

    container.addEventListener('pointerdown', onPointerDown, { capture: true });
    window.addEventListener('pointermove', onTouchMove, { capture: true });
    window.addEventListener('pointerup', onTouchEnd, { capture: true });
    window.addEventListener('pointercancel', onTouchEnd, { capture: true });
    container.addEventListener('click', onPlace);
    container.addEventListener('contextmenu', onContextMenu);
    return () => {
      container.removeEventListener('pointerdown', onPointerDown, { capture: true });
      container.removeEventListener('contextmenu', onContextMenu);
      container.removeEventListener('click', onPlace);
      window.removeEventListener('pointermove', onTouchMove, { capture: true });
      window.removeEventListener('pointerup', onTouchEnd, { capture: true });
      window.removeEventListener('pointercancel', onTouchEnd, { capture: true });
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
    // Mounted once; everything stateful is read through the mirroring refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onChartKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      selectTool(null);
      setSelectedId(null);
      return;
    }
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.code === 'KeyZ') {
      e.preventDefault();
      stepHistory(e.shiftKey ? 'after' : 'before');
      return;
    }
    if (mod && e.code === 'KeyY') {
      e.preventDefault();
      stepHistory('after');
      return;
    }
    if (e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')) {
      e.preventDefault();
      const d = drawings.find((x) => x.id === selectedId);
      const p = d && d.points[0] ? screenOf(d.points[0]) : null;
      setMenu({ id: d?.id ?? null, x: p?.x ?? 40, y: p?.y ?? 40 });
      return;
    }
    if (selectedId && !mod && !e.altKey && moveSelected(e.key)) {
      e.preventDefault();
      return;
    }
    const tool = e.altKey ? TOOL_KEYS[`${e.shiftKey ? 'Shift+' : ''}${e.code}`] : undefined;
    if (tool) {
      e.preventDefault();
      toggleDrawingTool(tool);
      return;
    }
    if (navigateChart(e)) {
      e.preventDefault();
      return;
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId && !drawings.find((d) => d.id === selectedId)?.locked) {
      e.preventDefault();
      commitDrawings(drawings.filter((d) => d.id !== selectedId));
      setSelectedId(null);
    }
  };

  useEffect(() => {
    chartRef.current?.applyOptions({ height });
  }, [height]);

  useEffect(() => {
    const mode = { normal: PriceScaleMode.Normal, log: PriceScaleMode.Logarithmic, percent: PriceScaleMode.Percentage }[scale];
    chartRef.current?.priceScale('right').applyOptions({ mode });
  }, [scale]);

  // Bar replay: keep the viewport from before replay, and restore it on exit.
  // This runs before the price series effect, which applies it.
  const replaying = !!replayDate;
  const replayViewport = useRef<{ saved: IRange<Time> | null; restore: boolean }>({ saved: null, restore: false });
  useEffect(() => {
    const timeScale = chartRef.current?.timeScale();
    if (!timeScale) return;
    if (replaying) replayViewport.current = { saved: timeScale.getVisibleRange(), restore: false };
    else if (replayViewport.current.saved) replayViewport.current.restore = true;
  }, [replaying]);

  const previousPriceContext = useRef<string>();
  const priceContext = `${drawingsKey ?? bars[0]?.date ?? ''}:${interval}`;
  // Price series (candlestick or close line).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const viewport = previousPriceContext.current === priceContext ? chart.timeScale().getVisibleRange() : null;
    const logical = chart.timeScale().getVisibleLogicalRange();
    previousPriceContext.current = priceContext;
    if (priceSeriesRef.current) {
      chart.removeSeries(priceSeriesRef.current);
      priceSeriesRef.current = null;
    }
    const upColor = resolvedTheme === 'dark' ? '#34d399' : '#147d65';
    const downColor = resolvedTheme === 'dark' ? '#fb7185' : '#c93850';
    const candleColors = { upColor, downColor, borderUpColor: upColor, borderDownColor: downColor, wickUpColor: upColor, wickDownColor: downColor };
    const closes = parsed.map((p) => ({ time: p.time, value: p.close }));
    if (chartType === 'candles' || chartType === 'heikin_ashi') {
      const series = chart.addSeries(CandlestickSeries, candleColors);
      series.setData(chartType === 'heikin_ashi' ? heikinAshi(parsed) : parsed);
      priceSeriesRef.current = series;
    } else if (chartType === 'bars') {
      const series = chart.addSeries(BarSeries, { upColor, downColor });
      series.setData(parsed);
      priceSeriesRef.current = series;
    } else if (chartType === 'area') {
      const series = chart.addSeries(AreaSeries, {
        lineColor: '#6366f1',
        topColor: 'rgba(99,102,241,0.28)',
        bottomColor: 'rgba(99,102,241,0.02)',
        lineWidth: 2,
      });
      series.setData(closes);
      priceSeriesRef.current = series;
    } else {
      const series = chart.addSeries(LineSeries, { color: '#6366f1', lineWidth: 2 });
      series.setData(closes);
      priceSeriesRef.current = series;
    }
    hideTicksUnderLastPrice(priceSeriesRef.current);
    const restore = replayViewport.current.restore && !replaying ? replayViewport.current.saved : null;
    if (restore) {
      replayViewport.current = { saved: null, restore: false };
      chart.timeScale().setVisibleRange(restore);
    } else if (replaying && logical && parsed.length) {
      // Replay keeps the zoom and scrolls so the newest bar sits near the right edge.
      const width = logical.to - logical.from;
      const end = parsed.length - 1 + 3;
      chart.timeScale().setVisibleLogicalRange({ from: end - width, to: end });
    } else if (viewport) chart.timeScale().setVisibleRange(viewport);
    else chart.timeScale().fitContent();
    // NFR-11 measures chart open time to this mark: the first frame after the
    // price series holds its bars.
    if (parsed.length > 0) requestAnimationFrame(() => performance.mark('wickstreet:chart-painted'));
  }, [chartType, parsed, priceContext, resolvedTheme]); // eslint-disable-line react-hooks/exhaustive-deps

  // MA overlays.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    for (const [period, series] of Array.from(maSeriesRef.current.entries())) {
      if (!activeMas.includes(period) || scale === 'percent') {
        chart.removeSeries(series);
        maSeriesRef.current.delete(period);
      }
    }
    for (const period of scale === 'percent' ? [] : activeMas) {
      let series = maSeriesRef.current.get(period);
      if (!series) {
        series = chart.addSeries(LineSeries, {
          color: maColors[period],
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        maSeriesRef.current.set(period, series);
      }
      series.applyOptions({ color: maColors[period], lineWidth: evidencePeriods.has(period) ? 3 : 1 });
      series.setData(maSeriesData.get(period) ?? []);
    }
  }, [activeMas, maSeriesData, scale, maColors, evidencePeriods]);

  // Evidence layers: dashed SMAs for periods the chart does not already show.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const wanted = new Map<number, { time: UTCTimestamp; value: number }[]>();
    if (scale !== 'percent') {
      const warmup = maWarmup ?? [];
      const closes = [...warmup, ...parsed.map((p) => p.close)];
      for (const period of evidencePeriods) {
        if (activeMas.includes(period)) continue;
        const means = sma(closes, period).slice(warmup.length);
        wanted.set(period, parsed.map((p, i) => ({ time: p.time, value: means[i] })).filter((p): p is { time: UTCTimestamp; value: number } => p.value !== null));
      }
    }
    for (const [period, series] of Array.from(evidenceSeriesRef.current.entries())) {
      if (!wanted.has(period)) {
        chart.removeSeries(series);
        evidenceSeriesRef.current.delete(period);
      }
    }
    for (const [period, data] of wanted) {
      let series = evidenceSeriesRef.current.get(period);
      if (!series) {
        series = chart.addSeries(LineSeries, { color: EVIDENCE_COLOR, lineWidth: 2, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false });
        evidenceSeriesRef.current.set(period, series);
      }
      series.setData(data);
    }
  }, [evidencePeriods, activeMas, parsed, maWarmup, scale]);

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
    ].filter((line) => line.points.length > 1 && (scale !== 'percent' || line.percentSafe));
    overlaySeriesRef.current = lines.map((line) => {
      const series = chart.addSeries(LineSeries, {
        color: line.color ?? '#a855f7',
        lineWidth: line.lineWidth ?? 2,
        lineStyle: line.lineStyle ?? LineStyle.Solid,
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
  }, [overlayLine, overlayLines, scale]);

  useEffect(() => {
    const series = priceSeriesRef.current;
    if (!series) return;
    const levels = (alertLevels ?? []).map((level) => series.createPriceLine({ ...level, color: '#b45309', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true }));
    return () => { for (const level of levels) series.removePriceLine(level); };
  }, [alertLevels, chartType, parsed]);

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
        shape: m.shape ?? 'circle' as const,
        size: m.size ?? 1,
        text: m.text,
      }))
    );
    return () => {
      markersRef.current?.detach();
      markersRef.current = null;
    };
  }, [markers, chartType, parsed]);

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
  }, [priceZone, chartType, parsed]);

  const lastWindow = useRef<string>();
  // Scroll to a requested date window (a selected wave's span), or back to the
  // whole loaded range when the caller clears it.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !parsed.length) return;
    // New bars may change the preset's date endpoints; they must not undo a pan.
    const key = JSON.stringify([priceContext, timeframe, visibleRange?.from, visibleRange?.to, !!initialWindow]);
    if (lastWindow.current === key) return;
    lastWindow.current = key;
    navigationRangeRef.current = null;
    const window = visibleRange ?? initialWindow;
    if (!window) {
      chart.timeScale().fitContent();
      return;
    }
    chart.timeScale().setVisibleRange({
      from: toTime(window.from),
      to: toTime(window.to),
    });
  }, [visibleRange, initialWindow?.from, initialWindow?.to, parsed, priceContext, timeframe]); // eslint-disable-line react-hooks/exhaustive-deps

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
    // Create the missing ones in registry order so pane positions are stable.
    for (const def of paneDefs) {
      if (!displayedPanes.includes(def.id) || paneSeriesRef.current.has(def.id)) continue;
      const pane = chart.addPane(false);
      const record: PaneRecord = { pane, series: [] };
      let guidesPlaced = false;
      for (const seriesDef of def.series) {
        if (seriesDef.type === 'histogram') {
          record.series.push(
            pane.addSeries(HistogramSeries, {
              priceLineVisible: false,
              lastValueVisible: seriesDef.lastValueVisible ?? false,
              priceFormat: { type: 'volume' },
              priceScaleId: 'right',
              base: 0,
            })
          );
          continue;
        }
        const line = pane.addSeries(LineSeries, {
          color: seriesDef.color,
          lineWidth: 1,
          priceLineVisible: false,
          ...(seriesDef.lastValueVisible === undefined
            ? {}
            : { lastValueVisible: seriesDef.lastValueVisible }),
        });
        // Guides hang off the pane's first line series, as RSI's always have.
        if (!guidesPlaced) {
          for (const guide of def.guides ?? []) {
            line.createPriceLine({
              price: guide.value,
              color: GUIDE_COLOR,
              lineStyle: LineStyle.Dashed,
              lineWidth: 1,
              title: guide.label ?? '',
            });
          }
          guidesPlaced = true;
        }
        record.series.push(line);
      }
      paneSeriesRef.current.set(def.id, record);
    }
    // Re-balance pane heights (price dominates, sub-panes share the rests).
    chart.panes().forEach((p, index) => p.setStretchFactor(index === 0 ? 3 : 1));

    // Refresh each pane's data.
    for (const def of paneDefs) {
      const record = paneSeriesRef.current.get(def.id);
      if (!record) continue;
      def.series.forEach((seriesDef, i) => {
        if (seriesDef.color) record.series[i]?.applyOptions({ color: seriesDef.color });
        record.series[i]?.setData(paneData.get(`${def.id}:${seriesDef.key}`) ?? []);
      });
    }
  }, [displayedPanes, paneData, paneDefs]);

  const toggleMas = (period: number, on: boolean) => {
    const next = on
      ? [...activeMas, period].sort((a, b) => a - b)
      : activeMas.filter((p) => p !== period);
    if (onActiveMasChange) onActiveMasChange(next);
    else setInternalMas(next);
  };

  const paneOrder = paneDefs.map((d) => d.id);
  const togglePane = (id: PaneId) => {
    const next = displayedPanes.includes(id)
      ? displayedPanes.filter((p) => p !== id)
      : [...displayedPanes, id].sort((a, b) => paneOrder.indexOf(a) - paneOrder.indexOf(b));
    setDisplayedPanes(next);
  };

  const toggleDrawingTool = (kind: DrawingKind) => selectTool(drawingToolRef.current === kind ? null : kind);

  const screenOf = (point: DrawingPoint): ScreenPoint | null => {
    const x = chartRef.current?.timeScale().timeToCoordinate(toTime(point.date));
    const y = priceSeriesRef.current?.priceToCoordinate(point.price);
    return x == null || y == null ? null : { x, y };
  };

  /** Arrow keys move the selected drawing: one bar sideways, 4 px of price up or down. */
  const moveSelected = (key: string): boolean => {
    const d = drawings.find((x) => x.id === selectedId);
    const series = priceSeriesRef.current;
    if (!d || !series || d.hidden) return false;
    if (d.locked) return ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(key);
    let shift = 0;
    let prices = d.points.map((p) => p.price);
    if (key === 'ArrowLeft') shift = -1;
    else if (key === 'ArrowRight') shift = 1;
    else if (key === 'ArrowUp' || key === 'ArrowDown') {
      const dy = key === 'ArrowUp' ? -4 : 4;
      prices = d.points.map((p) => {
        const y = series.priceToCoordinate(p.price);
        return (y == null ? null : series.coordinateToPrice(y + dy)) ?? p.price;
      });
    } else return false;
    const moved = moveDrawing(d, 'body', shift, prices, barDatesRef.current);
    commitDrawings(drawings.map((x) => (x.id === d.id ? moved : x)));
    return true;
  };

  /** Arrow keys pan, Ctrl/⌘ with ↑/↓ (or + and -) zoom, Alt+R resets. True when the key was used. */
  const navigateChart = (e: React.KeyboardEvent): boolean => {
    const timeScale = chartRef.current?.timeScale();
    const range = navigationRangeRef.current ?? timeScale?.getVisibleLogicalRange();
    if (!timeScale || !range) return false;
    const span = range.to - range.from;
    // Keep successive key repeats cumulative before the next animation frame.
    const setRange = (next: { from: number; to: number }) => { navigationRangeRef.current = next; timeScale.setVisibleLogicalRange(next); };
    const zoom = (factor: number) => {
      const centre = (range.from + range.to) / 2;
      const half = Math.max(5, (span * factor) / 2);
      setRange({ from: centre - half, to: centre + half });
    };
    const pan = (bars: number) => setRange({ from: range.from + bars, to: range.to + bars });
    const mod = e.ctrlKey || e.metaKey;
    if (e.altKey && e.code === 'KeyR') timeScale.fitContent();
    else if ((mod && e.key === 'ArrowUp') || e.key === '+' || e.key === '=') zoom(0.8);
    else if ((mod && e.key === 'ArrowDown') || e.key === '-') zoom(1.25);
    else if (e.key === 'ArrowLeft') pan(-Math.max(1, span / 10));
    else if (e.key === 'ArrowRight') pan(Math.max(1, span / 10));
    else return false;
    return true;
  };

  const clearDrawings = () => {
    commitDrawings([]);
    setSelectedId(null);
    setDraftPoints([]);
    setCursorPoint(null);
  };

  const showPaneControls = drawingsEnabled || indicatorSeries?.length;
  const rail = toolRail && drawingsEnabled && (
    <DrawingRail
      tool={drawingTool}
      onTool={(kind) => (kind ? toggleDrawingTool(kind) : selectTool(null))}
      canClear={drawings.length > 0}
      onClear={clearDrawings}
      collapsible={!!chrome}
    />
  );
  const activePaneSet = new Set(displayedPanes);

  // The chart's controls, laid out inline below, or portalled into the
  // workspace's toolbar, settings, history and range-bar slots (`chrome`).
  const rangeSelect = (
    <select
      aria-label="Range"
      value={timeframe}
      onChange={(e) => onTimeframeChange(e.target.value as TimeframeId)}
      className={`rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-1 py-0.5 text-xs ${focusRing}`}
    >
      {TIMEFRAMES.map((tf) => (
        <option key={tf.id} value={tf.id}>
          {tf.label}
        </option>
      ))}
    </select>
  );
  const rangeButtons = (
    <div className="flex items-center gap-0.5 rounded-lg bg-slate-100 dark:bg-slate-800/60 p-0.5">
      {TIMEFRAMES.map((tf) => (
        <ToggleButton key={tf.id} active={timeframe === tf.id} onClick={() => onTimeframeChange(tf.id)}>
          {tf.label}
        </ToggleButton>
      ))}
    </div>
  );
  const history = chrome ? (
    <span className="inline-flex items-center">
      <button type="button" aria-label="Undo" className={`ws-icon-button disabled:opacity-40 ${focusRing}`} disabled={!historyRef.current.past.length} onClick={() => stepHistory('before')} title="Undo (Ctrl/⌘+Z)">{UNDO_ICON}</button>
      <button type="button" aria-label="Redo" className={`ws-icon-button disabled:opacity-40 ${focusRing}`} disabled={!historyRef.current.future.length} onClick={() => stepHistory('after')} title="Redo (Ctrl/⌘+Shift+Z)">{UNDO_ICON_REDO}</button>
    </span>
  ) : (
    <span className="inline-flex items-center gap-1">
      <button type="button" className="workstation-button" disabled={!historyRef.current.past.length} onClick={() => stepHistory('before')}>Undo</button>
      <button type="button" className="workstation-button" disabled={!historyRef.current.future.length} onClick={() => stepHistory('after')}>Redo</button>
    </span>
  );
  // The drawings list: the Object tree panel tab on /chart, a disclosure elsewhere.
  const objectList = (
    <div className="flex flex-col gap-1.5" aria-label="Drawing objects">
      {!drawings.length && <p className="text-xs text-slate-500">No objects on this chart. Choose a tool on the rail to mark it. Removed objects can be restored with Undo.</p>}
      {drawings.map((d) => <div key={d.id} className="flex items-center gap-2 text-xs">
        <button type="button" className="flex-1 text-left" onClick={() => { setSelectedId(d.id); setMenu({ id: d.id, x: 40, y: 40 }); }}>{DRAWING_LABELS[d.kind]}</button>
        <button type="button" className="workstation-button" aria-label={`${d.hidden ? 'Show' : 'Hide'} ${DRAWING_LABELS[d.kind]}`} onClick={() => commitDrawings(drawings.map((x) => x.id === d.id ? { ...x, hidden: !x.hidden } : x))}>{d.hidden ? 'Show' : 'Hide'}</button>
        <button type="button" className="workstation-button" aria-label={`${d.locked ? 'Unlock' : 'Lock'} ${DRAWING_LABELS[d.kind]}`} onClick={() => commitDrawings(drawings.map((x) => x.id === d.id ? { ...x, locked: !x.locked } : x))}>{d.locked ? 'Unlock' : 'Lock'}</button>
      </div>)}
    </div>
  );
  const objects = drawingsEnabled && !chrome && (!compact || toolRail) && (
    <InspectorDisclosure label={<>Objects{drawings.length ? ` · ${drawings.length}` : ''}</>} name="Objects · manage drawings">
      <div className="study-options-content objects-content">
        {history}
        {objectList}
      </div>
    </InspectorDisclosure>
  );
  const intervalGroup = onIntervalChange && (
    <div role="group" aria-label="Interval" className="flex items-center gap-0.5 rounded-lg bg-slate-100 dark:bg-slate-800/60 p-0.5">
      {INTERVALS.map((iv) => (
        <ToggleButton key={iv.id} active={interval === iv.id} onClick={() => onIntervalChange(iv.id)} ariaLabel={iv.name}>
          {iv.label}
        </ToggleButton>
      ))}
    </div>
  );
  const chartTypeSelect = (
    <select
      aria-label="Chart type"
      value={chartType}
      onChange={(e) => setChartType(e.target.value as ChartType)}
      className={`rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-1.5 py-1 text-xs ${focusRing}`}
    >
      {CHART_TYPES.map((t) => (
        <option key={t.id} value={t.id}>
          {t.label}
        </option>
      ))}
    </select>
  );
  const scaleGroup = (
    <div role="group" aria-label="Price scale" className="flex items-center gap-0.5 rounded-lg bg-slate-100 dark:bg-slate-800/60 p-0.5">
      <ToggleButton active={scale === 'log'} onClick={() => setScale(scale === 'log' ? 'normal' : 'log')} ariaLabel="Log scale">
        Log
      </ToggleButton>
      <ToggleButton active={scale === 'percent'} onClick={() => setScale(scale === 'percent' ? 'normal' : 'percent')} ariaLabel="Percent scale">
        %
      </ToggleButton>
    </div>
  );
  const volumeToggle = (
    <ToggleButton active={showVolume} onClick={() => setShowVolume((v) => !v)}>
      Volume
    </ToggleButton>
  );
  const studies = (
    <>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-600 dark:text-slate-300">Moving averages</span>
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
              <span aria-hidden="true" className="inline-block w-2 h-2 rounded-sm" style={{ backgroundColor: maColors[period] }} />
              <span>MA{period}</span>
            </label>
          ))}
        </div>
        {showPaneControls && (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate-600 dark:text-slate-300">Indicators</span>
              {PANE_DEFS.map((def) => (
                <label
                  key={def.id}
                  className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={activePaneSet.has(def.id)}
                    disabled={!indicatorSeries?.length}
                    onChange={() => togglePane(def.id)}
                    className="w-3 h-3 accent-indigo-500"
                  />
                  <span aria-hidden="true" className="inline-block w-2 h-2 rounded-sm" style={{ backgroundColor: paneColor(def) }} />
                  <span>{def.label}</span>
                </label>
              ))}
            </div>
            {drawingsEnabled && !toolRail && (
              <div className="flex items-center gap-1 flex-wrap">
                <span className="text-xs text-slate-600 dark:text-slate-300">Draw</span>
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
    </>
  );
  const footText = isLoading
    ? 'Loading price series…'
    : (footnote ??
      `${bars.length} ${barWord} bars from the stored NSE series. Moving averages are simple rolling means of the stored closes.${
        bars.at(-1)?.partial ? ` The last ${interval === '1M' ? 'month' : 'week'} is not complete.` : ''
      }${dataVersion ? ` Data version ${dataVersion}.` : ''}`);
  const lastBar = parsed.at(-1);
  const previousClose = parsed.at(-2)?.close;
  const shownBar = readout?.bar ?? lastBar;
  const ohlc = (bar: { open: number; high: number; low: number; close: number }) =>
    `O ${bar.open.toFixed(2)} H ${bar.high.toFixed(2)} L ${bar.low.toFixed(2)} C ${bar.close.toFixed(2)}`;
  const legendAction = `pointer-events-auto w-4 h-4 inline-flex items-center justify-center rounded text-slate-500 opacity-60 hover:opacity-100 hover:bg-[var(--ws-muted)] focus-visible:opacity-100 ${focusRing}`;
  // TradingView's familiar order: title, the bar's values, then one line per study.
  const overlayLegend = (
    <div className="chart-overlay-legend">
      <div className="tabular-nums">
        {legendTitle && <span className="font-semibold text-[var(--ws-ink)]">{legendTitle}</span>}
        {legendChip}
        {!readout && shownBar && (
          <span className="ml-2 text-slate-600 dark:text-slate-300">
            {ohlc(shownBar)}
            {previousClose !== undefined && (
              <span className={shownBar.close >= previousClose ? 'ml-1 text-emerald-700 dark:text-emerald-400' : 'ml-1 text-rose-700 dark:text-rose-400'}>
                {`${shownBar.close >= previousClose ? '+' : ''}${(shownBar.close - previousClose).toFixed(2)} (${((shownBar.close / previousClose - 1) * 100).toFixed(2)}%)`}
              </span>
            )}
          </span>
        )}
      </div>
      {readout && (
        <div data-testid="crosshair-readout" className="tabular-nums text-slate-600 dark:text-slate-300">
          <div>
            {readout.date}
            {readout.bar && <span className="ml-2">{ohlc(readout.bar)}</span>}
          </div>
          {readout.panes.map((p) => (
            <div key={p.id} style={{ color: p.color }}>
              {p.label}: {p.value}
            </div>
          ))}
        </div>
      )}
      <div aria-label="Study legend" className="flex flex-col items-start">
        {evidenceLayers?.map((layer) => (
          <span key={layer.id} className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block w-3 border-t-2 border-dashed" style={{ borderColor: EVIDENCE_COLOR }} />
            <span>Evidence · temporary: {layer.label}</span>
            {onRemoveEvidence && <button type="button" aria-label={`Remove evidence ${layer.label}`} title="Remove" onClick={() => onRemoveEvidence(layer.id)} className={legendAction}>×</button>}
          </span>
        ))}
        {scale !== 'percent' && activeMas.map((period) => {
          const series = maSeriesData.get(period);
          const latest = series?.[series.length - 1]?.value;
          return (
            <span key={period} className="inline-flex items-center gap-1.5 tabular-nums">
              <span aria-hidden="true" className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: maColors[period] }} />
              <span className="text-slate-500 dark:text-slate-400">MA{period}</span>
              <span className="text-slate-700 dark:text-slate-300">{latest === undefined ? '—' : latest.toFixed(2)}</span>
              <button type="button" aria-label={`Remove MA${period}`} title="Remove" onClick={() => toggleMas(period, false)} className={legendAction}>×</button>
            </span>
          );
        })}
        {scale === 'percent' && (activeMas.length > 0 || !!studyLegend?.length) && <span className="text-slate-500">Price studies hidden on % scale</span>}
        {paneDefs.filter((d) => displayedPanes.includes(d.id)).map((def) => (
          <span key={def.id} className="inline-flex items-center gap-1.5 tabular-nums">
            <span aria-hidden="true" style={{ color: paneColor(def) }}>●</span>
            <span>{def.label}</span>
            <span>{def.series.map((s) => { const value = paneSourceBars.at(-1)?.[s.key]; return value == null ? '—' : Number(value).toFixed(2); }).join(' / ')}</span>
            {onOpenIndicators && <button type="button" aria-label={`Configure ${def.label}`} title="Settings" onClick={onOpenIndicators} className={legendAction}>⚙</button>}
            <button type="button" aria-label={`Remove ${def.label} pane`} title="Remove" onClick={() => togglePane(def.id)} className={legendAction}>×</button>
          </span>
        ))}
        {scale !== 'percent' && studyLegend?.map((entry, i) => (
          <span key={`${entry.label}-${i}`} className="inline-flex items-center gap-1.5 tabular-nums whitespace-nowrap">
            <span aria-hidden="true" className="inline-block w-3 h-0.5" style={{ background: entry.color }} />
            <span>{entry.label}</span>
            <strong className="font-medium">{entry.value}</strong>
            {onOpenIndicators && <button type="button" aria-label={`Configure ${entry.label}`} title="Settings" onClick={onOpenIndicators} className={legendAction}>⚙</button>}
          </span>
        ))}
      </div>
    </div>
  );
  const fitButton = <button type="button" className="workstation-button" onClick={() => chartRef.current?.timeScale().fitContent()} title="Fit all history (Alt+R)">Fit</button>;

  return (
    <div className="price-workstation" style={{ '--plot-height': `${height}px` } as React.CSSProperties}>
      {bare && !chrome ? null : chrome ? (
        <>
          {chartLabel && !bare && <div className="chart-controls flex items-center gap-1 mb-1">{chartLabel}</div>}
          {chrome.toolbar && createPortal(intervalGroup, chrome.toolbar)}
          {chrome.chartType && createPortal(chartTypeSelect, chrome.chartType)}
          {chrome.history && createPortal(history, chrome.history)}
          {chrome.objects && drawingsEnabled && createPortal(objectList, chrome.objects)}
          {chrome.settings && createPortal(
            <InspectorDisclosure label={SETTINGS_ICON} name="Chart settings">
              <div className="study-options-content">
                <div className="flex items-center gap-2">{volumeToggle}</div>
                {studies}
              </div>
            </InspectorDisclosure>,
            chrome.settings,
          )}
          {chrome.rangeBar && createPortal(
            <>
              {rangeButtons}
              <span className="flex-1" />
              <span className="chart-footnote" title={footText}>{footText}</span>
              {scaleGroup}
              {fitButton}
            </>,
            chrome.rangeBar,
          )}
        </>
      ) : (
      <div className={`chart-controls flex items-center ${compact ? 'gap-1 mb-1' : 'gap-2 mb-1'}`}>
        {chartLabel}
        {compact ? rangeSelect : rangeButtons}
        {objects}
        {intervalGroup}
        {!compact && (
          <>
            {chartTypeSelect}
            {scaleGroup}
            {volumeToggle}
            <InspectorDisclosure label="Studies">
              <div className="study-options-content">
                {studies}
              </div>
            </InspectorDisclosure>
            {fitButton}
          </>
        )}
      </div>
      )}
      {/* Legend: what is currently drawn, with each line's latest value, so
          the colours on the chart need no decoding. */}
      {!compact && !chrome && (activeMas.length > 0 || studyLegend?.length || displayedPanes.length > 0) && (
        <div className="chart-legend flex items-center gap-3 mb-1" aria-label="Study legend">
          {scale !== 'percent' && activeMas.map((period) => {
            const series = maSeriesData.get(period);
            const latest = series?.[series.length - 1]?.value;
            return (
              <span key={period} className="inline-flex items-center gap-1.5 text-[11px] tabular-nums">
                <span
                  aria-hidden="true"
                  className="inline-block w-3 h-0.5 rounded-full"
                  style={{ backgroundColor: maColors[period] }}
                />
                <span className="text-slate-500 dark:text-slate-400">MA{period}</span>
                <span className="text-slate-700 dark:text-slate-300">
                  {latest === undefined ? '—' : latest.toFixed(2)}
                </span>
              </span>
            );
          })}
          {scale === 'percent' && (activeMas.length > 0 || !!studyLegend?.length) && <span className="text-xs text-slate-500">Price studies hidden on % scale</span>}
          {paneDefs.filter((d) => displayedPanes.includes(d.id)).map((def) => <span key={def.id} className="inline-flex items-center gap-1.5 text-[11px] tabular-nums">
            <button type="button" onClick={onOpenIndicators} className={focusRing} title="Configure indicator"><span style={{ color: paneColor(def) }}>●</span> {def.label} {def.series.map((s) => { const value = paneSourceBars.at(-1)?.[s.key]; return value == null ? '—' : Number(value).toFixed(2); }).join(' / ')}</button>
            <button type="button" aria-label={`Remove ${def.label} pane`} onClick={() => togglePane(def.id)} className={focusRing}>×</button>
          </span>)}
          {scale !== 'percent' && studyLegend?.map((entry, i) => <button type="button" key={`${entry.label}-${i}`} onClick={onOpenIndicators} className={`inline-flex items-center gap-1.5 text-[11px] tabular-nums whitespace-nowrap ${focusRing}`} title="Configure study">
            <span aria-hidden="true" className="inline-block w-3 h-0.5" style={{ background: entry.color }} />
            <span>{entry.label}</span><strong className="font-medium">{entry.value}</strong>
          </button>)}
        </div>
      )}
      <div className={rail && !chrome ? 'flex gap-2' : undefined}>
      {chrome ? railSlot && rail && createPortal(rail, railSlot) : rail}
      <div className="relative flex-1 min-w-0">
        {noteEditor && <form aria-label="Text annotation" className="absolute z-30 flex flex-wrap gap-2 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 p-2 shadow-lg" style={{ left: Math.max(0, Math.min(noteEditor.x, (containerRef.current?.clientWidth ?? 300) - 250)), top: Math.max(0, Math.min(noteEditor.y, height - 88)), width: 248 }} onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Escape') { setNoteEditor(null); containerRef.current?.focus(); } }} onSubmit={(e) => { e.preventDefault(); const text = noteEditor.drawing.text?.trim(); if (!text) return; const next = { ...noteEditor.drawing, text }; commitDrawings(drawings.some((d) => d.id === next.id) ? drawings.map((d) => d.id === next.id ? next : d) : [...drawings, next]); setSelectedId(next.id); setNoteEditor(null); containerRef.current?.focus(); }}>
          <input autoFocus aria-label="Annotation text" maxLength={200} value={noteEditor.drawing.text ?? ''} onChange={(e) => setNoteEditor({ ...noteEditor, drawing: { ...noteEditor.drawing, text: e.target.value } })} className="w-full rounded border border-slate-300 dark:border-slate-600 bg-transparent px-2 py-1 text-xs" placeholder="Write a note…" />
          <button type="submit" className="workstation-button">Save note</button><button type="button" className="workstation-button" onClick={() => { setNoteEditor(null); containerRef.current?.focus(); }}>Cancel</button>
        </form>}
        {menu && menu.id === null && (
          <ChartMenu
            at={menu}
            scale={scale}
            onScale={setScale}
            onReset={() => chartRef.current?.timeScale().fitContent()}
            onIndicators={onOpenIndicators}
            onAlert={
              onAlertAtPrice
                ? () => {
                    const price = priceSeriesRef.current?.coordinateToPrice(menu.y);
                    if (price != null) onAlertAtPrice(price);
                  }
                : undefined
            }
            onClose={() => {
              setMenu(null);
              containerRef.current?.focus();
            }}
          />
        )}
        {menu && drawings.some((d) => d.id === menu.id) && (
          <DrawingMenu
            drawing={drawings.find((d) => d.id === menu.id)!}
            onEditText={() => { setNoteEditor({ drawing: drawings.find((d) => d.id === menu.id)!, x: menu.x, y: menu.y }); setMenu(null); }}
            onAlert={onAlertOnDrawing && (() => onAlertOnDrawing(menu.id!))}
            at={menu}
            onChange={(next) => commitDrawings(drawings.map((d) => (d.id === next.id ? next : d)))}
            onDelete={() => {
              commitDrawings(drawings.filter((d) => d.id !== menu.id));
              setSelectedId(null);
              setMenu(null);
              containerRef.current?.focus();
            }}
            onClose={() => {
              setMenu(null);
              containerRef.current?.focus();
            }}
          />
        )}
        <div
          ref={containerRef}
          tabIndex={drawingsEnabled ? 0 : undefined}
          onKeyDown={drawingsEnabled ? onChartKeyDown : undefined}
          data-testid="price-chart"
          role={drawingsEnabled ? 'application' : 'img'}
          aria-label={`Price chart, ${bars.length} ${barWord} bars${
            bars.length ? ` from ${bars[0].date} to ${bars[bars.length - 1].date}` : ''
          }. Moving averages shown: ${activeMas.length ? activeMas.map((p) => `MA${p}`).join(', ') : 'none'}.`}
          className={`w-full ${drawingsEnabled ? `rounded-sm ${focusRing}` : ''}`}
        />
        {!isLoading && bars.length === 0 && <div role="status" className="absolute inset-0 flex items-center justify-center text-xs text-slate-500">No stored bars for this security. Import EOD data from Data to begin.</div>}
        {isLoading && <div role="status" className="absolute top-3 left-3 text-xs text-slate-500">Loading stored history…</div>}
        {chrome && !compact && overlayLegend}
        {bare && chartLabel && <div className="chart-cell-label">{chartLabel}</div>}
        {readout && (compact || !chrome) && (
          <div data-testid="crosshair-readout" className={`pointer-events-none absolute ${bare ? 'top-6' : 'top-2'} left-2 rounded-md border border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 px-2 py-1.5 text-[10px] leading-4 shadow-sm`}>
            <div className="font-medium text-slate-700 dark:text-slate-300">
              {readout.date}
              {compact && readout.bar && <span className="font-normal tabular-nums"> · C {readout.bar.close.toFixed(2)}</span>}
            </div>
            {!compact && readout.bar && (
              <div className="text-slate-500 dark:text-slate-400 tabular-nums">
                O {readout.bar.open.toFixed(2)} · H {readout.bar.high.toFixed(2)} · L{' '}
                {readout.bar.low.toFixed(2)} · C {readout.bar.close.toFixed(2)}
              </div>
            )}
            {!compact && readout.panes.map((p) => (
              <div key={p.id} className="tabular-nums" style={{ color: p.color }}>
                {p.label}: {p.value}
              </div>
            ))}
          </div>
        )}
      </div>
      </div>
      {!compact && !chrome?.rangeBar && <p className="text-xs text-slate-600 dark:text-slate-400 mt-2">{footText}</p>}
    </div>
  );
}
