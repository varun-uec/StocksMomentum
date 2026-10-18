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
export const DEFAULT_WORKSPACE: WorkspaceBody = { active_chart_id: null, right_panel: 'watchlist', charts: {} };

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
