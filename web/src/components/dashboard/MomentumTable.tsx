'use client';

import { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table';
import type { RankingItemDTO, RuleResults } from '@/lib/types';
import { StatusDot } from '@/components/shared/Card';
import { FloatingPanel } from '@/components/shared/FloatingPanel';
import { focusRing } from '@/lib/theme';

interface MomentumTableProps {
  items: RankingItemDTO[];
  onSymbolClick?: (symbol: string) => void;
  title?: string;
}

/** Human-readable labels for each rule in the checklist. */
const RULE_LABELS: Record<keyof RuleResults, string> = {
  price_above_long_mas: 'Price above long MAs',
  ma150_above_ma200: 'MA150 above MA200',
  ma200_trending_up: 'MA200 trending up',
  ma50_alignment: 'MA50 alignment',
  price_above_ma50: 'Price above MA50',
  above_52w_low_30pct: 'Above 52W low 30%',
  within_52w_high_25pct: 'Within 52W high 25%',
  rs_rating_gte_70: 'RS rating ≥ 70',
};

function ChecklistPopover({
  checklist,
  symbol,
}: {
  checklist: RuleResults;
  symbol: string;
}) {
  const passedCount = Object.values(checklist).filter(Boolean).length;

  return (
    <FloatingPanel
      trigger={({ ref, onClick, open }) => (
        <button
          ref={ref}
          type="button"
          onClick={onClick}
          aria-expanded={open}
          aria-label={`Checklist for ${symbol}`}
          className={`text-xs text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 underline decoration-dotted underline-offset-2 transition-colors ${focusRing}`}
        >
          {passedCount}/8
        </button>
      )}
    >
      <div className="p-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
          {symbol} — Trend Template
        </div>
        <ul className="space-y-1.5">
          {(Object.keys(RULE_LABELS) as (keyof RuleResults)[]).map((key) => {
            const passed = checklist[key];
            return (
              <li key={key} className="flex items-center gap-2 text-sm">
                <StatusDot passed={passed} />
                <span className={passed ? 'text-slate-800 dark:text-slate-200' : 'text-slate-400 dark:text-slate-500'}>
                  {RULE_LABELS[key]}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </FloatingPanel>
  );
}

function TrendTemplateBadge({ passed }: { passed: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full font-medium ${
        passed
          ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300'
          : 'bg-slate-100 dark:bg-slate-700/50 text-slate-500'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${passed ? 'bg-emerald-500 dark:bg-emerald-400' : 'bg-slate-300 dark:bg-slate-600'}`} />
      {passed ? 'Pass' : 'Fail'}
    </span>
  );
}

function RiskBadge({ bucket }: { bucket: string | null }) {
  if (!bucket) return <span className="text-slate-400 dark:text-slate-600">—</span>;
  const color =
    bucket === 'Low'
      ? 'text-emerald-600 dark:text-emerald-400'
      : bucket === 'Medium'
        ? 'text-amber-600 dark:text-amber-400'
        : 'text-rose-600 dark:text-rose-400';
  return <span className={`text-xs font-medium ${color}`}>{bucket}</span>;
}

function RankChange({ change }: { change: number | null }) {
  if (change === null || change === 0) return <span className="text-slate-400 dark:text-slate-600">—</span>;
  const isUp = change < 0; // negative delta = rank improved
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-xs font-medium tabular-nums ${
        isUp ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
      }`}
    >
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
        {isUp ? (
          <path fillRule="evenodd" clipRule="evenodd" d="M10 3a.75.75 0 01.75.75v10.638l3.096-3.096a.75.75 0 111.06 1.061l-4.5 4.5a.75.75 0 01-1.06 0l-4.5-4.5a.75.75 0 111.06-1.061l3.096 3.096V3.75A.75.75 0 0110 3z" />
        ) : (
          <path fillRule="evenodd" clipRule="evenodd" d="M10 17a.75.75 0 01-.75-.75V5.612L6.154 8.708a.75.75 0 11-1.06-1.061l4.5-4.5a.75.75 0 011.06 0l4.5 4.5a.75.75 0 01-1.06 1.061l-3.096-3.096v10.638A.75.75 0 0110 17z" />
        )}
      </svg>
      {Math.abs(change)}
    </span>
  );
}

const columnHelper = createColumnHelper<RankingItemDTO>();

export default function MomentumTable({ items, onSymbolClick, title }: MomentumTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 25 });

  const columns = useMemo(
    () => [
      columnHelper.accessor('rank', {
        header: 'Rank',
        cell: (info) => (
          <span className="font-bold text-slate-800 dark:text-slate-200 tabular-nums">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('symbol', {
        header: 'Symbol',
        cell: (info) => {
          const symbol = info.getValue();
          return (
            <button
              type="button"
              onClick={() => onSymbolClick?.(symbol)}
              className={`font-semibold text-slate-900 dark:text-white hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors ${focusRing} rounded`}
            >
              {symbol}
            </button>
          );
        },
      }),
      columnHelper.accessor('name', {
        header: 'Name',
        cell: (info) => <span className="text-slate-600 dark:text-slate-400">{info.getValue()}</span>,
      }),
      columnHelper.accessor('sector', {
        header: 'Sector',
        cell: (info) => <span className="text-xs text-slate-500 dark:text-slate-500">{info.getValue() ?? '—'}</span>,
      }),
      columnHelper.accessor('momentum_score', {
        header: 'Momentum',
        cell: (info) => (
          <span className="tabular-nums font-semibold text-slate-800 dark:text-slate-200">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('buy_setup_score', {
        header: 'Buy Setup',
        cell: (info) => <span className="tabular-nums text-slate-700 dark:text-slate-300">{info.getValue()}</span>,
      }),
      columnHelper.accessor('rs_rating', {
        header: 'RS',
        cell: (info) => {
          const val = info.getValue();
          return <span className="tabular-nums font-medium">{val ?? '—'}</span>;
        },
      }),
      columnHelper.display({
        id: 'trend_template',
        header: 'Trend',
        cell: (info) => {
          const explanation = info.row.original.explanation;
          const checklist = explanation?.checklist as unknown as RuleResults | undefined;
          if (!checklist) return <span className="text-slate-400 dark:text-slate-600">—</span>;
          const allPassed = Object.values(checklist).every(Boolean);
          return <TrendTemplateBadge passed={allPassed} />;
        },
        enableSorting: false,
      }),
      columnHelper.display({
        id: 'risk',
        header: 'Risk',
        cell: (info) => {
          const explanation = info.row.original.explanation;
          const riskBucket = (explanation?.risk_rating as string) ?? null;
          return <RiskBadge bucket={riskBucket} />;
        },
        enableSorting: false,
      }),
      columnHelper.display({
        id: 'volume',
        header: 'Volume',
        cell: (info) => {
          const explanation = info.row.original.explanation;
          const volQuality = (explanation?.volume_quality as string) ?? null;
          if (!volQuality) return <span className="text-slate-400 dark:text-slate-600">—</span>;
          const color =
            volQuality === 'High'
              ? 'text-emerald-600 dark:text-emerald-400'
              : volQuality === 'Medium'
                ? 'text-amber-600 dark:text-amber-400'
                : 'text-slate-500';
          return <span className={`text-xs font-medium ${color}`}>{volQuality}</span>;
        },
        enableSorting: false,
      }),
      columnHelper.display({
        id: 'breakout',
        header: 'Breakout',
        cell: (info) => {
          const explanation = info.row.original.explanation;
          const bq = (explanation?.breakout_quality as string) ?? null;
          if (!bq) return <span className="text-slate-400 dark:text-slate-600">—</span>;
          const color =
            bq === 'Strong'
              ? 'text-emerald-600 dark:text-emerald-400'
              : bq === 'Moderate'
                ? 'text-amber-600 dark:text-amber-400'
                : 'text-slate-500';
          return <span className={`text-xs font-medium ${color}`}>{bq}</span>;
        },
        enableSorting: false,
      }),
      columnHelper.display({
        id: 'pattern',
        header: 'Pattern',
        cell: (info) => {
          const explanation = info.row.original.explanation;
          const pattern = (explanation?.pattern as string) ?? null;
          if (!pattern) return <span className="text-slate-400 dark:text-slate-600">—</span>;
          return <span className="text-xs text-indigo-600 dark:text-indigo-300">{pattern}</span>;
        },
        enableSorting: false,
      }),
      columnHelper.display({
        id: 'rank_change',
        header: 'Δ Rank',
        cell: (info) => {
          const explanation = info.row.original.explanation;
          const change = (explanation?.rank_change as number) ?? null;
          return <RankChange change={change} />;
        },
        enableSorting: false,
      }),
      columnHelper.display({
        id: 'checklist',
        header: 'Rules',
        cell: (info) => {
          const explanation = info.row.original.explanation;
          const symbol = info.row.original.symbol;
          if (explanation?.checklist) {
            return (
              <ChecklistPopover
                checklist={explanation.checklist as unknown as RuleResults}
                symbol={symbol}
              />
            );
          }
          return <span className="text-slate-400 dark:text-slate-600 text-xs">N/A</span>;
        },
        enableSorting: false,
      }),
    ],
    [onSymbolClick],
  );

  const data = useMemo(() => items, [items]);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      globalFilter,
      pagination,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    globalFilterFn: (row, _columnId, filterValue) => {
      const symbol: string = row.getValue('symbol');
      const name: string = row.getValue('name') ?? '';
      const sector: string = row.getValue('sector') ?? '';
      const query = filterValue.toLowerCase();
      return (
        symbol.toLowerCase().includes(query) ||
        name.toLowerCase().includes(query) ||
        sector.toLowerCase().includes(query)
      );
    },
  });

  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500 text-sm">No screening results available.</div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {title && <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">{title}</h2>}
          <div className="relative">
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
              />
            </svg>
            <input
              type="text"
              placeholder="Search symbol, name, sector…"
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className={`pl-9 pr-3 py-2 w-full sm:w-72 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 text-sm ${focusRing}`}
            />
          </div>
        </div>
        <div className="text-xs text-slate-500 tabular-nums">
          {table.getFilteredRowModel().rows.length} of {items.length} results
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700/60 shadow-sm bg-white dark:bg-slate-900">
        <table className="w-full text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr
                key={headerGroup.id}
                className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60"
              >
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const isSorted = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      className={`px-3 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap ${
                        canSort
                          ? `cursor-pointer select-none hover:text-slate-800 dark:hover:text-slate-200 transition-colors ${focusRing}`
                          : ''
                      }`}
                      onClick={header.column.getToggleSortingHandler()}
                      style={{
                        textAlign:
                          header.id === 'rank' || header.id === 'symbol' || header.id === 'name' || header.id === 'sector' || header.id === 'checklist' || header.id === 'trend_template'
                            ? 'left'
                            : 'right',
                      }}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {isSorted ? (
                        <span className="ml-1.5 inline-block align-middle">
                          <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
                            {isSorted === 'asc' ? (
                              <path d="M10 3a.75.75 0 01.75.75v10.638l3.096-3.096a.75.75 0 111.06 1.061l-4.5 4.5a.75.75 0 01-1.06 0l-4.5-4.5a.75.75 0 111.06-1.061l3.096 3.096V3.75A.75.75 0 0110 3z" />
                            ) : (
                              <path d="M10 17a.75.75 0 01-.75-.75V5.612L6.154 8.708a.75.75 0 11-1.06-1.061l4.5-4.5a.75.75 0 011.06 0l4.5 4.5a.75.75 0 01-1.06 1.061l-3.096-3.096v10.638A.75.75 0 0110 17z" />
                            )}
                          </svg>
                        </span>
                      ) : null}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                {row.getVisibleCells().map((cell) => {
                  const columnId = cell.column.id;
                  const isNumeric =
                    columnId === 'momentum_score' ||
                    columnId === 'buy_setup_score' ||
                    columnId === 'rs_rating' ||
                    columnId === 'rank_change';

                  return (
                    <td
                      key={cell.id}
                      className={`px-3 py-3 ${
                        isNumeric ? 'text-right text-slate-700 dark:text-slate-300 tabular-nums' : 'text-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
        <div>
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
        </div>
        <div className="flex items-center gap-2">
          <PageButton onClick={() => table.setPageIndex(0)} disabled={!table.getCanPreviousPage()}>
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M15.79 14.77a.75.75 0 01-1.06.02l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 111.04 1.08L11.832 10l3.938 3.71a.75.75 0 01.02 1.06zM7.25 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5a.75.75 0 01.75.75z" />
            </svg>
          </PageButton>
          <PageButton onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06-.02z" />
            </svg>
          </PageButton>
          <PageButton onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06.02z" />
            </svg>
          </PageButton>
          <PageButton onClick={() => table.setPageIndex(table.getPageCount() - 1)} disabled={!table.getCanNextPage()}>
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M4.21 5.23a.75.75 0 011.06-.02l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 11-1.04-1.08L8.168 10 4.23 6.29a.75.75 0 01-.02-1.06zM12.75 10a.75.75 0 01.75-.75h1.5a.75.75 0 010 1.5h-1.5a.75.75 0 01-.75-.75z" />
            </svg>
          </PageButton>
          <select
            value={table.getState().pagination.pageSize}
            onChange={(e) => table.setPageSize(Number(e.target.value))}
            className={`ml-2 px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs ${focusRing}`}
          >
            {[10, 25, 50, 100].map((size) => (
              <option key={size} value={size}>
                {size} / page
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

function PageButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-30 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors ${focusRing}`}
    >
      {children}
    </button>
  );
}
