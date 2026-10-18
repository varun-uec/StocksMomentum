/**
 * Phase 9 — lightweight drawing-tool layer for the price chart.
 *
 * lightweight-charts v5 ships no drawing tools, so this module implements a thin
 * one using the library's pane-primitive (plugin) API: one primitive attached to
 * the price pane renders every persisted drawing plus any in-progress draft.
 *
 * The layer is deliberately dumb — it does not own tool state. PriceChart owns
 * the active tool, click handling, and the drawing list; this module only maps
 * `{date, price}` anchors to pane coordinates and paints them. ChartDrawing
 * instances are plain JSON (they round-trip through localStorage for Phase 9.5
 * persistence) plus a stable `id`.
 */

import type {
  IChartApi,
  IPanePrimitive,
  IPanePrimitivePaneView,
  IPrimitivePaneRenderer,
  ISeriesApi,
  PaneAttachedParameter,
  Time,
  UTCTimestamp,
} from 'lightweight-charts';
import type { CanvasRenderingTarget2D } from 'fancy-canvas';

export type DrawingKind = 'trendline' | 'horizontal' | 'rectangle' | 'fib';

export const DRAWING_KINDS: DrawingKind[] = ['trendline', 'horizontal', 'rectangle', 'fib'];

export const DRAWING_LABELS: Record<DrawingKind, string> = {
  trendline: 'Trendline',
  horizontal: 'Horizontal ray',
  rectangle: 'Rectangle',
  fib: 'Fib retracement',
};

/** Points a tool needs until it is complete. */
export const DRAWING_REQUIRED_POINTS: Record<DrawingKind, number> = {
  trendline: 2,
  horizontal: 1,
  rectangle: 2,
  fib: 2,
};

export interface DrawingPoint {
  /** ISO bar date (`YYYY-MM-DD`), the format every chart prop already uses. */
  date: string;
  price: number;
}

export interface ChartDrawing {
  id: string;
  kind: DrawingKind;
  points: DrawingPoint[];
  color: string;
}

/** Chart Drawing state is plain JSON; the `fib` ratios are the standard ones. */
export const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1] as const;

export function toTime(isoDate: string): UTCTimestamp {
  return (Date.parse(`${isoDate}T00:00:00Z`) / 1000) as UTCTimestamp;
}

export function fromTime(timestamp: UTCTimestamp): string {
  return new Date(timestamp * 1000).toISOString().slice(0, 10);
}

/** A locally-unique drawing id (no crypto requirement in every context). */
export function drawingId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export const DRAWING_COLOR = '#6366f1';

// ── Geometry (pure; unit-tested in chart-drawings.test.ts) ────────────────

export interface ScreenPoint {
  x: number;
  y: number;
}

/** Which part of a drawing the pointer is on: the whole shape, or one anchor. */
export type DrawingPart = 'body' | number;

/** Pointer distance, in px, within which an anchor handle is grabbed. */
export const HANDLE_RADIUS = 6;
/** Pointer distance, in px, within which a line is hit. */
const LINE_TOLERANCE = 5;

function distance(a: ScreenPoint, b: ScreenPoint): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function distanceToSegment(p: ScreenPoint, a: ScreenPoint, b: ScreenPoint): number {
  const lengthSq = (b.x - a.x) ** 2 + (b.y - a.y) ** 2;
  if (lengthSq === 0) return distance(p, a);
  const t = Math.max(0, Math.min(1, ((p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)) / lengthSq));
  return distance(p, { x: a.x + t * (b.x - a.x), y: a.y + t * (b.y - a.y) });
}

/**
 * Hit-test one drawing at `at`. `points` are the drawing's anchors in pane
 * coordinates (null when off-screen). Anchors win over the body, so a handle
 * on top of a line grabs the handle.
 */
export function hitTest(kind: DrawingKind, points: (ScreenPoint | null)[], at: ScreenPoint): DrawingPart | null {
  for (let i = 0; i < points.length; i += 1) {
    const p = points[i];
    if (p && distance(p, at) <= HANDLE_RADIUS) return i;
  }
  const [a, b] = points;
  if (!a || (kind !== 'horizontal' && !b)) return null;
  switch (kind) {
    case 'horizontal':
      return at.x >= a.x - LINE_TOLERANCE && Math.abs(at.y - a.y) <= LINE_TOLERANCE ? 'body' : null;
    case 'trendline':
      return distanceToSegment(at, a, b!) <= LINE_TOLERANCE ? 'body' : null;
    case 'rectangle': {
      const inX = at.x >= Math.min(a.x, b!.x) - LINE_TOLERANCE && at.x <= Math.max(a.x, b!.x) + LINE_TOLERANCE;
      const inY = at.y >= Math.min(a.y, b!.y) - LINE_TOLERANCE && at.y <= Math.max(a.y, b!.y) + LINE_TOLERANCE;
      return inX && inY ? 'body' : null;
    }
    case 'fib': {
      const inX = at.x >= Math.min(a.x, b!.x) - LINE_TOLERANCE && at.x <= Math.max(a.x, b!.x) + LINE_TOLERANCE;
      const lo = Math.min(a.y, b!.y);
      const hi = Math.max(a.y, b!.y);
      const nearLevel = FIB_LEVELS.some((ratio) => Math.abs(at.y - (hi + (lo - hi) * ratio)) <= LINE_TOLERANCE);
      return inX && nearLevel ? 'body' : null;
    }
  }
}

