/**
 * Chart-series helpers: window cuts and rebasing for display. Rebasing scales a
 * NAV series so its first point equals a starting amount; it is a change of
 * units on the chart, not a new return measure.
 */
import type { NavRow, Point } from './api';

export const WINDOWS = { '1Y': 1, '3Y': 3, '5Y': 5, '10Y': 10, Max: 99 } as const;
export type WindowKey = keyof typeof WINDOWS;

/** Points on or after the same calendar date `years` before the last point. */
export function sinceYears<T extends [string, number]>(points: T[], years: number): T[] {
  if (!points.length || years >= 99) return points;
  const last = points[points.length - 1][0];
  const cutoff = `${Number(last.slice(0, 4)) - years}${last.slice(4)}`;
  return points.filter(([d]) => d >= cutoff);
}

/** Valid NAVs as points; a row flagged as an anomaly is left out, never bridged. */
export function navPoints(rows: NavRow[]): Point[] {
  return rows.filter((r) => !r.anomaly && Number(r.nav) > 0).map((r) => [r.date, Number(r.nav)]);
}

/** Scale a series so it starts at `base`; points before `start` are dropped. */
export function rebase(points: Point[], base: number, start?: string): Point[] {
  const from = start ? points.filter(([d]) => d >= start) : points;
  if (!from.length) return [];
  const first = from[0][1];
  return from.map(([d, v]) => [d, (v / first) * base]);
}

/** How many years a window can show: the longest window the series covers. */
export function availableWindows(points: Point[]): WindowKey[] {
  if (points.length < 2) return ['Max'];
  const years = (Date.parse(points[points.length - 1][0]) - Date.parse(points[0][0])) / (365.25 * 864e5);
  return (Object.keys(WINDOWS) as WindowKey[]).filter((k) => WINDOWS[k] === 99 || WINDOWS[k] <= years + 0.02);
}
