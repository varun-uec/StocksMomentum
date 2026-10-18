/**
 * Saved drawings hold traded prices: the price as printed on each point's date
 * (ADR-013 §5). The chart shows prices adjusted for corporate actions (§4).
 * These functions convert at the chart's edge with the factors the bars use,
 * so a drawing stays on its bars after a split or bonus, past or future. On
 * weekly bars each point also moves to the bar of its ISO week, so a point
 * drawn on a Wednesday still has a bar to sit on.
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

/** The Monday of a date's ISO week. */
function mondayOf(date: string): string {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
}

/** The weekly bar (dated at its last session) whose week holds `date`, else `date`. */
export function weekBarFor(date: string, weekBars: string[]): string {
  const bar = weekBars.find((d) => d >= date);
  return bar && mondayOf(bar) <= date ? bar : date;
}

/**
 * Saved (traded) prices to chart (adjusted) prices. With `weekBars` (the dates
 * of weekly bars, ascending), each point also moves to its week's bar.
 */
export function toChartPrices(drawings: ChartDrawing[], steps: AdjustmentStepDTO[], weekBars?: string[]): ChartDrawing[] {
  return drawings.map((d) => {
    const chart = scale(d, steps, (price, factor) => price * factor);
    if (!weekBars) return chart;
    return { ...chart, points: chart.points.map((p) => ({ ...p, date: weekBarFor(p.date, weekBars) })) };
  });
}

/**
 * Chart prices back to traded prices. A drawing the chart did not change keeps
 * its saved object, so float rounding never shows up as an edit in a merge.
 */
export function toTradedPrices(
  drawings: ChartDrawing[],
  saved: ChartDrawing[],
  steps: AdjustmentStepDTO[],
  weekBars?: string[],
): ChartDrawing[] {
  const before = new Map(saved.map((d) => [d.id, d]));
  return drawings.map((d) => {
    const original = before.get(d.id);
    if (original && sameJson(toChartPrices([original], steps, weekBars)[0], d)) return original;
    return scale(d, steps, (price, factor) => price / factor);
  });
}
