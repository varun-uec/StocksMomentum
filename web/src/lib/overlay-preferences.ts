'use client';

/**
 * Per-symbol indicator preferences for the unified analysis screen.
 *
 * Deliberately separate from `chart-preferences.ts` (`chart-prefs:${symbol}`):
 * two shipped screens depend on that validated shape, and widening it to carry
 * a catalogue that changes would risk them. Same pattern though — read once in
 * an effect, expose a `ready` flag, validate everything on the way in. An
 * indicator id the catalogue no longer defines is dropped, not crashed on.
 */

import { useEffect, useState } from 'react';
import { INDICATOR_BY_ID, defaultParams, type Params } from '@/lib/indicators/catalogue';
import { PRESET_BY_ID, DEFAULT_PRESET_ID } from '@/lib/strategies';

/** One configured instance of a catalogue indicator. */
export interface ActiveIndicator {
  /** Unique per instance, so a second SMA with another period can coexist. */
  uid: string;
  id: string;
  params: Params;
}

export interface OverlayPreferences {
  indicators: ActiveIndicator[];
  presetId: string;
  /** False when the preset's rules are evaluated but not marked on the chart. */
  showSignals: boolean;
  /** True once the user edits away from the preset's own configuration. */
  presetEdited: boolean;
}

export function overlayStorageKeyFor(symbol: string): string {
  return `chart-overlays:${symbol}`;
}

export function newUid(id: string): string {
  return `${id}-${Math.random().toString(36).slice(2, 8)}`;
}

function defaults(): OverlayPreferences {
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
  return { uid: typeof v.uid === 'string' ? v.uid : newUid(v.id), id: v.id, params };
}

function parseStored(raw: string | null): OverlayPreferences {
  const base = defaults();
  if (!raw) return base;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return base;
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return base;
  const input = parsed as Record<string, unknown>;

  const indicators = Array.isArray(input.indicators)
    ? input.indicators
        .map(validIndicator)
        .filter((x): x is ActiveIndicator => x !== null)
    : base.indicators;

  const presetId =
    typeof input.presetId === 'string' && PRESET_BY_ID.has(input.presetId)
      ? input.presetId
      : base.presetId;

  return {
    indicators,
    presetId,
    showSignals: typeof input.showSignals === 'boolean' ? input.showSignals : base.showSignals,
    presetEdited: typeof input.presetEdited === 'boolean' ? input.presetEdited : base.presetEdited,
  };
}

export function useOverlayPreferences(symbol: string): {
  overlays: OverlayPreferences;
  ready: boolean;
  update: (patch: Partial<OverlayPreferences>) => void;
} {
  const [overlays, setOverlays] = useState<OverlayPreferences>(defaults);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!symbol) {
      setReady(true);
      return;
    }
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(overlayStorageKeyFor(symbol));
    } catch {
      stored = null;
    }
    setOverlays(parseStored(stored));
    setReady(true);
  }, [symbol]);

  const update = (patch: Partial<OverlayPreferences>) => {
    setOverlays((prev) => {
      const next = { ...prev, ...patch };
      try {
        localStorage.setItem(overlayStorageKeyFor(symbol), JSON.stringify(next));
      } catch {
        // Storage unavailable (private mode, quota). Preferences are a
        // convenience, never a reason to break the chart.
      }
      return next;
    });
  };

  return { overlays, ready, update };
}
