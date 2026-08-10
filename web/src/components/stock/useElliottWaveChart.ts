'use client';

/**
 * Elliott Wave chart state, extracted unchanged from the Elliott Wave page so
 * the unified analysis screen can render the same annotation without a second
 * implementation. Everything shown still comes from
 * `GET /stocks/{symbol}/elliott-wave`; nothing is computed or inferred here.
 */

import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineStyle } from 'lightweight-charts';
import { getElliottWave } from '@/lib/api-client';
import { lookbackDaysFor } from '@/components/stock/useChartShell';
import type { ChartMarker, ChartOverlayLine, TimeframeId } from '@/components/stock/PriceChart';
import type {
  ElliottSubdivision,
  ElliottWaveCount,
  ElliottWaveLabel,
} from '@/lib/types';

export const MAX_LOOKBACK_DAYS = 2000;

/** One colour per ranked candidate, so a count keeps its identity everywhere. */
export const CANDIDATE_COLORS = ['#a855f7', '#0ea5e9', '#f59e0b'];
/** Lower-opacity variants, so the degree below the selected one reads as finer. */
export const CANDIDATE_FAINT = [
  'rgba(168, 85, 247, 0.45)',
  'rgba(14, 165, 233, 0.45)',
  'rgba(245, 158, 11, 0.45)',
];

/** A level of the degree hierarchy: the count itself, or a nested subdivision. */
export interface DegreeNode {
  degree: string;
  pattern: string;
  variant: string | null;
  labels: ElliottWaveLabel[];
  subdivisions: ElliottSubdivision[];
}

function rootNode(count: ElliottWaveCount): DegreeNode {
  return {
    degree: count.degree,
    pattern: count.pattern,
    variant: count.variant,
    labels: count.labels,
    subdivisions: count.subdivisions,
  };
}

function subNode(subdivision: ElliottSubdivision): DegreeNode {
  return {
    degree: subdivision.degree,
    pattern: subdivision.pattern,
    variant: subdivision.variant,
    labels: subdivision.labels,
    subdivisions: subdivision.subdivisions,
  };
}

/** Walk `path` (subdivision indices) down from the count, collecting each level. */
export function nodesAlong(count: ElliottWaveCount, path: number[]): DegreeNode[] {
  const nodes = [rootNode(count)];
  let subdivisions = count.subdivisions;
  for (const index of path) {
    const child = subdivisions[index];
    if (!child) break;
    nodes.push(subNode(child));
    subdivisions = child.subdivisions;
  }
  return nodes;
}

export function describe(node: DegreeNode): string {
  return node.variant ? `${node.variant} ${node.pattern}` : node.pattern;
}

export function useElliottWaveChart(
  symbol: string,
  timeframe: TimeframeId,
  strategyName: string
) {
  const [thresholdPct, setThresholdPct] = useState(5);
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [degreePath, setDegreePath] = useState<number[]>([]);
  const [selectedWave, setSelectedWave] = useState<number | null>(null);

  const {
    data: analysis,
    isLoading: waveLoading,
    error: waveError,
  } = useQuery({
    queryKey: ['elliott-wave', symbol, timeframe, thresholdPct, strategyName],
    queryFn: () =>
      getElliottWave(
        symbol,
        lookbackDaysFor(timeframe, MAX_LOOKBACK_DAYS),
        thresholdPct,
        strategyName
      ),
    enabled: !!symbol,
  });

  const candidates = useMemo(() => analysis?.candidates ?? [], [analysis]);
  const count = candidates[candidateIndex] ?? candidates[0] ?? null;
  const colorIndex = Math.min(candidateIndex, CANDIDATE_COLORS.length - 1);
  const color = CANDIDATE_COLORS[colorIndex];
  const faint = CANDIDATE_FAINT[colorIndex];

  const path = useMemo(() => (count ? nodesAlong(count, degreePath) : []), [count, degreePath]);
  const active = path[path.length - 1] ?? null;

  const selectCount = useCallback((index: number) => {
    setCandidateIndex(index);
    setDegreePath([]);
    setSelectedWave(null);
  }, []);

  const markers = useMemo<ChartMarker[]>(() => {
    if (!active || !count) return [];
    const own: ChartMarker[] = active.labels
      .filter((l) => l.label !== '0')
      .map((l) => ({
        date: l.bar_date,
        text: l.label,
        position: count.direction === 'up' ? 'aboveBar' : 'belowBar',
        color,
      }));
    const finer: ChartMarker[] = active.subdivisions.flatMap((subdivision) =>
      subdivision.labels
        .filter((l) => l.label !== '0')
        .map((l) => ({
          date: l.bar_date,
          text: `(${l.label})`,
          position: count.direction === 'up' ? 'aboveBar' : ('belowBar' as const),
          color: faint,
          size: 0.7,
        }))
    );
    return [...own, ...finer];
  }, [active, count, color, faint]);

  const overlayLine = useMemo(
    () =>
      (active?.labels ?? []).map((l) => ({
        date: l.bar_date,
        price: parseFloat(l.price),
        color,
      })),
    [active, color]
  );

  const overlayLines = useMemo<ChartOverlayLine[]>(
    () =>
      (active?.subdivisions ?? []).map((subdivision) => ({
        points: subdivision.labels.map((l) => ({
          date: l.bar_date,
          price: parseFloat(l.price),
        })),
        color: faint,
        lineWidth: 1 as const,
        lineStyle: LineStyle.Dashed,
      })),
    [active, faint]
  );

  const priceZone = useMemo(
    () =>
      count?.projection && degreePath.length === 0
        ? {
            low: parseFloat(count.projection.low),
            high: parseFloat(count.projection.high),
            title: 'Projected zone',
            color,
          }
        : null,
    [count, degreePath, color]
  );

  // Selecting a wave scrolls the chart to that leg; clearing it restores the
  // full loaded range.
  const visibleRange = useMemo(() => {
    if (!active || selectedWave === null || selectedWave < 1) return null;
    return {
      from: active.labels[selectedWave - 1].bar_date,
      to: active.labels[selectedWave].bar_date,
    };
  }, [active, selectedWave]);

  return {
    analysis,
    waveLoading,
    waveError,
    candidates,
    count,
    color,
    faint,
    path,
    active,
    thresholdPct,
    setThresholdPct,
    candidateIndex,
    selectCount,
    degreePath,
    setDegreePath,
    selectedWave,
    setSelectedWave,
    markers,
    overlayLine,
    overlayLines,
    priceZone,
    visibleRange,
  };
}
