/**
 * The symbol pages' header (plan 2026-10-19, workflow 4): initial badge,
 * name, `SYMBOL · NSE`, last close and change, "EOD as of", the page's
 * Momentum25 badges, and one tab row (Overview | Analysis | Elliott Wave |
 * Chart ↗) shared by every `/stock/[symbol]/*` route, so the way back to the
 * chart is never lost (audit 2026-08-09, U11).
 */

import { Link } from 'react-router';
import type { ReactNode } from 'react';
import { focusRing } from '@/lib/theme';
import { WatchlistStar } from '@/components/stock/WatchlistStar';
import { BackLink } from '@/components/shell/BackLink';
import { useShell, useShellPanel } from '@/components/shell/shell-context';
import { useSecuritySearch } from '@/components/workspace/useSecuritySearch';
import type { OHLCVBarDTO } from '@/lib/types';

type View = 'overview' | 'analysis' | 'elliott-wave';

const VIEWS: { id: View; label: string; path: string }[] = [
  { id: 'overview', label: 'Overview', path: '' },
  { id: 'analysis', label: 'Analysis', path: '/analysis' },
  { id: 'elliott-wave', label: 'Elliott Wave', path: '/elliott-wave' },
];

/** Adds query params only when they carry meaning; never a bare `?`. */
function withQuery(path: string, params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value) query.set(key, value);
  const qs = query.toString();
  return qs ? `${path}?${qs}` : path;
}

export function SymbolHeader({
  symbol,
  strategyName,
  current,
  bars,
  asOf,
  children,
}: {
  symbol: string;
  strategyName?: string | null;
  current: View;
  /** The page's daily bars: the last close and its change come from them. */
  bars?: OHLCVBarDTO[];
  /** The evaluation's data date, shown as "EOD as of". */
  asOf?: string;
  /** The page's Momentum25 badges. */
  children?: ReactNode;
}) {
  // The page is the symbol's assessment; the panel offers its alerts and watchlist.
  useShellPanel({ symbol });
  const { openPanel } = useShell();
  const name = useSecuritySearch(symbol, 1).results.find((r) => r.symbol === symbol)?.name;
  const strategy = strategyName ?? undefined;
  const last = bars?.at(-1);
  const prev = bars?.at(-2);
  const close = last ? parseFloat(last.close) : null;
  const change = last && prev ? (parseFloat(last.close) / parseFloat(prev.close) - 1) * 100 : null;
  const view = VIEWS.find((v) => v.id === current)!;
  const patterns = current === 'analysis' ? withQuery(`/stock/${symbol}/analysis`, { strategy, mode: 'patterns' }) : `${withQuery(`/stock/${symbol}`, { strategy })}#patterns`;
  const action = `px-2.5 py-1 rounded-md text-xs font-medium border border-[var(--ws-line)] text-slate-700 dark:text-slate-300 hover:bg-[var(--ws-muted)] ${focusRing}`;

  return (
    <header className="border-b border-[var(--ws-line)] bg-white dark:bg-slate-900 px-4 sm:px-6 pt-3">
      <BackLink />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span aria-hidden="true" className="w-9 h-9 rounded-full bg-[var(--ws-muted)] text-sm font-bold flex items-center justify-center">
          {symbol[0]}
        </span>
        <div className="min-w-0">
          <h1 className="text-xl font-bold tracking-tight leading-6">
            {name ?? symbol}
            <span className="sr-only"> — {symbol} · {view.label}</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            <span className="font-semibold text-slate-700 dark:text-slate-300">{symbol}</span> · NSE
          </p>
        </div>
        {close !== null && (
          <div className="flex items-baseline gap-2 tabular-nums">
            <span className="text-xl font-bold">{close.toFixed(2)}</span>
            {change !== null && (
              <span className={`text-sm font-semibold ${change >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'}`}>
                {change >= 0 ? '+' : ''}
                {change.toFixed(2)}%
              </span>
            )}
            <span className="text-[11px] text-slate-500">EOD as of {asOf ?? last?.date}</span>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">{children}</div>
        <span className="flex-1" />
        <WatchlistStar symbol={symbol} />
        <Link to={patterns} className={action}>Patterns</Link>
        <button type="button" onClick={() => openPanel('alerts')} className={action}>Create alert</button>
      </div>
      <nav aria-label="Symbol views" className="flex items-center gap-1 mt-2 -mb-px overflow-x-auto">
        {VIEWS.map((v) => (
          <Link
            key={v.id}
            to={withQuery(`/stock/${symbol}${v.path}`, { strategy })}
            aria-current={v.id === current ? 'page' : undefined}
            className={`px-3 py-2 text-sm font-medium border-b-2 whitespace-nowrap ${focusRing} ${v.id === current ? 'border-[var(--ws-accent)] text-[var(--ws-ink)]' : 'border-transparent text-slate-500 hover:text-[var(--ws-ink)]'}`}
          >
            {v.label}
          </Link>
        ))}
        <Link to={`/chart/${symbol}`} className={`px-3 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-[var(--ws-ink)] whitespace-nowrap ${focusRing}`}>
          Open in chart <span aria-hidden="true">↗</span>
        </Link>
      </nav>
    </header>
  );
}
