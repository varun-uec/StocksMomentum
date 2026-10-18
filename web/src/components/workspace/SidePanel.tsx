/**
 * The chart workspace's right panel (M12): the watchlist, and Momentum25's
 * view of the open symbol. It reads the same queries as the watchlist and
 * stock pages, so all three always agree.
 */

import { Link } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, StatusDot } from '@/components/shared/Card';
import { investmentReadiness } from '@/components/stock/readiness';
import { rankReasons } from '@/components/stock/WhyItRanks';
import { addToWatchlist, getLiveStockAnalysis, getWatchlistDetail, removeFromWatchlist } from '@/lib/api-client';
import { num } from '@/lib/format';
import { focusRing } from '@/lib/theme';
import type { RightPanel } from '@/lib/workspace';

const TABS: { id: NonNullable<RightPanel>; label: string }[] = [
  { id: 'watchlist', label: 'Watchlist' },
  { id: 'details', label: 'Details' },
];

/** Add or remove a symbol; both lists refresh. */
export function useWatchlistToggle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, add }: { symbol: string; add: boolean }) => (add ? addToWatchlist(symbol) : removeFromWatchlist(symbol)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist-detail'] });
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    },
  });
}

export function useWatchlistDetail(strategy: string) {
  return useQuery({ queryKey: ['watchlist-detail', strategy], queryFn: () => getWatchlistDetail(strategy) });
}

export function SidePanel({
  symbol,
  strategy,
  panel,
  onPanel,
  onOpenSymbol,
  height,
}: {
  symbol: string;
  strategy: string;
  panel: NonNullable<RightPanel>;
  onPanel: (panel: RightPanel) => void;
  onOpenSymbol: (symbol: string) => void;
  height: number;
}) {
  return (
    <aside aria-label="Side panel" style={{ height }} className="flex flex-col rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-slate-200 dark:border-slate-800">
        <div role="tablist" aria-label="Panel" className="flex gap-1 flex-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={panel === tab.id}
              onClick={() => onPanel(tab.id)}
              className={`px-2 py-1 rounded-md text-xs font-medium ${focusRing} ${
                panel === tab.id ? 'bg-indigo-100 dark:bg-indigo-600/25 text-indigo-700 dark:text-indigo-300' : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <button type="button" onClick={() => onPanel(null)} aria-label="Close panel" title="Close panel" className={`w-6 h-6 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}>
          ×
        </button>
      </div>
      <div role="tabpanel" aria-label={panel === 'watchlist' ? 'Watchlist' : 'Details'} className="flex-1 overflow-y-auto">
        {panel === 'watchlist' ? (
          <WatchlistTab symbol={symbol} strategy={strategy} onOpenSymbol={onOpenSymbol} />
        ) : (
          <DetailsTab symbol={symbol} strategy={strategy} />
        )}
      </div>
    </aside>
  );
}

function WatchlistTab({ symbol, strategy, onOpenSymbol }: { symbol: string; strategy: string; onOpenSymbol: (symbol: string) => void }) {
  const { data, isLoading } = useWatchlistDetail(strategy);
  const toggle = useWatchlistToggle();
  const items = data?.items ?? [];
  const listed = items.some((i) => i.symbol === symbol);

  return (
    <div>
      <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800">
        <button
          type="button"
          disabled={toggle.isPending || isLoading}
          onClick={() => toggle.mutate({ symbol, add: !listed })}
          title="Alt+W"
          className={`text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline disabled:opacity-50 ${focusRing}`}
        >
          {listed ? `Remove ${symbol}` : `Add ${symbol}`}
        </button>
      </div>
      {isLoading && <p className="px-3 py-2 text-xs text-slate-500">Loading watchlist…</p>}
      {!isLoading && items.length === 0 && <p className="px-3 py-2 text-xs text-slate-500">No symbols yet. Add the open symbol with Alt+W.</p>}
      <ul>
        {items.map((item) => {
          const change = item.change_pct === null ? null : parseFloat(item.change_pct);
          return (
            <li key={item.symbol}>
              <button
                type="button"
                onClick={() => onOpenSymbol(item.symbol)}
                aria-current={item.symbol === symbol ? 'true' : undefined}
                className={`w-full flex items-baseline gap-2 px-3 py-1.5 text-left text-xs hover:bg-slate-50 dark:hover:bg-slate-800/60 ${focusRing} ${
                  item.symbol === symbol ? 'bg-indigo-50 dark:bg-indigo-600/15' : ''
                }`}
              >
                <span className="flex-1 font-semibold truncate">{item.symbol}</span>
                {item.rank !== null && <span className="text-slate-400 tabular-nums">#{item.rank}</span>}
                <span className="tabular-nums w-16 text-right">{item.close === null ? '—' : num(item.close)}</span>
                <span className={`tabular-nums w-14 text-right ${change === null ? 'text-slate-400' : change >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {change === null ? '—' : `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function DetailsTab({ symbol, strategy }: { symbol: string; strategy: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['stock-live', symbol, strategy],
    queryFn: () => getLiveStockAnalysis(symbol, false, strategy),
  });
  if (isLoading) return <p className="px-3 py-2 text-xs text-slate-500">Evaluating {symbol}…</p>;
  const explanation = data?.explanation;
  if (error || !explanation) {
    return <p className="px-3 py-2 text-xs text-slate-500">No Momentum25 evaluation for {symbol}: not enough stored history.</p>;
  }
  const readiness = investmentReadiness(explanation);
  const { contributors, detractors } = rankReasons(explanation, 3);

  return (
    <div className="px-3 py-2 space-y-3 text-xs">
      <div className="space-y-1">
        <Badge color={readiness.color}>{readiness.label}</Badge>
        <dl className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-slate-600 dark:text-slate-300">
          <dt>Momentum score</dt>
          <dd className="text-right tabular-nums">{num(explanation.momentum_score)}</dd>
          <dt>Setup score</dt>
          <dd className="text-right tabular-nums">{num(explanation.buy_setup_score)}</dd>
          <dt>Gate failures</dt>
          <dd className="text-right tabular-nums">{explanation.hard_filter_failures.length}</dd>
        </dl>
      </div>
      <section aria-label="Why it ranks">
        <h3 className="font-semibold mb-1">Why it ranks</h3>
        {contributors.length === 0 && <p className="text-slate-500">No passing rules.</p>}
        {contributors.map((r) => (
          <p key={r.rule_id} className="flex gap-1.5 text-slate-700 dark:text-slate-300">
            <StatusDot passed /> <span>{r.explanation}</span>
          </p>
        ))}
      </section>
      <section aria-label="What could invalidate this">
        <h3 className="font-semibold mb-1">What could invalidate this</h3>
        {detractors.length === 0 && <p className="text-slate-500">No failing rules.</p>}
        {detractors.map((r) => (
          <p key={r.rule_id} className="flex gap-1.5 text-slate-700 dark:text-slate-300">
            <StatusDot passed={false} /> <span className="flex-1">{r.explanation}</span>
            {explanation.hard_filter_failures.includes(r.rule_id) && <Badge color="rose">gate</Badge>}
          </p>
        ))}
      </section>
      <Link to={`/stock/${encodeURIComponent(symbol)}`} className={`inline-block text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}>
        Full research →
      </Link>
    </div>
  );
}
