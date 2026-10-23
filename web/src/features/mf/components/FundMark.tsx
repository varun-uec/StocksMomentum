/**
 * A fund-house monogram (audit U-06): two letters from the AMC name on a tint
 * picked by a stable hash, so a fund house keeps its colour on every screen. It
 * is a marker, not a logo: Wickstreet holds no AMC brand assets.
 */
import type { ColorTokens } from '../theme/themes';
import { token } from '../theme/themes';
import { cx } from './ui';

const FILLER = new Set(['asset', 'management', 'mutual', 'fund', 'funds', 'company', 'co', 'pvt', 'private', 'ltd', 'limited', 'india', 'investment', 'managers', 'amc', 'the', 'of', '&', 'and']);
const TINTS: (keyof ColorTokens)[] = ['chart1', 'chart2', 'chart3', 'chart4', 'chart5'];

/** `PPFAS Asset Management Pvt. Ltd.` → `PP`; `Aditya Birla Sun Life AMC` → `AB`. */
export function initials(amc: string | null | undefined): string {
  const words = (amc ?? '').replace(/[^A-Za-z& ]/g, ' ').split(/\s+/).filter((w) => w && !FILLER.has(w.toLowerCase()));
  if (!words.length) return '··';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function tint(amc: string): keyof ColorTokens {
  let h = 0;
  for (const c of amc) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

export function FundMark({ amc, size = 'md', className }: { amc: string | null | undefined; size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const role = tint(amc ?? '');
  return (
    <span
      aria-hidden="true"
      className={cx(
        'inline-grid shrink-0 place-items-center font-semibold tracking-tight text-mf-ink',
        size === 'sm' ? 'h-7 w-7 rounded-[8px] text-[10px]' : size === 'lg' ? 'h-14 w-14 rounded-[16px] text-base' : 'h-9 w-9 rounded-[10px] text-xs',
        className,
      )}
      style={{ background: token(role, 0.22), boxShadow: `inset 0 0 0 1px ${token(role, 0.35)}` }}
    >
      {initials(amc)}
    </span>
  );
}
