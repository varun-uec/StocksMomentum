'use client';

/**
 * Phase 6.9 — watchlist table.
 *
 * A single `GET /watchlist/detail?strategy=` call returns every column for
 * every row. Symbols in the strategy's latest completed run come from
 * persisted results; symbols outside it are evaluated live, server-side, in
 * that same request (see `GetWatchlistDetail`) -- the client never fans out
 * per-row calls, which was ruled out for latency (each `/live` call
 * recomputes universe-wide RS ratings, ~2,000 symbols).
 */

import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getWatchlistDetail, removeFromWatchlist } from '@/lib/api-client';
import { Card, EmptyState, LoadingSpinner } from '@/components/shared/Card';
import { DEFAULT_STRATEGY } from '@/app/strategy-context';
import { focusRing } from '@/lib/theme';
import { num } from '@/lib/format';
import type { WatchlistItemDTO } from '@/lib/types';

function Cell({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2 whitespace-nowrap ${className}`}>{children}</td>;
}

function WatchlistRow({
  item,
  strategy,
  onRemove,
  removing,
}: {
  item: WatchlistItemDTO;
  strategy: string;
  onRemove: () => void;
  removing: boolean;
}) {
  const changePct = item.change_pct !== null ? parseFloat(item.change_pct) : null;
  const rankChange = item.rank_change;

  return (
    <tr className="border-t border-slate-200 dark:border-slate-800 text-xs">
      <Cell>
        <Link
          href={`/stock/${item.symbol}?strategy=${strategy}`}
          className={`font-semibold text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}
        >
          {item.symbol}
        </Link>
        {!item.in_latest_run && (
          <span className="ml-1.5 text-[10px] text-slate-400 dark:text-slate-500" title="Evaluated live — not part of the latest screening run">
            live
          </span>
        )}
      </Cell>
      <Cell className="tabular-nums text-right">{num(item.close)}</Cell>
      <Cell
        className={`tabular-nums text-right ${
          changePct === null
            ? 'text-slate-500'
            : changePct >= 0
              ? 'text-emerald-600 dark:text-emerald-400'
              : 'text-rose-600 dark:text-rose-400'
        }`}
      >
        {changePct !== null ? `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%` : '—'}
      </Cell>
      <Cell className="tabular-nums text-right">{num(item.momentum_score, 1)}</Cell>
      <Cell className="tabular-nums text-right">{item.rs_rating ?? '—'}</Cell>
      <Cell className="tabular-nums text-right">
        {/* "—" alone cannot say whether the stock was evaluated and failed the
            gates or was never in the run at all (audit U6). */}
        {item.rank != null ? (
          `#${item.rank}`
        ) : item.in_latest_run ? (
          <span
            className="text-[10px] font-medium text-amber-600 dark:text-amber-400"
            title="Evaluated in the latest run but did not pass every gate, so it is unranked."
          >
            not qualified
          </span>
        ) : (
          <span className="text-slate-400 dark:text-slate-600" title="Not part of the latest screening run.">
            —
          </span>
        )}
      </Cell>
      <Cell
        className={`tabular-nums text-right ${
          rankChange === null || rankChange === undefined
            ? 'text-slate-500'
            : rankChange > 0
              ? 'text-emerald-600 dark:text-emerald-400'
              : rankChange < 0
                ? 'text-rose-600 dark:text-rose-400'
                : 'text-slate-500'
        }`}
      >
        {item.rank == null ? (
          <span className="text-slate-400 dark:text-slate-600">—</span>
        ) : rankChange == null ? (
          <span className="text-[10px] font-medium" title="No rank in the previous run to compare against.">
            new
          </span>
        ) : rankChange === 0 ? (
          '0'
        ) : (
          `${rankChange > 0 ? '+' : ''}${rankChange}`
        )}
      </Cell>
      <Cell className="tabular-nums text-right">
        {item.pct_below_high_52w !== null ? `${num(item.pct_below_high_52w)}%` : '—'}
      </Cell>
      <Cell className="text-right">
        <button
          type="button"
          onClick={onRemove}
          disabled={removing}
          aria-label={`Remove ${item.symbol} from watchlist`}
          className={`px-2 py-1 rounded-md text-slate-500 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 ${focusRing}`}
        >
          Remove
        </button>
      </Cell>
    </tr>
  );
}

const COLUMNS = [
  { label: 'Symbol', align: 'text-left' },
  { label: 'Close', align: 'text-right' },
  { label: 'Change', align: 'text-right' },
  { label: 'Momentum', align: 'text-right' },
  { label: 'RS rating', align: 'text-right' },
  { label: 'Rank', align: 'text-right' },
  { label: 'Rank Δ', align: 'text-right' },
  { label: 'Below 52w high', align: 'text-right' },
  { label: '', align: 'text-right' },
];

export function WatchlistTable({ strategy = DEFAULT_STRATEGY }: { strategy?: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ['watchlist-detail', strategy],
    queryFn: () => getWatchlistDetail(strategy),
  });

  const remove = useMutation({
    mutationFn: (symbol: string) => removeFromWatchlist(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist-detail'] });
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    },
  });

  if (isLoading) return <LoadingSpinner text="Loading watchlist…" />;
  if (error) return <EmptyState message="The watchlist could not be loaded." />;

  const items = data?.items ?? [];
  if (items.length === 0) {
    return (
      <EmptyState message="No stocks watchlisted yet. Open any stock's research page and use the Watchlist button to track it here." />
    );
  }

  return (
    <Card
      title="Watchlist"
      subtitle={`${items.length} symbol(s) · scores from the latest run, live-evaluated where outside it`}
    >
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">
              {COLUMNS.map((c, i) => (
                <th key={c.label || i} className={`px-3 py-2 font-semibold ${c.align}`}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <WatchlistRow
                key={item.symbol}
                item={item}
                strategy={strategy}
                onRemove={() => remove.mutate(item.symbol)}
                removing={remove.isPending && remove.variables === item.symbol}
              />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
