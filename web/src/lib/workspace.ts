/**
 * The owner's workspace and drawings, stored on the server (ADR-013 §5).
 *
 * Presentation (range, moving averages, panes, indicators) belongs to a chart,
 * named by a stable `chartId`. Drawings belong to a symbol and appear on every
 * chart of that symbol.
 */

import type { components } from '@/lib/api-schema';
import { mergeById, mergeFields } from '@/lib/merge';
import { useServerDocument, type DocumentSpec, type MergeResult } from '@/lib/server-document';

type Schemas = components['schemas'];
export type WorkspaceBody = Schemas['WorkspaceV1'];
export type ChartSettings = Schemas['ChartV1'];
export type DrawingsBody = Schemas['SymbolDrawingsV1'];

/** One workspace per instance until M13 adds layouts. */
export const WORKSPACE_ID = 'default';

export const DEFAULT_CHART: ChartSettings = {
  symbol: null,
  range: '1Y',
  interval: '1D',
  chart_type: 'candles',
  scale: 'normal',
  mas: [50, 200],
  panes: [],
  indicators: [],
  preset_id: null,
  show_signals: true,
  preset_edited: false,
  compare: [],
};

/** A workspace before the owner changes anything. */
export const DEFAULT_WORKSPACE: WorkspaceBody = {
  active_chart_id: null,
  right_panel: 'watchlist',
  layout: '1x1',
  sync: { symbol: false, interval: false, crosshair: true },
  charts: {},
};

function withoutCharts(ws: WorkspaceBody): Record<string, unknown> {
  return Object.fromEntries(Object.entries(ws).filter(([key]) => key !== 'charts'));
}

/** Where the owner is, not what they set: the newest window wins (see `mergeFields`). */
const NAVIGATION_FIELDS = ['symbol', 'active_chart_id'] as const;

/**
 * Merge two workspaces chart by chart, field by field. A setting both windows
 * changed differently is a conflict, named `<chart id>.<field>`. A chart that
 * did not exist yet started from `DEFAULT_CHART`, so that is its base.
 */
export function mergeWorkspaces(base: WorkspaceBody | null, mine: WorkspaceBody, theirs: WorkspaceBody): MergeResult<WorkspaceBody> & { conflicts: string[] } {
  const charts = { mine: { ...theirs.charts }, theirs: { ...theirs.charts } };
  const conflicts: string[] = [];
  for (const [id, chart] of Object.entries(mine.charts)) {
    const r = mergeFields(base?.charts[id] ?? DEFAULT_CHART, chart, theirs.charts[id], NAVIGATION_FIELDS);
    charts.mine[id] = r.mine;
    charts.theirs[id] = r.theirs;
    conflicts.push(...r.conflicts.map((field) => `${id}.${field}`));
  }
  // Every field outside `charts` (the active chart, the side panel) merges the same way.
  const top = mergeFields(withoutCharts(base ?? DEFAULT_WORKSPACE), withoutCharts(mine), withoutCharts(theirs), NAVIGATION_FIELDS);
  conflicts.push(...top.conflicts);
  return {
    mine: { ...top.mine, charts: charts.mine } as WorkspaceBody,
    theirs: { ...top.theirs, charts: charts.theirs } as WorkspaceBody,
    conflicted: conflicts.length > 0,
    conflicts,
  };
}

export const workspaceSpec: DocumentSpec<WorkspaceBody> = {
  path: `/api/v1/workspaces/${WORKSPACE_ID}`,
  label: 'Your chart settings',
  defaults: () => DEFAULT_WORKSPACE,
  merge: mergeWorkspaces,
};

type Drawing = DrawingsBody['drawings'][number];
/** A drawing as the app builds it; the server fills `width` and `text` when absent. */
export type DrawingInput = Omit<Drawing, 'width' | 'text'> & Partial<Pick<Drawing, 'width' | 'text'>>;

/**
 * A drawings document: point prices are traded prices, adjusted only to draw
 * (ADR-013 §5). Each drawing carries the server's defaults written out, so
 * the saved copy and this one compare equal in a merge.
 */
export const drawingsBody = (drawings: DrawingInput[]): DrawingsBody => ({
  price_basis: 'traded',
  drawings: drawings.map((d) => ({ ...d, width: d.width ?? 2, text: d.text ?? null })),
});

const drawingSpecs = new Map<string, DocumentSpec<DrawingsBody>>();

export function drawingsSpec(symbol: string): DocumentSpec<DrawingsBody> {
  let spec = drawingSpecs.get(symbol);
  if (!spec) {
    spec = {
      path: `/api/v1/drawings/${encodeURIComponent(symbol)}`,
      label: `Your drawings on ${symbol}`,
      defaults: () => drawingsBody([]),
      merge: (base, mine, theirs) => {
        const r = mergeById(base?.drawings ?? [], mine.drawings, theirs.drawings);
        return { mine: drawingsBody(r.mine), theirs: drawingsBody(r.theirs), conflicted: r.conflicts.length > 0 };
      },
    };
    drawingSpecs.set(symbol, spec);
  }
  return spec;
}

