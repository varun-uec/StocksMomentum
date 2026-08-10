'use client';

/**
 * Pattern detection state, extracted unchanged from `PatternCard` so the
 * detail page and the unified analysis screen run the same detection with the
 * same geometry colours.
 *
 * Detection is a mutation, never a query: it runs only when the reader clicks.
 */

import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { detectChartPatterns } from '@/lib/api-client';
import type { ChartPatternAnalysis, DetectedPattern } from '@/lib/types';
import type { ChartOverlayLine } from '@/components/stock/PriceChart';

/** One formation the backend reports, with its criteria and geometry. */
export type PatternCandidate = DetectedPattern;

export const GEOMETRY_COLORS = ['#a855f7', '#0ea5e9', '#f59e0b', '#10b981'];

export function useChartPatterns(symbol: string, lookbackDays: number) {
  const [selected, setSelected] = useState(0);
  const detection = useMutation<ChartPatternAnalysis>({
    // The endpoint accepts 60–2000 sessions; short chart timeframes are widened
    // to the shortest history a formation can occupy rather than rejected.
    mutationFn: () => detectChartPatterns(symbol, Math.min(2000, Math.max(60, lookbackDays)), 5),
    onSuccess: () => setSelected(0),
  });

  const analysis = detection.data;
  const shown = analysis?.patterns[selected];

  const overlayLines = useMemo<ChartOverlayLine[]>(
    () =>
      (shown?.geometry ?? []).map((line, i) => ({
        color: GEOMETRY_COLORS[i % GEOMETRY_COLORS.length],
        points: line.points.map((p) => ({ date: p.bar_date, price: parseFloat(p.price) })),
      })),
    [shown]
  );

  return { detection, analysis, shown, selected, setSelected, overlayLines };
}
