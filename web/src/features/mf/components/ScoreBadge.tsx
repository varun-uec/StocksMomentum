/**
 * The Wickstreet score in a small tile. The score is a category-relative
 * historical percentile (equal parts consistency, return per risk and drawdown),
 * not a suitability finding, so the label says "score", never "rating".
 */
import { cx } from './ui';

export function ScoreBadge({ score, size = 'md' }: { score: number | null | undefined; size?: 'sm' | 'md' }) {
  const has = typeof score === 'number' && Number.isFinite(score);
  const band = !has ? 'none' : score >= 80 ? 'high' : score >= 50 ? 'mid' : 'low';
  return (
    <span
      title={has ? `Score ${score.toFixed(1)} of 100, against category peers` : 'No score: a part is missing or the category has too few peers'}
      aria-label={has ? `Score ${Math.round(score)} of 100` : 'No score'}
      className={cx(
        'inline-grid shrink-0 place-items-center rounded-[9px] font-semibold tabular',
        size === 'sm' ? 'h-7 w-8 text-xs' : 'h-9 w-10 text-sm',
        band === 'high' && 'bg-mf-brand text-mf-on-brand',
        band === 'mid' && 'bg-mf-brand-soft text-mf-brand-strong',
        band === 'low' && 'bg-mf-warning-soft text-mf-warning',
        band === 'none' && 'bg-mf-sunken text-mf-muted',
      )}
    >
      {has ? Math.round(score) : '—'}
    </span>
  );
}