/** One chart's presentation settings. */
export function useWorkspaceChart(chartId: string) {
  const doc = useServerDocument(workspaceSpec);
  const chart = doc.body.charts[chartId] ?? DEFAULT_CHART;
  return {
    chart,
    ready: doc.status !== 'loading',
    status: doc.status,
    savedAt: doc.savedAt,
    retry: doc.retry,
    update: (patch: Partial<ChartSettings>) =>
      doc.update((ws) => ({
        ...ws,
        active_chart_id: chartId,
        charts: { ...ws.charts, [chartId]: { ...(ws.charts[chartId] ?? DEFAULT_CHART), ...patch } },
      })),
  };
}

/** A symbol's drawings. */
export function useSymbolDrawings(symbol: string) {
  const doc = useServerDocument(drawingsSpec(symbol || '_'));
  return {
    drawings: doc.body.drawings,
    ready: doc.status !== 'loading',
    status: doc.status,
    savedAt: doc.savedAt,
    retry: doc.retry,
    update: (drawings: DrawingInput[]) => doc.update(() => drawingsBody(drawings)),
  };
}

export type RightPanel = WorkspaceBody['right_panel'];

/** The workspace's side panel: which tab is open, or none. */
export function useRightPanel(): { panel: RightPanel; ready: boolean; setPanel: (panel: RightPanel) => void } {
  const doc = useServerDocument(workspaceSpec);
  return {
    panel: doc.body.right_panel,
    ready: doc.status !== 'loading',
    setPanel: (panel) => doc.update((ws) => (ws.right_panel === panel ? ws : { ...ws, right_panel: panel })),
  };
}

export type Layout = WorkspaceBody['layout'];
export type LayoutSync = NonNullable<WorkspaceBody['sync']>;

/** The chart grids, columns × rows (M13). */
export const LAYOUTS: { id: Layout; label: string; cols: number; rows: number }[] = [
  { id: '1x1', label: 'One chart', cols: 1, rows: 1 },
  { id: '2x1', label: 'Two, side by side', cols: 2, rows: 1 },
  { id: '1x2', label: 'Two, stacked', cols: 1, rows: 2 },
  { id: '2x2', label: 'Four (2 × 2)', cols: 2, rows: 2 },
  { id: '3x3', label: 'Nine (3 × 3)', cols: 3, rows: 3 },
  { id: '4x4', label: 'Sixteen (4 × 4)', cols: 4, rows: 4 },
];

/** The stable chart id of grid slot `index`: the first slot is the single chart's own. */
export const slotChartId = (index: number): string => (index === 0 ? 'main' : `c${index + 1}`);

/**
 * `ws` switched to layout `id`. A cell the layout opens with no symbol of its
 * own gets the active chart's: without one it followed the active chart, so a
 * new 4 × 4 grid changed 15 charts at once even with symbol sync off.
 */
export function withLayout(ws: WorkspaceBody, id: Layout): WorkspaceBody {
  const layout = LAYOUTS.find((l) => l.id === id);
  if (!layout || ws.layout === id) return ws;
  // A research screen's chart (`stock`, `analysis`) can be the active one; the grid's is `main`.
  const activeId = ws.active_chart_id && /^(main|c\d+)$/.test(ws.active_chart_id) ? ws.active_chart_id : 'main';
  const symbol = ws.charts[activeId]?.symbol ?? ws.charts.main?.symbol ?? null;
  const charts = { ...ws.charts };
  for (let i = 0; i < layout.cols * layout.rows && symbol; i += 1) {
    const chartId = slotChartId(i);
    if (!charts[chartId]?.symbol) charts[chartId] = { ...(charts[chartId] ?? DEFAULT_CHART), symbol };
  }
  return { ...ws, layout: id, charts };
}

/**
 * The workspace's chart grid: its slots, which one is active, and what the
 * charts share. Any chart update marks its chart active, including the
 * research screens' charts, so an active id outside the grid means `main`.
 */
export function useLayout() {
  const doc = useServerDocument(workspaceSpec);
  const layout = LAYOUTS.find((l) => l.id === doc.body.layout) ?? LAYOUTS[0];
  const slots = Array.from({ length: layout.cols * layout.rows }, (_, i) => slotChartId(i));
  const activeId = doc.body.active_chart_id;
  return {
    layout,
    slots,
    active: activeId && slots.includes(activeId) ? activeId : 'main',
    sync: doc.body.sync ?? DEFAULT_WORKSPACE.sync!,
    charts: doc.body.charts,
    ready: doc.status !== 'loading',
    setLayout: (id: Layout) => doc.update((ws) => withLayout(ws, id)),
    setSync: (patch: Partial<LayoutSync>) =>
      doc.update((ws) => ({ ...ws, sync: { ...(ws.sync ?? DEFAULT_WORKSPACE.sync!), ...patch } })),
    setActive: (id: string) => doc.update((ws) => (ws.active_chart_id === id ? ws : { ...ws, active_chart_id: id })),
  };
}
