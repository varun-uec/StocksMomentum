/**
 * Catalogue indicators and the signal preset for the unified analysis screen.
 * Display only (NFR-1a): nothing here feeds a score, gate or rank.
 */

import { useMemo } from 'react';
import { INDICATOR_BY_ID, defaultParams, type Params } from '@/lib/indicators/catalogue';
import { PRESET_BY_ID, DEFAULT_PRESET_ID } from '@/lib/strategies';
import { useWorkspaceChart, type ChartSettings } from '@/lib/workspace';

/** One configured instance of a catalogue indicator. */
export interface ActiveIndicator {
  /** Unique per instance, so a second SMA with another period can coexist. */
  uid: string;
  id: string;
  params: Params;
  color?: string | null;
  hidden?: boolean;
}

export interface OverlayPreferences {
  indicators: ActiveIndicator[];
  presetId: string;
  /** False when the preset's rules are evaluated but not marked on the chart. */
  showSignals: boolean;
  /** True once the user edits away from the preset's own configuration. */
  presetEdited: boolean;
}

export function newUid(id: string): string {
  return `${id}-${Math.random().toString(36).slice(2, 8)}`;
}

export function defaultOverlays(): OverlayPreferences {
  return { indicators: [], presetId: DEFAULT_PRESET_ID, showSignals: true, presetEdited: false };
}

function validIndicator(value: unknown): ActiveIndicator | null {
  if (typeof value !== 'object' || value === null) return null;
  const v = value as Record<string, unknown>;
  if (typeof v.id !== 'string') return null;
  const def = INDICATOR_BY_ID.get(v.id);
  if (!def) return null;
  const stored = typeof v.params === 'object' && v.params !== null ? (v.params as Params) : {};
  const params = defaultParams(def);
  for (const param of def.params) {
    const raw = stored[param.key];
    if (param.type === 'number' && typeof raw === 'number' && Number.isFinite(raw)) params[param.key] = raw;
    if (param.type !== 'number' && typeof raw === 'string') params[param.key] = raw;
  }
  return { uid: typeof v.uid === 'string' ? v.uid : newUid(v.id), id: v.id, params, color: typeof v.color === 'string' ? v.color : null, hidden: v.hidden === true };
}

export const LEGACY_OVERLAY_KEY_PREFIX = 'chart-overlays:';

/**
 * Parse the per-symbol blob that Phase 9.5 kept under `chart-overlays:<symbol>`,
 * once, for the import in `local-import.ts`. Anything unknown falls back to the
 * defaults.
 */
export function parseLegacyOverlays(raw: string | null): OverlayPreferences {
  const base = defaultOverlays();
  if (!raw) return base;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return base;
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return base;
  const input = parsed as Record<string, unknown>;
  return {
    indicators: Array.isArray(input.indicators)
      ? input.indicators.map(validIndicator).filter((x): x is ActiveIndicator => x !== null)
      : base.indicators,
    presetId: typeof input.presetId === 'string' && PRESET_BY_ID.has(input.presetId) ? input.presetId : base.presetId,
    showSignals: typeof input.showSignals === 'boolean' ? input.showSignals : base.showSignals,
    presetEdited: typeof input.presetEdited === 'boolean' ? input.presetEdited : base.presetEdited,
  };
}

/**
 * One chart's catalogue indicators and signal preset, stored in the server
 * workspace (ADR-013 §5). An indicator id the catalogue no longer defines is
 * dropped, not crashed on.
 */
export function useOverlayPreferences(chartId: string): {
  overlays: OverlayPreferences;
  ready: boolean;
  update: (patch: Partial<OverlayPreferences>) => void;
} {
  const { chart, ready, update: updateChart } = useWorkspaceChart(chartId);

  const overlays = useMemo<OverlayPreferences>(() => {
    const base = defaultOverlays();
    return {
      indicators: chart.indicators.map(validIndicator).filter((x): x is ActiveIndicator => x !== null),
      presetId: chart.preset_id && PRESET_BY_ID.has(chart.preset_id) ? chart.preset_id : base.presetId,
      showSignals: chart.show_signals,
      presetEdited: chart.preset_edited,
    };
  }, [chart]);

  const update = (patch: Partial<OverlayPreferences>) => {
    const settings: Partial<ChartSettings> = {};
    if (patch.indicators) settings.indicators = patch.indicators.map((i) => ({ ...i, hidden: i.hidden ?? false }));
    if (patch.presetId !== undefined) settings.preset_id = patch.presetId;
    if (patch.showSignals !== undefined) settings.show_signals = patch.showSignals;
    if (patch.presetEdited !== undefined) settings.preset_edited = patch.presetEdited;
    updateChart(settings);
  };

  return { overlays, ready, update };
}
