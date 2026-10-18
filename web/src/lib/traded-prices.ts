/**
 * Saved drawings hold traded prices: the price as printed on each point's date
 * (ADR-013 §5). The chart shows prices adjusted for corporate actions (§4).
 * These functions convert at the chart's edge with the factors the bars use,
 * so a drawing stays on its bars after a split or bonus, past or future. On
 * weekly or monthly bars each point also moves to the bar of its ISO week or
 * calendar month, so a point drawn on a Wednesday still has a bar to sit on.
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

/** Weekly or monthly bars: the interval and each bar's date (its last session), ascending. */
export interface PeriodBars {
  interval: '1W' | '1M';
  dates: string[];
}

/** The first day of a date's ISO week (Monday) or calendar month. */
function periodStart(date: string, interval: PeriodBars['interval']): string {
  if (interval === '1M') return `${date.slice(0, 8)}01`;
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
}

/** The bar whose week or month holds `date`, else `date`. */
export function periodBarFor(date: string, bars: PeriodBars): string {
  const bar = bars.dates.find((d) => d >= date);
  return bar && periodStart(bar, bars.interval) <= date ? bar : date;
}

/**
 * Saved (traded) prices to chart (adjusted) prices. With `periodBars`, each
 * point also moves to the bar of its week or month.
 */
export function toChartPrices(drawings: ChartDrawing[], steps: AdjustmentStepDTO[], periodBars?: PeriodBars): ChartDrawing[] {
  return drawings.map((d) => {
    const chart = scale(d, steps, (price, factor) => price * factor);
    if (!periodBars) return chart;
    return { ...chart, points: chart.points.map((p) => ({ ...p, date: periodBarFor(p.date, periodBars) })) };
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
  periodBars?: PeriodBars,
): ChartDrawing[] {
  const before = new Map(saved.map((d) => [d.id, d]));
  return drawings.map((d) => {
    const original = before.get(d.id);
    if (original && sameJson(toChartPrices([original], steps, periodBars)[0], d)) return original;
    return scale(d, steps, (price, factor) => price / factor);
  });
}
