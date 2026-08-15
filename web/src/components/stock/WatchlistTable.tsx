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
 *
 * Sorting and filtering are client-side over the rows already fetched, using
 * the same TanStack Table setup as the dashboard.
 */

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import { getWatchlistDetail, removeFromWatchlist } from '@/lib/api-client';
import { Card, EmptyState, ErrorMessage } from '@/components/shared/Card';
import { FloatingPanel } from '@/components/shared/FloatingPanel';
import { SkeletonRegion, SkeletonTable } from '@/components/shared/Skeleton';
import { DEFAULT_STRATEGY } from '@/app/strategy-context';
import { focusRing } from '@/lib/theme';
import { num } from '@/lib/format';
import type { WatchlistItemDTO } from '@/lib/types';

const LEFT_ALIGNED = new Set(['symbol']);

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

function RemoveAction({
  symbol,
  onRemove,
  removing,
}: {
  symbol: string;
  onRemove: () => void;
  removing: boolean;
}) {
  const button = (className: string) => (
    <button
      type="button"
      onClick={onRemove}
      disabled={removing}
      aria-label={`Remove ${symbol} from watchlist`}
      className={className}
    >
      Remove
    </button>
  );

  return (
    <>
      <span className="hidden sm:inline">
        {button(
          `px-2 py-1 rounded-md text-slate-500 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 ${focusRing}`
        )}
      </span>
      {/* On a narrow screen a ninth always-visible column costs more than it
          is worth, so the action moves behind a trailing menu. */}
      <span className="sm:hidden">
        <FloatingPanel
          panelClassName="w-40"
          trigger={({ ref, onClick, open }) => (
            <button
              ref={ref}
              type="button"
              onClick={onClick}
              aria-expanded={open}
              aria-haspopup="menu"
              aria-label={`Actions for ${symbol}`}
              className={`px-2 py-1 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
            >
              ⋯
            </button>
          )}
        >
          <div className="p-1">
            {button(
              `w-full text-left px-3 py-2 rounded-md text-sm text-rose-600 dark:text-rose-400 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 ${focusRing}`
            )}
          </div>
        </FloatingPanel>
      </span>
    </>
  );
}

const columnHelper = createColumnHelper<WatchlistItemDTO>();

export function WatchlistTable({ strategy = DEFAULT_STRATEGY }: { strategy?: string }) {
  const queryClient = useQueryClient();
  const [sorting, setSorting] = useState<SortingState>([{ id: 'rank', desc: false }]);
  const [filter, setFilter] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['watchlist-detail', strategy],
    queryFn: () => getWatchlistDetail(strategy),
    refetchInterval: 60_000,
    // Switching strategy keeps the current rows on screen instead of
    // collapsing the table to a skeleton.
    placeholderData: keepPreviousData,
  });

  const remove = useMutation({
    mutationFn: (symbol: string) => removeFromWatchlist(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist-detail'] });
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    },
  });

  const columns = useMemo(
    () => [
      columnHelper.accessor('symbol', {
        header: 'Symbol',
        cell: (info) => {
          const item = info.row.original;
          return (
            <>
              <Link
                href={`/stock/${item.symbol}?strategy=${strategy}`}
                className={`font-semibold text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}
              >
                {item.symbol}
              </Link>
              {!item.in_latest_run && (
                <span
                  className="ml-1.5 text-[10px] text-slate-400 dark:text-slate-500"
                  title="Evaluated live — not part of the latest screening run"
                >
                  live
                </span>
              )}
            </>
          );
        },
      }),
      columnHelper.accessor((row) => toNumber(row.close), {
        id: 'close',
        header: 'Close',
        cell: (info) => num(info.row.original.close),
      }),
      columnHelper.accessor((row) => toNumber(row.change_pct), {
        id: 'change_pct',
        header: 'Change',
        cell: (info) => {
          const changePct = info.getValue();
          return (
            <span
              className={
                changePct === null
                  ? 'text-slate-500 dark:text-slate-400'
                  : changePct >= 0
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-rose-600 dark:text-rose-400'
              }
            >
              {changePct !== null ? `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%` : '—'}
            </span>
          );
        },
        sortUndefined: 'last',
      }),
      columnHelper.accessor((row) => toNumber(row.momentum_score), {
        id: 'momentum_score',
        header: 'Momentum',
        cell: (info) => num(info.row.original.momentum_score, 1),
      }),
      columnHelper.accessor('rs_rating', {
        header: 'RS rating',
        cell: (info) => info.getValue() ?? '—',
        sortUndefined: 'last',
      }),
      columnHelper.accessor('rank', {
        header: 'Rank',
        cell: (info) => {
          const item = info.row.original;
          // "—" alone cannot say whether the stock was evaluated and failed the
          // gates or was never in the run at all (audit U6).
          if (item.rank != null) return `#${item.rank}`;
          return item.in_latest_run ? (
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
          );
        },
        sortUndefined: 'last',
      }),
      columnHelper.accessor('rank_change', {
        id: 'rank_change',
        header: 'Rank Δ',
        cell: (info) => {
          const item = info.row.original;
          const rankChange = item.rank_change;
          const tone =
            rankChange === null || rankChange === undefined
              ? 'text-slate-500 dark:text-slate-400'
              : rankChange > 0
                ? 'text-emerald-600 dark:text-emerald-400'
                : rankChange < 0
                  ? 'text-rose-600 dark:text-rose-400'
                  : 'text-slate-500 dark:text-slate-400';
          return (
            <span className={tone}>
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
            </span>
          );
        },
        sortUndefined: 'last',
      }),
      columnHelper.accessor((row) => toNumber(row.pct_below_high_52w), {
        id: 'pct_below_high_52w',
        header: 'Below 52w high',
        cell: (info) =>
          info.row.original.pct_below_high_52w !== null
            ? `${num(info.row.original.pct_below_high_52w)}%`
            : '—',
        sortUndefined: 'last',
      }),
      columnHelper.display({
        id: 'actions',
        header: '',
        cell: (info) => (
          <RemoveAction
            symbol={info.row.original.symbol}
            onRemove={() => remove.mutate(info.row.original.symbol)}
            removing={remove.isPending && remove.variables === info.row.original.symbol}
          />
        ),
      }),
    ],
    [strategy, remove]
  );

  const items = useMemo(() => data?.items ?? [], [data]);

  const table = useReactTable({
    data: items,
    columns,
    state: { sorting, globalFilter: filter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    globalFilterFn: (row, _columnId, filterValue) =>
      row.original.symbol.toLowerCase().includes(String(filterValue).toLowerCase()),
  });

  if (isLoading) {
    return (
      <SkeletonRegion label="Loading watchlist">
        <SkeletonTable rows={6} columns={9} />
      </SkeletonRegion>
    );
  }
  if (error) {
    return (
      <ErrorMessage
        message="The watchlist could not be loaded."
        onRetry={() => queryClient.invalidateQueries({ queryKey: ['watchlist-detail', strategy] })}
      />
    );
  }
  if (items.length === 0) {
    return (
      <EmptyState message="No stocks watchlisted yet. Open any stock's research page and use the Watchlist button to track it here." />
    );
  }

  const visible = table.getRowModel().rows.length;

  return (
    <Card
      title="Watchlist"
      subtitle={`${items.length} symbol(s) · scores from the latest run, live-evaluated where outside it`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
        <div>
          <label htmlFor="watchlist-filter" className="sr-only">
            Filter watchlist by symbol
          </label>
          <input
            id="watchlist-filter"
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by symbol…"
            className={`px-3 py-1.5 w-full sm:w-56 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 text-sm ${focusRing}`}
          />
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 tabular-nums">
          Showing {visible} of {items.length}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const isSorted = header.column.getIsSorted();
                  const toggleSort = header.column.getToggleSortingHandler();
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      aria-sort={
                        !canSort
                          ? undefined
                          : isSorted === 'asc'
                            ? 'ascending'
                            : isSorted === 'desc'
                              ? 'descending'
                              : 'none'
                      }
                      tabIndex={canSort ? 0 : undefined}
                      onClick={toggleSort}
                      onKeyDown={
                        canSort
                          ? (event) => {
                              if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                toggleSort?.(event);
                              }
                            }
                          : undefined
                      }
                      className={`px-3 py-2 font-semibold whitespace-nowrap ${
                        LEFT_ALIGNED.has(header.id) ? 'text-left' : 'text-right'
                      } ${
                        canSort
                          ? `cursor-pointer select-none hover:text-slate-800 dark:hover:text-slate-200 transition-colors ${focusRing}`
                          : ''
                      }`}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {isSorted && <span className="ml-1">{isSorted === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-t border-slate-200 dark:border-slate-800 text-xs">
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={`px-3 py-2 whitespace-nowrap ${
                      LEFT_ALIGNED.has(cell.column.id) ? '' : 'text-right tabular-nums'
                    }`}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {visible === 0 && <EmptyState message={`No watchlisted symbol matches “${filter}”.`} />}
    </Card>
  );
}
