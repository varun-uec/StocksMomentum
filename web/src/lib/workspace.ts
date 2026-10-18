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
  mas: [50, 200],
  panes: [],
  indicators: [],
  preset_id: null,
  show_signals: true,
  preset_edited: false,
};

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
  const active = mergeFields(
    base ? { active_chart_id: base.active_chart_id } : undefined,
    { active_chart_id: mine.active_chart_id },
    { active_chart_id: theirs.active_chart_id },
    NAVIGATION_FIELDS,
  ).mine;
  return {
    mine: { ...active, charts: charts.mine },
    theirs: { ...active, charts: charts.theirs },
    conflicted: conflicts.length > 0,
    conflicts,
  };
}

export const workspaceSpec: DocumentSpec<WorkspaceBody> = {
  path: `/api/v1/workspaces/${WORKSPACE_ID}`,
  label: 'Your chart settings',
  defaults: () => ({ active_chart_id: null, charts: {} }),
  merge: mergeWorkspaces,
};

const drawingSpecs = new Map<string, DocumentSpec<DrawingsBody>>();

export function drawingsSpec(symbol: string): DocumentSpec<DrawingsBody> {
  let spec = drawingSpecs.get(symbol);
  if (!spec) {
    spec = {
      path: `/api/v1/drawings/${encodeURIComponent(symbol)}`,
      label: `Your drawings on ${symbol}`,
      defaults: () => ({ drawings: [] }),
      merge: (base, mine, theirs) => {
        const r = mergeById(base?.drawings ?? [], mine.drawings, theirs.drawings);
        return { mine: { drawings: r.mine }, theirs: { drawings: r.theirs }, conflicted: r.conflicts.length > 0 };
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
    update: (drawings: DrawingsBody['drawings']) => doc.update(() => ({ drawings })),
  };
}
