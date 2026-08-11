'use client';

/**
 * The symbol-scoped actions, identical on every `/stock/[symbol]/*` route so a
 * reader never loses the way back to the chart, the analysis screen, the wave
 * count or the pattern candidates (audit 2026-08-09, U11).
 *
 * Targets are route-aware. On the detail and wave pages, Chart and Patterns
 * jump to that page's own sections. On the analysis page, which has its own
 * Chart, Patterns and Elliott Wave modes, those actions switch modes instead
 * of navigating away to another page.
 */

import Link from 'next/link';
import { focusRing } from '@/lib/theme';
import { WatchlistStar } from '@/components/stock/WatchlistStar';

type ActionId = 'chart' | 'analysis' | 'patterns' | 'elliott-wave';

/** Adds query params only when they carry meaning; never a bare `?`. */
function withQuery(path: string, params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const qs = query.toString();
  return qs ? `${path}?${qs}` : path;
}

export function SymbolActionBar({
  symbol,
  strategyName,
  current,
}: {
  symbol: string;
  strategyName?: string | null;
  current: ActionId;
}) {
  // Identical link shapes on all three routes; the analysis route swaps its
  // Chart / Patterns / Elliott Wave actions for in-page mode switches.
  const onAnalysis = current === 'analysis';
  const analysis = withQuery(`/stock/${symbol}/analysis`, {
    strategy: strategyName ?? undefined,
  });
  const withMode = (mode: string) =>
    withQuery(`/stock/${symbol}/analysis`, {
      strategy: strategyName ?? undefined,
      mode,
    });
  const detail = withQuery(`/stock/${symbol}`, { strategy: strategyName ?? undefined });
  const wave = withQuery(`/stock/${symbol}/elliott-wave`, {
    strategy: strategyName ?? undefined,
  });

  const actions: { id: ActionId; label: string; href: string }[] = [
    { id: 'chart', label: 'Chart', href: onAnalysis ? withMode('chart') : `${detail}#chart` },
    { id: 'analysis', label: 'Analysis', href: analysis },
    { id: 'elliott-wave', label: 'Elliott Wave', href: onAnalysis ? withMode('elliott') : wave },
    { id: 'patterns', label: 'Patterns', href: onAnalysis ? withMode('patterns') : `${detail}#patterns` },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2">
      <WatchlistStar symbol={symbol} />
      {actions.map((action) =>
        action.id === current ? (
          <span
            key={action.id}
            aria-current="page"
            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-indigo-300 dark:border-indigo-700 text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-600/10"
          >
            {action.label}
          </span>
        ) : (
          <Link
            key={action.id}
            href={action.href}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
          >
            {action.label}
          </Link>
        )
      )}
    </div>
  );
}
