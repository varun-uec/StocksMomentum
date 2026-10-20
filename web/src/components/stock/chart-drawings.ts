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
import { sameJson } from '@/lib/merge';

export type DrawingKind =
  | 'trendline'
  | 'ray'
  | 'extended'
  | 'horizontal'
  | 'hline'
  | 'vline'
  | 'crossline'
  | 'channel'
  | 'rectangle'
  | 'fib'
  | 'price_range'
  | 'text'
  // Phase B3: additive kinds; documents saved before them still load.
  | 'arrow'
  | 'date_range'
  | 'date_price_range'
  | 'ellipse'
  | 'triangle'
  | 'fib_extension'
  | 'pitchfork'
  | 'callout'
  | 'price_label';

export const DRAWING_KINDS: DrawingKind[] = [
  'trendline',
  'ray',
  'extended',
  'horizontal',
  'hline',
  'vline',
  'crossline',
  'channel',
  'rectangle',
  'fib',
  'price_range',
  'text',
  'arrow',
  'date_range',
  'date_price_range',
  'ellipse',
  'triangle',
  'fib_extension',
  'pitchfork',
  'callout',
  'price_label',
];

export const DRAWING_LABELS: Record<DrawingKind, string> = {
  trendline: 'Trendline',
  ray: 'Ray',
  extended: 'Extended line',
  horizontal: 'Horizontal ray',
  hline: 'Horizontal line',
  vline: 'Vertical line',
  crossline: 'Cross line',
  channel: 'Parallel channel',
  rectangle: 'Rectangle',
  fib: 'Fib retracement',
  price_range: 'Price range',
  text: 'Text note',
  arrow: 'Arrow',
  date_range: 'Date range',
  date_price_range: 'Date and price range',
  ellipse: 'Ellipse',
  triangle: 'Triangle',
  fib_extension: 'Trend-based Fib extension',
  pitchfork: 'Pitchfork',
  callout: 'Callout',
  price_label: 'Price label',
};

/** Points a tool needs until it is complete. */
export const DRAWING_REQUIRED_POINTS: Record<DrawingKind, number> = {
  trendline: 2,
  ray: 2,
  extended: 2,
  horizontal: 1,
  hline: 1,
  vline: 1,
  crossline: 1,
  channel: 3,
  rectangle: 2,
  fib: 2,
  price_range: 2,
  text: 1,
  arrow: 2,
  date_range: 2,
  date_price_range: 2,
  ellipse: 2,
  triangle: 3,
  fib_extension: 3,
  pitchfork: 3,
  callout: 2,
  price_label: 1,
};

/** Saved drawings an EOD close alert can watch (ADR-013 amendments): levels, a zone, sloped lines. */
export const ALERTABLE_KINDS: ReadonlySet<string> = new Set(['hline', 'horizontal', 'rectangle', 'trendline', 'ray', 'extended']);
/** The sloped ones: their level changes by session, so they have no single price line. */
export const SLOPED_KINDS: ReadonlySet<string> = new Set(['trendline', 'ray', 'extended']);

/** Kinds that carry text the owner writes; the note editor opens when one is placed. */
export const TEXT_KINDS: ReadonlySet<DrawingKind> = new Set(['text', 'callout']);

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
  /** Line width in px, 1 to 4. The server fills 2 for drawings saved before M13. */
  width?: number;
  locked?: boolean;
  hidden?: boolean;
  dash?: 'solid' | 'dashed' | 'dotted';
  /** A text note's text; null for every other kind. */
  text?: string | null;
}

/** Colours the context menu offers. */
export const DRAWING_COLORS = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#64748b'];
export const DRAWING_WIDTHS = [1, 2, 3, 4];

/** Chart Drawing state is plain JSON; the `fib` ratios are the standard ones. */
export const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1] as const;
/** Trend-based extension ratios, projected from the third anchor by the a→b move. */
export const FIB_EXTENSION_LEVELS = [0, 0.618, 1, 1.272, 1.618, 2.618] as const;

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

/** Distance from `p` to the line through `a` and `b`; `from` 0 makes it a ray from `a`, -Infinity a full line. */
function distanceToLine(p: ScreenPoint, a: ScreenPoint, b: ScreenPoint, from: number): number {
  const lengthSq = (b.x - a.x) ** 2 + (b.y - a.y) ** 2;
  if (lengthSq === 0) return distance(p, a);
  const t = Math.max(from, ((p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)) / lengthSq);
  return distance(p, { x: a.x + t * (b.x - a.x), y: a.y + t * (b.y - a.y) });
}

