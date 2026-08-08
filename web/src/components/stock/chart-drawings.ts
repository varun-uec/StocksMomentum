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
}

const EMPTY_STATE: RenderState = { drawings: [], draft: null, cursor: null };

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
        this._renderDrawing(context, mediaSize.width, chart, priceSeries, drawing);
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
    drawing: ChartDrawing
  ): void {
    ctx.strokeStyle = drawing.color;
    ctx.lineWidth = 1.5;
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