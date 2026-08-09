/**
 * Display-only number formatting.
 *
 * The backend serializes every quantity as a full-precision decimal string.
 * Rendering those verbatim produces values like `0.62867475968448131269894781`
 * in table cells. These helpers change presentation only — the underlying
 * strings are never mutated, re-parsed into the app state, or sent back.
 */

/** Fixed-decimal rendering, with an em dash for absent values. */
export function num(value: string | number | null | undefined, dp = 2): string {
  if (value === null || value === undefined || value === '') return '—';
  const n = typeof value === 'number' ? value : parseFloat(value);
  return Number.isFinite(n) ? n.toFixed(dp) : String(value);
}

/** "minervini_trend_template" -> "Minervini Trend Template". */
export function strategyDisplayName(name: string): string {
  return name
    .split('_')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ');
}