/** The channel's parallel line: segment a→b shifted so it passes through c. */
export function channelOffset(a: ScreenPoint, b: ScreenPoint, c: ScreenPoint): { a: ScreenPoint; b: ScreenPoint } {
  const t = b.x === a.x ? 0 : (c.x - a.x) / (b.x - a.x);
  const lineY = a.y + t * (b.y - a.y);
  const dy = c.y - lineY;
  return { a: { x: a.x, y: a.y + dy }, b: { x: b.x, y: b.y + dy } };
}

/** The y of each extension level, and the x span the levels draw over (right of the third anchor). */
export function fibExtensionLevels(a: ScreenPoint, b: ScreenPoint, c: ScreenPoint): { ratio: number; y: number }[] & { from: number; to: number } {
  const levels = FIB_EXTENSION_LEVELS.map((ratio) => ({ ratio, y: c.y + (b.y - a.y) * ratio }));
  return Object.assign(levels, { from: c.x, to: c.x + Math.max(40, Math.abs(b.x - a.x)) });
}

/**
 * Andrews' pitchfork: the median line runs from the pivot `a` through the
 * midpoint of `b` and `c`; the two tines start at `b` and `c`, parallel to it.
 * Each line is a start and a direction; all three are rays.
 */
export function pitchforkLines(a: ScreenPoint, b: ScreenPoint, c: ScreenPoint): { start: ScreenPoint; dir: ScreenPoint }[] {
  const dir = { x: (b.x + c.x) / 2 - a.x, y: (b.y + c.y) / 2 - a.y };
  return [a, b, c].map((start) => ({ start, dir }));
}

/** Whether `p` lies inside triangle a-b-c (either winding). */
export function inTriangle(p: ScreenPoint, a: ScreenPoint, b: ScreenPoint, c: ScreenPoint): boolean {
  const side = (u: ScreenPoint, v: ScreenPoint) => (p.x - v.x) * (u.y - v.y) - (u.x - v.x) * (p.y - v.y);
  const [d1, d2, d3] = [side(a, b), side(b, c), side(c, a)];
  return !((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0));
}

/** The box a price label occupies, right of its anchor. */
export function priceLabelBox(at: ScreenPoint): { x: number; y: number; w: number; h: number } {
  return { x: at.x + 6, y: at.y - 9, w: 64, h: 18 };
}

/** The box a text note occupies, right of its anchor. */
export function textBox(at: ScreenPoint, text: string): { x: number; y: number; w: number; h: number } {
  return { x: at.x, y: at.y - 14, w: Math.max(24, text.length * 6.5 + 8), h: 18 };
}

/**
 * Hit-test one drawing at `at`. `points` are the drawing's anchors in pane
 * coordinates (null when off-screen). Anchors win over the body, so a handle
 * on top of a line grabs the handle.
 */