/** The topmost drawing under the pointer: the last one drawn wins, as it paints on top. */
export function hitTestAll(
  drawings: { id: string; kind: DrawingKind; points: (ScreenPoint | null)[] }[],
  at: ScreenPoint,
): { id: string; part: DrawingPart } | null {
  for (let i = drawings.length - 1; i >= 0; i -= 1) {
    const part = hitTest(drawings[i].kind, drawings[i].points, at);
    if (part !== null) return { id: drawings[i].id, part };
  }
  return null;
}

/**
 * Move a drawing by a whole number of bars and a price offset per anchor.
 * `body` moves every anchor; an anchor index moves that anchor only. Bar
 * indices clamp to the loaded range, so a drawing never lands off the data.
 */
export function moveDrawing(
  drawing: ChartDrawing,
  part: DrawingPart,
  barShift: number,
  newPrices: number[],
  barDates: string[],
): ChartDrawing {
  const indexOf = new Map(barDates.map((d, i) => [d, i]));
  const points = drawing.points.map((point, i) => {
    if (part !== 'body' && part !== i) return point;
    const from = indexOf.get(point.date);
    const date = from === undefined ? point.date : barDates[Math.max(0, Math.min(barDates.length - 1, from + barShift))];
    return { date, price: newPrices[i] ?? point.price };
  });
  return { ...drawing, points };
}

// ── Rendering ─────────────────────────────────────────────────────────────

/** Resolves the price series of the price pane at render time; the series is
 * rebuilt on the candlestick/line toggle, so the layer must not cache it. */
export type PriceSeriesRef = () => ISeriesApi<'Candlestick' | 'Line'> | null;

interface RenderablePoint {
  date: string;
  price: number;
}

interface RenderState {
  drawings: ChartDrawing[];
  draft: RenderablePoint[] | null;
  cursor: RenderablePoint | null;
  /** The selected drawing, painted thicker with its anchor handles. */
  selectedId: string | null;
}

const EMPTY_STATE: RenderState = { drawings: [], draft: null, cursor: null, selectedId: null };

class DrawingsPrimitive implements IPanePrimitive<Time> {
  private _chart: IChartApi | null = null;
  private _requestUpdate: (() => void) | null = null;
  private _state: RenderState = EMPTY_STATE;
  private readonly _priceSeries: PriceSeriesRef;

  constructor(priceSeries: PriceSeriesRef) {
    this._priceSeries = priceSeries;
  }

  attached(params: PaneAttachedParameter): void {
    this._chart = params.chart;
    this._requestUpdate = params.requestUpdate;
  }

  detached(): void {
    this._chart = null;
    this._requestUpdate = null;
  }

  updateState(state: RenderState): void {
    this._state = state;
  }

  requestRender(): void {
    this._requestUpdate?.();
  }

  /** Chart instance, or null while the primitive is detached. */
  chart(): IChartApi | null {
    return this._chart;
  }

  state(): RenderState {
    return this._state;
  }

  /** Current price-pane series for price↔coordinate conversion. */
  priceSeries(): ISeriesApi<'Candlestick' | 'Line'> | null {
    return this._priceSeries();
  }

  paneViews(): readonly IPanePrimitivePaneView[] {
    return [new DrawingsPaneView(this)];
  }
}

class DrawingsPaneView implements IPanePrimitivePaneView {
  private readonly _primitive: DrawingsPrimitive;

  constructor(primitive: DrawingsPrimitive) {
    this._primitive = primitive;
  }

  renderer(): IPrimitivePaneRenderer | null {
    return new DrawingsPaneRenderer(this._primitive);
  }
}

class DrawingsPaneRenderer implements IPrimitivePaneRenderer {
  private readonly _primitive: DrawingsPrimitive;

  constructor(primitive: DrawingsPrimitive) {
    this._primitive = primitive;
  }

  draw(target: CanvasRenderingTarget2D): void {
    const chart = this._primitive.chart();
    if (!chart) return;
    const state = this._primitive.state();
    const priceSeries = this._primitive.priceSeries();
    if (!priceSeries) return;

    target.useMediaCoordinateSpace(({ context, mediaSize }) => {
      context.lineCap = 'round';
      for (const drawing of state.drawings) {
        const selected = drawing.id === state.selectedId;
        this._renderDrawing(context, mediaSize.width, chart, priceSeries, drawing, selected);
        if (selected) this._paintHandles(context, chart, priceSeries, drawing);
      }
      if (state.draft?.length) {
        this._paintDraft(context, chart, priceSeries, state.draft, state.cursor);
      }
    });
  }

