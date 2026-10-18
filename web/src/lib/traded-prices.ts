/**
 * Saved drawings hold traded prices: the price as printed on each point's date
 * (ADR-013 §5). The chart shows prices adjusted for corporate actions (§4).
 * These functions convert at the chart's edge with the factors the bars use,
 * so a drawing stays on its bars after a split or bonus, past or future.
 */

import type { ChartDrawing } from '@/components/stock/chart-drawings';
import { sameJson } from '@/lib/merge';
import type { AdjustmentStepDTO } from '@/lib/types';

/** A date's factor: the first step that runs to or past it, else the latest one. */
export function factorAt(steps: AdjustmentStepDTO[], date: string): number {
  const step = steps.find((s) => date <= s.until) ?? steps.at(-1);
  return step ? parseFloat(step.factor) : 1;
}

function scale(drawing: ChartDrawing, steps: AdjustmentStepDTO[], by: (price: number, factor: number) => number): ChartDrawing {
  return { ...drawing, points: drawing.points.map((p) => ({ ...p, price: by(p.price, factorAt(steps, p.date)) })) };
}

/** Saved (traded) prices to chart (adjusted) prices. */
export function toChartPrices(drawings: ChartDrawing[], steps: AdjustmentStepDTO[]): ChartDrawing[] {
  return drawings.map((d) => scale(d, steps, (price, factor) => price * factor));
}

/**
 * Chart prices back to traded prices. A drawing the chart did not change keeps
 * its saved object, so float rounding never shows up as an edit in a merge.
 */
export function toTradedPrices(drawings: ChartDrawing[], saved: ChartDrawing[], steps: AdjustmentStepDTO[]): ChartDrawing[] {
  const before = new Map(saved.map((d) => [d.id, d]));
  return drawings.map((d) => {
    const original = before.get(d.id);
    if (original && sameJson(toChartPrices([original], steps)[0], d)) return original;
    return scale(d, steps, (price, factor) => price / factor);
  });
}
