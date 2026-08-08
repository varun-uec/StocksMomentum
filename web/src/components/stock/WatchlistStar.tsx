'use client';

/** Star toggle bound to `POST/DELETE /watchlist/{symbol}` and `GET /watchlist`. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { addToWatchlist, getWatchlist, removeFromWatchlist } from '@/lib/api-client';
import { focusRing } from '@/lib/theme';

export function WatchlistStar({ symbol }: { symbol: string }) {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ['watchlist'], queryFn: getWatchlist });
  const starred = data?.symbols.includes(symbol.toUpperCase()) ?? false;

  const toggle = useMutation({
    mutationFn: () => (starred ? removeFromWatchlist(symbol) : addToWatchlist(symbol)),
    onSuccess: (response) => queryClient.setQueryData(['watchlist'], response),
  });

  return (
    <button
      type="button"
      onClick={() => toggle.mutate()}
      disabled={toggle.isPending}
      aria-pressed={starred}
      aria-label={starred ? `Remove ${symbol} from watchlist` : `Add ${symbol} to watchlist`}
      title={starred ? 'Remove from watchlist' : 'Add to watchlist'}
      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors disabled:opacity-50 ${focusRing} ${
        starred
          ? 'border-amber-300 dark:border-amber-500/40 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300'
          : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
      }`}
    >
      <svg
        viewBox="0 0 20 20"
        fill={starred ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth={1.5}
        className="w-4 h-4"
        aria-hidden
      >
        <path d="M10 2.5l2.35 4.76 5.25.76-3.8 3.7.9 5.23L10 14.5l-4.7 2.45.9-5.23-3.8-3.7 5.25-.76L10 2.5z" />
      </svg>
      {starred ? 'Watchlisted' : 'Watchlist'}
    </button>
  );
}
