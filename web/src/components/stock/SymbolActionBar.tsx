'use client';

/**
 * The symbol-scoped actions, identical on every `/stock/[symbol]/*` route so a
 * reader never loses the way back to the chart, the wave count or the pattern
 * candidates (audit 2026-08-09, U11).
 */

import Link from 'next/link';
import { focusRing } from '@/lib/theme';
import { WatchlistStar } from '@/components/stock/WatchlistStar';

type ActionId = 'chart' | 'elliott-wave' | 'patterns';

export function SymbolActionBar({
  symbol,
  strategyName,
  current,
}: {
  symbol: string;
  strategyName?: string | null;
  current: ActionId;
}) {
  const query = strategyName ? `?strategy=${strategyName}` : '';
  const detail = `/stock/${symbol}${query}`;
  const actions: { id: ActionId; label: string; href: string }[] = [
    { id: 'chart', label: 'Chart', href: `${detail}#chart` },
    { id: 'elliott-wave', label: 'Elliott Wave', href: `/stock/${symbol}/elliott-wave${query}` },
    { id: 'patterns', label: 'Patterns', href: `${detail}#patterns` },
  ];

  return (
    <div className="flex items-center gap-2">
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
