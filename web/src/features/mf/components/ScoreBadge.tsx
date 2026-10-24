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

/** The score as a ring, for a fund's headline: the arc fills to the score out of 100. */
export function ScoreRing({ score, size = 76 }: { score: number | null | undefined; size?: number }) {
  const has = typeof score === 'number' && Number.isFinite(score);
  // Stroke and text scale with the ring, so a small ring keeps its number inside.
  const stroke = Math.max(4, Math.round(size * 0.09));
  const r = size / 2 - stroke / 2 - 2;
  const length = 2 * Math.PI * r;
  return (
    <span className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }} role="img" aria-label={has ? `Score ${Math.round(score)} of 100` : 'No score'}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-mf-sunken" />
        {has && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${(length * Math.max(0, Math.min(100, score))) / 100} ${length}`}
            className={cx('transition-[stroke-dasharray] duration-700', score >= 50 ? 'stroke-mf-brand' : 'stroke-mf-warning')}
          />
        )}
      </svg>
      <span className="absolute inset-0 grid place-items-center text-center leading-none" aria-hidden="true">
        <span>
          <span className="block font-semibold tabular text-mf-ink" style={{ fontSize: Math.round(size * 0.3) }}>{has ? Math.round(score) : '—'}</span>
          {size >= 60 && <span className="text-[10px] text-mf-muted">/100</span>}
        </span>
      </span>
    </span>
  );
}
