/**
 * Axis ticks for MF charts. A tick label always equals its gridline's true value
 * (audit F-02), and time ticks fall on month or year starts (F-15). Charts plot
 * dates as UTC milliseconds, so a band or marker resolves at any date, not only
 * at a date the thinned data happens to keep (F-01).
 */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** `2026-10-22` → UTC milliseconds. */
export const toTime = (iso: string) => Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)) || 1);

/** Round gridlines that cover [lo, hi]: steps of 1, 2 or 5 × 10ⁿ, about `count` of them. */
export function niceTicks(lo: number, hi: number, count = 5): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [];
  if (lo === hi) {
    const pad = Math.abs(lo) * 0.1 || 1;
    lo -= pad;
    hi += pad;
  }
  if (lo > hi) [lo, hi] = [hi, lo];
  const rough = (hi - lo) / Math.max(1, count - 1);
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= rough * 0.999) ?? 10 * power;
  const first = Math.floor(lo / step + 1e-9) * step;
  const ticks: number[] = [];
  for (let v = first; v < hi + step - 1e-9 * step; v += step) ticks.push(Number(v.toPrecision(12)));
  return ticks;
}

/** A percentage tick with as many decimals as it needs, so 2.5% never reads as 3%. */
export function pctTick(value: number): string {
  const p = value * 100;
  const digits = [0, 1, 2].find((d) => Math.abs(Number(p.toFixed(d)) - p) < 1e-9) ?? 2;
  const text = `${Math.abs(p).toFixed(digits)}%`;
  return p < 0 && Number(text.slice(0, -1)) !== 0 ? `−${text}` : text;
}

const MONTH_STEPS = [1, 2, 3, 6, 12, 24, 36, 60, 120];

/** Gridlines on month or year starts between two times; about `count` of them. */
export function timeTicks(from: number, to: number, count = 6): { ticks: number[]; years: boolean } {
  if (!(to > from)) return { ticks: [], years: false };
  const months = (to - from) / (30.44 * 864e5);
  const step = MONTH_STEPS.find((s) => months / s <= count) ?? 120;
  // Months since year 0 of the first month start on or after `from`, aligned to the
  // step: yearly ticks fall in January, quarterly ones in Jan, Apr, Jul and Oct.
  const start = new Date(from);
  const first = start.getUTCFullYear() * 12 + start.getUTCMonth() + (start.getUTCDate() > 1 ? 1 : 0);
  const ticks: number[] = [];
  for (let index = Math.ceil(first / step) * step; ; index += step) {
    const t = Date.UTC(Math.floor(index / 12), index % 12, 1);
    if (t > to) break;
    ticks.push(t);
  }
  return { ticks, years: step >= 12 };
}

/** A time tick in words: `2021` for yearly ticks, `Mar 24` for monthly ones. */
export function timeLabel(time: number, years: boolean): string {
  const d = new Date(time);
  return years ? String(d.getUTCFullYear()) : `${MONTHS[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}`;
}

/** Log-scale gridlines on 1, 2 and 5 × 10ⁿ inside [lo, hi]; both ends must be positive. */
export function logTicks(lo: number, hi: number): number[] {
  if (!(lo > 0) || !(hi > lo)) return [];
  const ticks: number[] = [];
  for (let p = Math.floor(Math.log10(lo)); p <= Math.ceil(Math.log10(hi)); p++)
    for (const m of [1, 2, 5]) {
      const t = m * 10 ** p;
      if (t >= lo && t <= hi) ticks.push(Number(t.toPrecision(12)));
    }
  return ticks;
}
