'use client';

import { useEffect, useState } from 'react';
import {
  DRAWING_KINDS,
  type ChartDrawing,
  type DrawingKind,
} from '@/components/stock/chart-drawings';
import { TIMEFRAMES, type PaneId, type TimeframeId } from '@/components/stock/PriceChart';

/**
 * Phase 9.5 — per-symbol chart preferences persisted in localStorage.
 *
 * Mirrors the `theme-provider.tsx` storage pattern (`localStorage.getItem/setItem`)
 * with a key scoped per symbol. Chart display prefs are genuinely client-only, so
 * this is the right layer — no backend involvement.
 */

export interface ChartPreferences {
  timeframe: TimeframeId;
  activeMas: number[];
  activePanes: PaneId[];
  drawings: ChartDrawing[];
}

const VALID_TIMEFRAMES: readonly string[] = TIMEFRAMES.map((t) => t.id);
const VALID_PANES: readonly string[] = ['rsi', 'macd', 'adx'];

export function storageKeyFor(symbol: string): string {
  return `chart-prefs:${symbol}`;
}

/**
 * Parse an untrusted stored JSON blob into a fully-validated preferences
 * object. Anything unknown is dropped back to the defaults so a stale or
 * hand-edited payload can never crash the chart.
 */
function parseStored(raw: string | null): ChartPreferences {
  const base: ChartPreferences = {
    timeframe: '1Y',
    activeMas: [50, 200],
    activePanes: [],
    drawings: [],
  };
  if (!raw) return base;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return base;
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return base;
  const input = parsed as Record<string, unknown>;

  const timeframe = VALID_TIMEFRAMES.includes(String(input.timeframe))
    ? (input.timeframe as TimeframeId)
    : base.timeframe;

  const activeMas = Array.isArray(input.activeMas)
    ? input.activeMas.filter(
        (p): p is number => typeof p === 'number' && p >= 0 && Number.isInteger(p)
      )
    : base.activeMas;

  const activePanes = Array.isArray(input.activePanes)
    ? input.activePanes.filter((p): p is PaneId => VALID_PANES.includes(String(p)))
    : base.activePanes;

  const drawings = Array.isArray(input.drawings)
    ? input.drawings.filter(isValidDrawing)
    : base.drawings;

  return { timeframe, activeMas, activePanes, drawings };
}

function isValidDrawing(value: unknown): value is ChartDrawing {
  if (typeof value !== 'object' || value === null) return false;
  const d = value as Record<string, unknown>;
  if (typeof d.id !== 'string' || typeof d.color !== 'string') return false;
  if (!DRAWING_KINDS.includes(d.kind as DrawingKind)) return false;
  if (!Array.isArray(d.points) || d.points.length === 0) return false;
  return d.points.every(
    (p) =>
      typeof p === 'object' &&
      p !== null &&
      typeof (p as Record<string, unknown>).date === 'string' &&
      typeof (p as Record<string, unknown>).price === 'number'
  );
}

/**
 * Per-symbol chart preferences. `ready` becomes true after the stored value
 * has been read (once, on mount) so consumers can render with final values
 * instead of a defaults-then-sync flash.
 */
export function useChartPreferences(symbol: string): {
  preferences: ChartPreferences;
  ready: boolean;
  update: (patch: Partial<ChartPreferences>) => void;
} {
  const [preferences, setPreferences] = useState<ChartPreferences>(() => ({
    timeframe: '1Y',
    activeMas: [50, 200],
    activePanes: [],
    drawings: [],
  }));
  const [ready, setReady] = useState(false);

  // Read once on mount (never during render — mirrors theme-provider).
  useEffect(() => {
    if (!symbol) {
      setReady(true);
      return;
    }
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(storageKeyFor(symbol));
    } catch {
      stored = null;
    }
    setPreferences(parseStored(stored));
    setReady(true);
  }, [symbol]);

  const update = (patch: Partial<ChartPreferences>) => {
    setPreferences((prev) => {
      const next = { ...prev, ...patch };
      try {
        localStorage.setItem(storageKeyFor(symbol), JSON.stringify(next));
      } catch {
        // Storage unavailable (private mode, quota) — preferences are a
        // best-effort convenience, never a reason to break the chart.
      }
      return next;
    });
  };

  return { preferences, ready, update };
}