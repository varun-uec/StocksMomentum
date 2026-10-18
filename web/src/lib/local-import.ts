/**
 * One-time import of chart state saved in this browser before M11 (ADR-013 §5).
 *
 * Phase 9.5 kept drawings and chart settings in `localStorage` under
 * `chart-prefs:<symbol>`, and the analysis screen's indicators under
 * `chart-overlays:<symbol>`. Only the server copy is changed, never by
 * overwriting: the original keys stay in place as the backup.
 */

import { LEGACY_KEY_PREFIX, parseLegacyPreferences } from '@/lib/chart-preferences';
import { sameJson } from '@/lib/merge';
import { defaultOverlays, LEGACY_OVERLAY_KEY_PREFIX, parseLegacyOverlays } from '@/lib/overlay-preferences';
import { documentStore, reloadIfPristine } from '@/lib/server-document';
import { DEFAULT_CHART, drawingsBody, drawingsSpec, workspaceSpec, type ChartSettings, type WorkspaceBody } from '@/lib/workspace';

const MARKER_PREFIX = 'wickstreet:imported:';

function legacyKeys(): string[] {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key?.startsWith(LEGACY_KEY_PREFIX) && !localStorage.getItem(MARKER_PREFIX + key)) keys.push(key);
  }
  return keys;
}

/**
 * Drawings: each symbol's drawings are sent with `If-None-Match: *`, so the
 * import only creates documents that do not exist yet. A second browser, or a
 * second run, changes nothing (the server copy wins). A marker records each
 * finished key. Safe to call on every start.
 */
export async function importLocalDrawings(http: typeof fetch = (...a) => fetch(...a)): Promise<number> {
  let keys: string[];
  try {
    keys = legacyKeys();
  } catch {
    return 0; // storage unavailable: nothing to import
  }
  let imported = 0;
  for (const key of keys) {
    const symbol = key.slice(LEGACY_KEY_PREFIX.length);
    const { drawings } = parseLegacyPreferences(localStorage.getItem(key));
    if (drawings.length > 0) {
      const res = await http(drawingsSpec(symbol).path, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'If-None-Match': '*' },
        body: JSON.stringify(drawingsBody(drawings)), // as drawn on the raw chart: traded prices
      }).catch(() => null);
      // 201 imported; 412 the server already had them (server wins). Anything else: retry next start.
      if (!res || (res.status !== 201 && res.status !== 412)) continue;
      if (res.status === 201) {
        imported += 1;
        reloadIfPristine(drawingsSpec(symbol).path);
      }
    }
    localStorage.setItem(MARKER_PREFIX + key, new Date().toISOString());
  }
  return imported;
}

const PRESENTATION_MARKER = `${MARKER_PREFIX}presentation`;

/** The screens that had a chart before M11 share one setting per symbol; `main` is the M11 chart. */
const CHARTS_WITH_SETTINGS = ['main', 'stock', 'analysis', 'elliott-wave'];
/** Only the analysis screen showed catalogue indicators. */
const CHARTS_WITH_OVERLAYS = ['analysis'];
/** Server limits on a chart (ChartV1). */
const MAX_MAS = 8;
const MAX_PERIOD = 1000;
const MAX_INDICATORS = 32;

/** The value set on the most symbols; a tie goes to the first in JSON order, so the result is stable. */
function mostCommon<T>(values: T[]): T | null {
  const counts = new Map<string, { value: T; n: number }>();
  for (const value of values) {
    const key = JSON.stringify(value);
    counts.set(key, { value, n: (counts.get(key)?.n ?? 0) + 1 });
  }
  const ranked = [...counts.entries()].sort(([ka, a], [kb, b]) => b.n - a.n || (ka < kb ? -1 : 1));
  return ranked[0]?.[1].value ?? null;
}

type Entries = [key: string, value: string | null][];

/**
 * The charts to create from legacy per-symbol settings.
 *
 * Settings were per symbol; they are now per chart. Each chart takes the
 * setting the owner chose on the most symbols. Symbols left at the defaults
 * do not count, so a symbol that only holds drawings never outvotes a choice.
 */
export function legacyCharts(entries: Entries): Record<string, ChartSettings> {
  const charts: Record<string, ChartSettings> = {};
  const defaultSettings = { range: DEFAULT_CHART.range, mas: DEFAULT_CHART.mas, panes: DEFAULT_CHART.panes };
  const settings = mostCommon(
    entries
      .filter(([key]) => key.startsWith(LEGACY_KEY_PREFIX))
      .map(([, raw]) => {
        const p = parseLegacyPreferences(raw);
        const mas = [...new Set(p.activeMas.filter((n) => n <= MAX_PERIOD))].sort((a, b) => a - b).slice(0, MAX_MAS);
        return { range: p.timeframe, mas, panes: p.activePanes };
      })
      .filter((s) => !sameJson(s, defaultSettings)),
  );
  const overlays = mostCommon(
    entries
      .filter(([key]) => key.startsWith(LEGACY_OVERLAY_KEY_PREFIX))
      .map(([, raw]) => {
        const o = parseLegacyOverlays(raw);
        return {
          indicators: o.indicators.slice(0, MAX_INDICATORS).map(({ id, params }) => ({ id, params })),
          preset_id: o.presetId,
          show_signals: o.showSignals,
          preset_edited: o.presetEdited,
        };
      })
      .filter((o) => {
        const d = defaultOverlays();
        return !sameJson(o, { indicators: [], preset_id: d.presetId, show_signals: d.showSignals, preset_edited: d.presetEdited });
      }),
  );
  if (settings) for (const id of CHARTS_WITH_SETTINGS) charts[id] = { ...DEFAULT_CHART, ...settings };
  if (overlays) {
    for (const id of CHARTS_WITH_OVERLAYS) {
      const indicators = overlays.indicators.map((i, n) => ({ ...i, uid: `${i.id}-${n + 1}` }));
      charts[id] = { ...(charts[id] ?? DEFAULT_CHART), ...overlays, indicators };
    }
  }
  return charts;
}

/** Add the charts the workspace does not have yet. The server's charts always win. */
export function fillMissingCharts(ws: WorkspaceBody, charts: Record<string, ChartSettings>): WorkspaceBody {
  const missing = Object.entries(charts).filter(([id]) => !(id in ws.charts));
  return missing.length ? { ...ws, charts: { ...Object.fromEntries(missing), ...ws.charts } } : ws;
}

/**
 * Chart settings: one pass over every legacy key, applied through the shared
 * workspace store, so it never races the screen that is open. A marker records
 * that the pass is done; a failed load leaves no marker and retries next start.
 */
export async function importLocalPresentation(storage: Storage = localStorage): Promise<void> {
  let entries: Entries;
  try {
    if (storage.getItem(PRESENTATION_MARKER)) return;
    entries = Array.from({ length: storage.length }, (_, i) => storage.key(i))
      .filter((key): key is string => key !== null)
      .map((key) => [key, storage.getItem(key)]);
  } catch {
    return; // storage unavailable: nothing to import
  }
  const charts = legacyCharts(entries);
  if (Object.keys(charts).length > 0) {
    const store = documentStore(workspaceSpec);
    await store.whenLoaded();
    if (store.getState().status !== 'saved') return;
    store.update((ws) => fillMissingCharts(ws, charts));
  }
  storage.setItem(PRESENTATION_MARKER, new Date().toISOString());
}