export function hitTest(kind: DrawingKind, points: (ScreenPoint | null)[], at: ScreenPoint, text = ''): DrawingPart | null {
  for (let i = 0; i < points.length; i += 1) {
    const p = points[i];
    if (p && distance(p, at) <= HANDLE_RADIUS) return i;
  }
  const [a, b, c] = points;
  if (!a || points.length < DRAWING_REQUIRED_POINTS[kind] || points.slice(0, DRAWING_REQUIRED_POINTS[kind]).some((p) => !p)) return null;
  const inBox = (box: { x: number; y: number; w: number; h: number }) => at.x >= box.x && at.x <= box.x + box.w && at.y >= box.y && at.y <= box.y + box.h;
  const hit = (near: boolean): DrawingPart | null => (near ? 'body' : null);
  switch (kind) {
    case 'horizontal':
      return hit(at.x >= a.x - LINE_TOLERANCE && Math.abs(at.y - a.y) <= LINE_TOLERANCE);
    case 'hline':
      return hit(Math.abs(at.y - a.y) <= LINE_TOLERANCE);
    case 'vline':
      return hit(Math.abs(at.x - a.x) <= LINE_TOLERANCE);
    case 'crossline':
      return hit(Math.abs(at.y - a.y) <= LINE_TOLERANCE || Math.abs(at.x - a.x) <= LINE_TOLERANCE);
    case 'ray':
      return hit(distanceToLine(at, a, b!, 0) <= LINE_TOLERANCE);
    case 'extended':
      return hit(distanceToLine(at, a, b!, -Infinity) <= LINE_TOLERANCE);
    case 'channel': {
      const other = channelOffset(a, b!, c!);
      return hit(distanceToSegment(at, a, b!) <= LINE_TOLERANCE || distanceToSegment(at, other.a, other.b) <= LINE_TOLERANCE);
    }
    case 'text': {
      const box = textBox(a, text);
      return hit(at.x >= box.x && at.x <= box.x + box.w && at.y >= box.y && at.y <= box.y + box.h);
    }
    case 'trendline':
      return distanceToSegment(at, a, b!) <= LINE_TOLERANCE ? 'body' : null;
    case 'arrow':
      return hit(distanceToSegment(at, a, b!) <= LINE_TOLERANCE);
    case 'ellipse': {
      const [rx, ry] = [Math.abs(b!.x - a.x) / 2 + LINE_TOLERANCE, Math.abs(b!.y - a.y) / 2 + LINE_TOLERANCE];
      const [cx, cy] = [(a.x + b!.x) / 2, (a.y + b!.y) / 2];
      return hit(((at.x - cx) / rx) ** 2 + ((at.y - cy) / ry) ** 2 <= 1);
    }
    case 'triangle':
      return hit(inTriangle(at, a, b!, c!) || [[a, b], [b, c], [c, a]].some(([u, v]) => distanceToSegment(at, u!, v!) <= LINE_TOLERANCE));
    case 'fib_extension': {
      const levels = fibExtensionLevels(a, b!, c!);
      const inX = at.x >= levels.from - LINE_TOLERANCE && at.x <= levels.to + LINE_TOLERANCE;
      return hit((inX && levels.some((l) => Math.abs(at.y - l.y) <= LINE_TOLERANCE)) || distanceToSegment(at, a, b!) <= LINE_TOLERANCE || distanceToSegment(at, b!, c!) <= LINE_TOLERANCE);
    }
    case 'pitchfork':
      return hit(pitchforkLines(a, b!, c!).some(({ start, dir }) => distanceToLine(at, start, { x: start.x + dir.x, y: start.y + dir.y }, 0) <= LINE_TOLERANCE));
    case 'callout':
      return hit(inBox(textBox(b!, text)) || distanceToSegment(at, a, b!) <= LINE_TOLERANCE);
    case 'price_label':
      return hit(inBox(priceLabelBox(a)));
    case 'date_range':
    case 'date_price_range':
    case 'price_range':
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
  drawings: { id: string; kind: DrawingKind; points: (ScreenPoint | null)[]; text?: string }[],
  at: ScreenPoint,
): { id: string; part: DrawingPart } | null {
  for (let i = drawings.length - 1; i >= 0; i -= 1) {
    const part = hitTest(drawings[i].kind, drawings[i].points, at, drawings[i].text);
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

// ── Undo and redo (pure; unit-tested) ─────────────────────────────────────

/** One drawing before and after an edit; null means absent (added or deleted). */
export interface DrawingChange {
  id: string;
  before: ChartDrawing | null;
  after: ChartDrawing | null;
}

/** The drawings an edit changed. */
export function diffDrawings(prev: ChartDrawing[], next: ChartDrawing[]): DrawingChange[] {
  const before = new Map(prev.map((d) => [d.id, d]));
  const after = new Map(next.map((d) => [d.id, d]));
  const changes: DrawingChange[] = [];
  for (const id of new Set([...before.keys(), ...after.keys()])) {
    const [b, a] = [before.get(id) ?? null, after.get(id) ?? null];
    if (!sameJson(b, a)) changes.push({ id, before: b, after: a });
  }
  return changes;
}

/**
 * Apply one side of recorded changes to the current list. Only the changed
 * drawings move, so undo never reverts what another window did meanwhile.
 */
export function applyDrawingChanges(list: ChartDrawing[], changes: DrawingChange[], side: 'before' | 'after'): ChartDrawing[] {
  let out = [...list];
  for (const change of changes) {
    const target = change[side];
    const index = out.findIndex((d) => d.id === change.id);
    if (target === null) out = out.filter((d) => d.id !== change.id);
    else if (index >= 0) out[index] = target;
    else out.push(target);
  }
  return out;
}

// ── Rendering ─────────────────────────────────────────────────────────────

/** Resolves the price series of the price pane at render time; the series is
 * rebuilt on the candlestick/line toggle, so the layer must not cache it. */
/** The price pane's main series, whatever the chart type. */
export type PriceSeries = ISeriesApi<'Candlestick' | 'Bar' | 'Line' | 'Area'>;

export type PriceSeriesRef = () => PriceSeries | null;

interface RenderablePoint {
  date: string;
  price: number;
}

interface RenderState {
  drawings: ChartDrawing[];
  draft: RenderablePoint[] | null;
  /** The tool the draft belongs to, so its preview has the final shape. */
  draftKind?: DrawingKind | null;
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
  priceSeries(): PriceSeries | null {
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
        if (drawing.hidden) continue;
        const selected = drawing.id === state.selectedId;
        this._renderDrawing(context, mediaSize, chart, priceSeries, drawing, selected);
        if (selected && !drawing.locked) this._paintHandles(context, chart, priceSeries, drawing);
      }
      if (state.draft?.length) {
        this._paintDraft(context, mediaSize, chart, priceSeries, state);
      }
    });
  }

  /** Map a stored point to on-pane coordinates; null when outside the scales. */
  private static _screen(
    chart: IChartApi,
    series: PriceSeries,
    point: RenderablePoint
  ): { x: number; y: number } | null {
    const x = chart.timeScale().timeToCoordinate(toTime(point.date));
    const y = series.priceToCoordinate(point.price);
    if (x == null || y == null) return null;
    return { x, y };
  }

  private _renderDrawing(
    ctx: CanvasRenderingContext2D,
    pane: { width: number; height: number },
    chart: IChartApi,
    series: PriceSeries,
    drawing: ChartDrawing,
    selected: boolean
  ): void {
    const width = drawing.width ?? 2;
    ctx.strokeStyle = drawing.color;
    ctx.lineWidth = selected ? width + 1 : width;
    ctx.setLineDash(drawing.dash === 'dashed' ? [7, 5] : drawing.dash === 'dotted' ? [2, 4] : []);
    const screen = (i: number) => (drawing.points[i] ? DrawingsPaneRenderer._screen(chart, series, drawing.points[i]) : null);
    const line = (a: ScreenPoint, b: ScreenPoint) => {
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    };
    /** Extend a→b to the pane edge; both ways when `both`. */
    const extend = (a: ScreenPoint, b: ScreenPoint, both: boolean) => {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const reach = (pane.width + pane.height) / Math.max(1e-6, Math.hypot(dx, dy)) + 1;
      line(both ? { x: a.x - dx * reach, y: a.y - dy * reach } : a, { x: a.x + dx * reach, y: a.y + dy * reach });
    };

    switch (drawing.kind) {
      case 'horizontal': {
        const a = screen(0);
        if (a) line(a, { x: pane.width, y: a.y });
        break;
      }
      case 'hline': {
        const y = drawing.points[0] ? series.priceToCoordinate(drawing.points[0].price) : null;
        if (y != null) line({ x: 0, y }, { x: pane.width, y });
        break;
      }
      case 'vline': {
        const x = drawing.points[0] ? chart.timeScale().timeToCoordinate(toTime(drawing.points[0].date)) : null;
        if (x != null) line({ x, y: 0 }, { x, y: pane.height });
        break;
      }
      case 'crossline': {
        const a = screen(0);
        if (!a) break;
        line({ x: 0, y: a.y }, { x: pane.width, y: a.y });
        line({ x: a.x, y: 0 }, { x: a.x, y: pane.height });
        break;
      }
      case 'trendline': {
        const [a, b] = [screen(0), screen(1)];
        if (a && b) line(a, b);
        break;
      }
      case 'ray':
      case 'extended': {
        const [a, b] = [screen(0), screen(1)];
        if (a && b) extend(a, b, drawing.kind === 'extended');
        break;
      }
      case 'channel': {
        const [a, b, c] = [screen(0), screen(1), screen(2)];
        if (!a || !b) break;
        line(a, b);
        if (!c) break;
        const other = channelOffset(a, b, c);
        line(other.a, other.b);
        ctx.fillStyle = `${drawing.color}14`;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.lineTo(other.b.x, other.b.y);
        ctx.lineTo(other.a.x, other.a.y);
        ctx.closePath();
        ctx.fill();
        break;
      }
      case 'rectangle': {
        const [a, b] = [screen(0), screen(1)];
        if (a && b) ctx.strokeRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y));
        break;
      }
      case 'price_range': {
        const [a, b] = [screen(0), screen(1)];
        const [pa, pb] = drawing.points;
        if (!a || !b || !pa || !pb) break;
        const up = pb.price >= pa.price;
        ctx.fillStyle = up ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)';
        ctx.fillRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y));
        line({ x: (a.x + b.x) / 2, y: a.y }, { x: (a.x + b.x) / 2, y: b.y });
        const change = pb.price - pa.price;
        const pct = pa.price === 0 ? 0 : (change / pa.price) * 100;
        ctx.fillStyle = up ? '#059669' : '#dc2626';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${change >= 0 ? '+' : ''}${change.toFixed(2)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`, (a.x + b.x) / 2, Math.min(a.y, b.y) - 6);
        break;
      }
      case 'text': {
        const a = screen(0);
        if (!a) break;
        const box = textBox(a, drawing.text ?? '');
        ctx.fillStyle = `${drawing.color}22`;
        ctx.fillRect(box.x, box.y, box.w, box.h);
        if (selected) ctx.strokeRect(box.x, box.y, box.w, box.h);
        ctx.fillStyle = drawing.color;
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(drawing.text ?? '', box.x + 4, box.y + 13);
        break;
      }
      case 'arrow': {
        const [a, b] = [screen(0), screen(1)];
        if (!a || !b) break;
        line(a, b);
        // The head: two short strokes back from b, 28° either side of the shaft.
        const angle = Math.atan2(b.y - a.y, b.x - a.x);
        const size = 8 + width * 2;
        for (const side of [-1, 1]) line(b, { x: b.x - size * Math.cos(angle + side * 0.5), y: b.y - size * Math.sin(angle + side * 0.5) });
        break;
      }
      case 'ellipse': {
        const [a, b] = [screen(0), screen(1)];
        if (!a || !b) break;
        ctx.beginPath();
        ctx.ellipse((a.x + b.x) / 2, (a.y + b.y) / 2, Math.abs(b.x - a.x) / 2, Math.abs(b.y - a.y) / 2, 0, 0, Math.PI * 2);
        ctx.fillStyle = `${drawing.color}14`;
        ctx.fill();
        ctx.stroke();
        break;
      }
      case 'triangle': {
        const [a, b, c] = [screen(0), screen(1), screen(2)];
        if (!a || !b) break;
        if (!c) { line(a, b); break; }
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.lineTo(c.x, c.y);
        ctx.closePath();
        ctx.fillStyle = `${drawing.color}14`;
        ctx.fill();
        ctx.stroke();
        break;
      }
      case 'date_range':
      case 'date_price_range': {
        const [a, b] = [screen(0), screen(1)];
        const [pa, pb] = drawing.points;
        if (!a || !b || !pa || !pb) break;
        const [left, right, top, bottom] = [Math.min(a.x, b.x), Math.max(a.x, b.x), Math.min(a.y, b.y), Math.max(a.y, b.y)];
        ctx.fillStyle = `${drawing.color}1f`;
        ctx.fillRect(left, top, right - left, bottom - top);
        const midY = (top + bottom) / 2;
        line({ x: left, y: midY }, { x: right, y: midY });
        if (drawing.kind === 'date_price_range') line({ x: (left + right) / 2, y: top }, { x: (left + right) / 2, y: bottom });
        const index = (date: string) => chart.timeScale().timeToIndex(toTime(date), true) ?? 0;
        const bars = Math.abs(index(pb.date) - index(pa.date));
        const days = Math.round(Math.abs(Date.parse(pb.date) - Date.parse(pa.date)) / 86_400_000);
        const change = pb.price - pa.price;
        const pct = pa.price === 0 ? 0 : (change / pa.price) * 100;
        const label = `${bars} bars, ${days}d${drawing.kind === 'date_price_range' ? ` · ${change >= 0 ? '+' : ''}${change.toFixed(2)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)` : ''}`;
        ctx.fillStyle = drawing.color;
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(label, (left + right) / 2, bottom + 14);
        break;
      }
      case 'fib_extension': {
        const [a, b, c] = [screen(0), screen(1), screen(2)];
        if (!a || !b) break;
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1;
        line(a, b);
        if (c) line(b, c);
        ctx.setLineDash([]);
        if (!c) break;
        const levels = fibExtensionLevels(a, b, c);
        for (const { ratio, y } of levels) {
          ctx.strokeStyle = ratio === 0 || ratio === 1 ? drawing.color : `${drawing.color}80`;
          ctx.lineWidth = ratio === 0 || ratio === 1 ? width : 1;
          line({ x: levels.from, y }, { x: levels.to, y });
          ctx.fillStyle = drawing.color;
          ctx.font = '10px sans-serif';
          ctx.textAlign = 'left';
          ctx.fillText(`${ratio}`, levels.to + 4, y + 3);
        }
        break;
      }
      case 'pitchfork': {
        const [a, b, c] = [screen(0), screen(1), screen(2)];
        if (!a || !b) break;
        if (!c) { line(a, b); break; }
        line(b, c);
        for (const [i, { start, dir }] of pitchforkLines(a, b, c).entries()) {
          ctx.lineWidth = i === 0 ? width : Math.max(1, width - 1);
          extend(start, { x: start.x + dir.x, y: start.y + dir.y }, false);
        }
        break;
      }
      case 'callout': {
        const [a, b] = [screen(0), screen(1)];
        if (!a || !b) break;
        line(a, b);
        ctx.beginPath();
        ctx.arc(a.x, a.y, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = drawing.color;
        ctx.fill();
        const box = textBox(b, drawing.text ?? '');
        ctx.fillStyle = `${drawing.color}22`;
        ctx.fillRect(box.x, box.y, box.w, box.h);
        ctx.strokeRect(box.x, box.y, box.w, box.h);
        ctx.fillStyle = drawing.color;
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(drawing.text ?? '', box.x + 4, box.y + 13);
        break;
      }
      case 'price_label': {
        const a = screen(0);
        const price = drawing.points[0]?.price;
        if (!a || price === undefined) break;
        const box = priceLabelBox(a);
        ctx.fillStyle = drawing.color;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(box.x, box.y);
        ctx.lineTo(box.x + box.w, box.y);
        ctx.lineTo(box.x + box.w, box.y + box.h);
        ctx.lineTo(box.x, box.y + box.h);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(price.toFixed(2), box.x + box.w / 2, box.y + 13);
        break;
      }
      case 'fib': {
        const [a, b] = [screen(0), screen(1)];
        if (!a || !b) break;
        const lo = Math.min(a.y, b.y);
        const hi = Math.max(a.y, b.y);
        const startX = Math.min(a.x, b.x);
        const endX = Math.max(a.x, b.x);
        // The base line (0%↔100%) plus each retracement level, right-labelled.
        for (const ratio of FIB_LEVELS) {
          const y = hi + (lo - hi) * ratio;
          ctx.strokeStyle = ratio === 0 || ratio === 1 ? drawing.color : `${drawing.color}80`;
          ctx.lineWidth = ratio === 0 || ratio === 1 ? width : 1;
          line({ x: startX, y }, { x: endX, y });
          ctx.fillStyle = drawing.color;
          ctx.font = '10px sans-serif';
          ctx.textAlign = 'left';
          ctx.fillText(`${ratio}`, endX + 4, y + 3);
        }
        break;
      }
    }
  }

  private _paintHandles(
    ctx: CanvasRenderingContext2D,
    chart: IChartApi,
    series: PriceSeries,
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
    pane: { width: number; height: number },
    chart: IChartApi,
    series: PriceSeries,
    state: RenderState
  ): void {
    const draft = state.draft ?? [];
    const preview = state.cursor ? [...draft, state.cursor] : draft;
    const kind = state.draftKind;
    // Enough points for the final shape: preview it, dashed.
    if (kind && preview.length >= DRAWING_REQUIRED_POINTS[kind]) {
      ctx.save();
      ctx.globalAlpha = 0.7;
      this._renderDrawing(ctx, pane, chart, series, { id: 'draft', kind, points: preview, color: DRAWING_COLOR, text: '' }, false);
      ctx.restore();
      return;
    }
    ctx.strokeStyle = DRAWING_COLOR;
    ctx.lineWidth = 1.25;
    ctx.setLineDash([4, 4]);
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