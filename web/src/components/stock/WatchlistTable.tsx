'use client';

/**
 * Phase 6.9 — watchlist table.
 *
 * Per row, three existing endpoints:
 *  - `GET /securities/{symbol}/ohlcv` → last two bars give close and ±%.
 *  - `GET /stocks/{symbol}/history`   → `momentum_score`, `rank`, and the
 *    prior run's rank for `rank_change`.
 *  - `GET /stocks/{symbol}`           → `rule_explanations` supply
 *    `tt_rs_rating_min.actual_value` (RS rating) and
 *    `tt_near_52w_high.actual_value` (% below the 52-week high).
 *
 * Deviation from the plan: rows do not call `/stocks/{symbol}/live`. That
 * endpoint recomputes universe-wide RS ratings (~2,000 symbols, ~6 s per
 * call), so one call per row would make the page unusable. Every figure shown
 * is still a real backend field, taken from the latest completed run.
 */

import Link from 'next/link';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getOhlcv,
  getStockExplanation,
  getStockHistory,
  getWatchlist,
  removeFromWatchlist,
} from '@/lib/api-client';
import { Card, EmptyState, LoadingSpinner } from '@/components/shared/Card';
import { DEFAULT_HORIZON } from '@/lib/horizons';
import { focusRing } from '@/lib/theme';
import type { StockExplanation, StockHistoryResponse, SecurityOHLCVDTO } from '@/lib/types';

function ruleValue(explanation: StockExplanation | undefined, ruleId: string): number | null {
  const rule = explanation?.rule_explanations.find((r) => r.rule_id === ruleId);
  if (!rule?.actual_value) return null;
  const n = parseFloat(rule.actual_value);
  return Number.isFinite(n) ? n : null;
}

function Cell({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2 whitespace-nowrap ${className}`}>{children}</td>;
}

function WatchlistRow({
  symbol,
  strategy,
  onRemove,
  removing,
}: {
  symbol: string;
  strategy: string;
  onRemove: () => void;
  removing: boolean;
}) {
  const [ohlcvQuery, historyQuery, explanationQuery] = useQueries({
    queries: [
      { queryKey: ['ohlcv-tail', symbol], queryFn: () => getOhlcv(symbol) },
      { queryKey: ['stock-history', symbol, strategy, 5], queryFn: () => getStockHistory(symbol, strategy, 5) },
      { queryKey: ['stock-explanation', symbol, strategy], queryFn: () => getStockExplanation(symbol, undefined, strategy) },
    ],
  });

  const bars = (ohlcvQuery.data as SecurityOHLCVDTO | undefined)?.bars ?? [];
  const last = bars.at(-1);
  const prev = bars.at(-2);
  const close = last ? parseFloat(last.close) : null;
  const prevClose = prev ? parseFloat(prev.close) : null;
  const changePct = close !== null && prevClose ? ((close - prevClose) / prevClose) * 100 : null;

  const points = ((historyQuery.data as StockHistoryResponse | undefined)?.score_history ?? [])
    .slice()
    .sort((a, b) => a.run_date.localeCompare(b.run_date));
  const latest = points.at(-1);
  const priorRank = points.at(-2)?.rank ?? null;
  const rankChange = latest?.rank != null && priorRank != null ? priorRank - latest.rank : null;

  const explanation = explanationQuery.data as StockExplanation | undefined;
  const rsRating = ruleValue(explanation, 'tt_rs_rating_min') ?? ruleValue(explanation, 'rs_rating');
  const belowHigh = ruleValue(explanation, 'tt_near_52w_high');

  const loading = ohlcvQuery.isLoading || historyQuery.isLoading || explanationQuery.isLoading;

  return (
    <tr className="border-t border-slate-200 dark:border-slate-800 text-xs">
      <Cell>
        <Link
          href={`/stock/${symbol}?strategy=${strategy}`}
          className={`font-semibold text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}
        >
          {symbol}
        </Link>
      </Cell>
      <Cell className="tabular-nums text-right">{close !== null ? close.toFixed(2) : loading ? '…' : '—'}</Cell>
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
      <Cell className="tabular-nums text-right">{latest?.momentum_score ?? '—'}</Cell>
      <Cell className="tabular-nums text-right">{rsRating !== null ? rsRating.toFixed(0) : '—'}</Cell>
      <Cell className="tabular-nums text-right">{latest?.rank != null ? `#${latest.rank}` : '—'}</Cell>
      <Cell
        className={`tabular-nums text-right ${
          rankChange === null
            ? 'text-slate-500'
            : rankChange > 0
              ? 'text-emerald-600 dark:text-emerald-400'
              : rankChange < 0
                ? 'text-rose-600 dark:text-rose-400'
                : 'text-slate-500'
        }`}
      >
        {rankChange === null ? '—' : rankChange === 0 ? '0' : `${rankChange > 0 ? '+' : ''}${rankChange}`}
      </Cell>
      <Cell className="tabular-nums text-right">
        {belowHigh !== null ? `${belowHigh.toFixed(2)}%` : '—'}
      </Cell>
      <Cell className="text-right">
        <button
          type="button"
          onClick={onRemove}
          disabled={removing}
          aria-label={`Remove ${symbol} from watchlist`}
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

export function WatchlistTable({ strategy = DEFAULT_HORIZON.strategyName }: { strategy?: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ['watchlist'], queryFn: getWatchlist });

  const remove = useMutation({
    mutationFn: (symbol: string) => removeFromWatchlist(symbol),
    onSuccess: (response) => queryClient.setQueryData(['watchlist'], response),
  });

  if (isLoading) return <LoadingSpinner text="Loading watchlist…" />;
  if (error) return <EmptyState message="The watchlist could not be loaded." />;

  const symbols = data?.symbols ?? [];
  if (symbols.length === 0) {
    return (
      <EmptyState message="No stocks watchlisted yet. Open any stock's research page and use the Watchlist button to track it here." />
    );
  }

  return (
    <Card
      title="Watchlist"
      subtitle={`${symbols.length} symbol(s) · scores and ranks from the latest completed run`}
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
            {symbols.map((symbol) => (
              <WatchlistRow
                key={symbol}
                symbol={symbol}
                strategy={strategy}
                onRemove={() => remove.mutate(symbol)}
                removing={remove.isPending && remove.variables === symbol}
              />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