  /** Map a stored point to on-pane coordinates; null when outside the scales. */
  private static _screen(
    chart: IChartApi,
    series: ISeriesApi<'Candlestick' | 'Line'>,
    point: RenderablePoint
  ): { x: number; y: number } | null {
    const x = chart.timeScale().timeToCoordinate(toTime(point.date));
    const y = series.priceToCoordinate(point.price);
    if (x == null || y == null) return null;
    return { x, y };
  }

  private _renderDrawing(
    ctx: CanvasRenderingContext2D,
    paneWidth: number,
    chart: IChartApi,
    series: ISeriesApi<'Candlestick' | 'Line'>,
    drawing: ChartDrawing,
    selected: boolean
  ): void {
    ctx.strokeStyle = drawing.color;
    ctx.lineWidth = selected ? 2.5 : 1.5;
    ctx.setLineDash([]);

    switch (drawing.kind) {
      case 'horizontal': {
        const p = drawing.points[0];
        if (!p) break;
        const x0 = chart.timeScale().timeToCoordinate(toTime(p.date));
        const y = series.priceToCoordinate(p.price);
        if (x0 == null || y == null) break;
        ctx.beginPath();
        ctx.moveTo(x0, y);
        ctx.lineTo(paneWidth, y);
        ctx.stroke();
        break;
      }
      case 'trendline': {
        const a = DrawingsPaneRenderer._screen(chart, series, drawing.points[0]);
        const b = DrawingsPaneRenderer._screen(chart, series, drawing.points[1]);
        if (a && b) {
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        break;
      }
      case 'rectangle': {
        const a = DrawingsPaneRenderer._screen(chart, series, drawing.points[0]);
        const b = DrawingsPaneRenderer._screen(chart, series, drawing.points[1]);
        if (a && b) ctx.strokeRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y));
        break;
      }
      case 'fib': {
        const a = DrawingsPaneRenderer._screen(chart, series, drawing.points[0]);
        const b = DrawingsPaneRenderer._screen(chart, series, drawing.points[1]);
        if (!a || !b) break;
        const lo = Math.min(a.y, b.y);
        const hi = Math.max(a.y, b.y);
        const startX = Math.min(a.x, b.x);
        const endX = Math.max(a.x, b.x);
        // The base line (0%↔100%) plus each retracement level, right-labelled.
        for (const ratio of FIB_LEVELS) {
          const y = hi + (lo - hi) * ratio;
          ctx.strokeStyle = ratio === 0 || ratio === 1 ? drawing.color : `${drawing.color}80`;
          ctx.lineWidth = ratio === 0 || ratio === 1 ? 1.5 : 1;
          ctx.beginPath();
          ctx.moveTo(startX, y);
          ctx.lineTo(endX, y);
          ctx.stroke();
          ctx.fillStyle = drawing.color;
          ctx.font = '10px sans-serif';
          ctx.textAlign = 'left';
          ctx.fillText(`${ratio}`, endX + 4, y + 3);
        }
        ctx.strokeStyle = drawing.color;
        ctx.lineWidth = 1.5;
        break;
      }
    }
  }

  private _paintHandles(
    ctx: CanvasRenderingContext2D,
    chart: IChartApi,
    series: ISeriesApi<'Candlestick' | 'Line'>,
    drawing: ChartDrawing
  ): void {
    for (const point of drawing.points) {
      const p = DrawingsPaneRenderer._screen(chart, series, point);
      if (!p) continue;
      ctx.beginPath();
      ctx.arc(p.x, p.y, HANDLE_RADIUS - 2, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = drawing.color;
      ctx.stroke();
    }
  }

  private _paintDraft(
    ctx: CanvasRenderingContext2D,
    chart: IChartApi,
    series: ISeriesApi<'Candlestick' | 'Line'>,
    draft: RenderablePoint[],
    cursor: RenderablePoint | null
  ): void {
    ctx.strokeStyle = DRAWING_COLOR;
    ctx.lineWidth = 1.25;
    ctx.setLineDash([4, 4]);
    const preview = cursor ? [...draft, cursor] : draft;
    if (preview[0] && preview[1]) {
      const a = DrawingsPaneRenderer._screen(chart, series, preview[0]);
      const b = DrawingsPaneRenderer._screen(chart, series, preview[1]);
      if (a && b) {
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
    ctx.setLineDash([]);
  }
}

export interface DrawingsLayer {
  /** Push the current drawings/draft state and repaint. */
  update(state: RenderState): void;
  /** Detach the primitive from the price pane. */
  detach(): void;
}

/** Attach one drawings primitive to the price pane (pane 0).
 *
 * The pane is used rather than a series so the drawings survive a candlestick/
 * line series rebuild untouched. The price-series resolver is consulted at each
 * render, because the price series object is recreated on every series rebuild
 * and `priceToCoordinate` only exists on series. */
export function attachDrawingsLayer(
  chart: IChartApi,
  priceSeries: PriceSeriesRef
): DrawingsLayer {
  const primitive = new DrawingsPrimitive(priceSeries);
  const pane = chart.panes()[0];
  pane.attachPrimitive(primitive);
  return {
    update: (state: RenderState) => {
      primitive.updateState(state);
      primitive.requestRender();
    },
    detach: () => pane.detachPrimitive(primitive),
  };
}