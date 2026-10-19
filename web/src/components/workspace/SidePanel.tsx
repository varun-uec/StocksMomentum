/**
 * The chart workspace's right panel (M12): the watchlist, and Momentum25's
 * view of the open symbol. It reads the same queries as the watchlist and
 * stock pages, so all three always agree.
 */

import { useState } from 'react';
import { Link } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertsTab, useAlerts } from '@/components/workspace/AlertsTab';
import { ExplanationSummary } from '@/components/workspace/ExplanationSummary';
import { addToWatchlist, getLiveStockAnalysis, getWatchlistDetail, removeFromWatchlist } from '@/lib/api-client';
import { num } from '@/lib/format';
import { focusRing } from '@/lib/theme';
import type { RightPanel } from '@/lib/workspace';

const TABS: { id: NonNullable<RightPanel>; label: string }[] = [
  { id: 'watchlist', label: 'Watchlist' },
  { id: 'details', label: 'Details' },
  { id: 'alerts', label: 'Alerts' },
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
  alertPrice,
}: {
  symbol: string;
  strategy: string;
  panel: NonNullable<RightPanel>;
  onPanel: (panel: RightPanel) => void;
  onOpenSymbol: (symbol: string) => void;
  height: number;
  /** A price picked on the chart for a new alert. */
  alertPrice?: number;
}) {
  const unseen = useAlerts().data?.unseen ?? 0;
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
              tabIndex={panel === tab.id ? 0 : -1}
              id={`workspace-tab-${tab.id}`}
              aria-controls="workspace-panel-content"
              onKeyDown={(e) => {
                const index = TABS.findIndex((t) => t.id === panel);
                const next = e.key === 'ArrowRight' ? (index + 1) % TABS.length : e.key === 'ArrowLeft' ? (index + TABS.length - 1) % TABS.length : e.key === 'Home' ? 0 : e.key === 'End' ? TABS.length - 1 : -1;
                if (next >= 0) { e.preventDefault(); onPanel(TABS[next].id); document.getElementById(`workspace-tab-${TABS[next].id}`)?.focus(); }
              }}
              onClick={() => onPanel(tab.id)}
              className={`px-2 py-1 rounded-md text-xs font-medium ${focusRing} ${
                panel === tab.id ? 'bg-indigo-100 dark:bg-indigo-600/25 text-indigo-700 dark:text-indigo-300' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {tab.label}
              {tab.id === 'alerts' && unseen > 0 && (
                <span aria-label={`${unseen} new`} className="ml-1 px-1 rounded-full bg-rose-600 text-white text-[10px]">
                  {unseen}
                </span>
              )}
            </button>
          ))}
        </div>
        <button type="button" onClick={() => onPanel(null)} aria-label="Close panel" title="Close panel" className={`w-6 h-6 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}>
          ×
        </button>
      </div>
      <div id="workspace-panel-content" role="tabpanel" aria-labelledby={`workspace-tab-${panel}`} aria-label={TABS.find((t) => t.id === panel)?.label} className="flex-1 overflow-y-auto">
        {panel === 'watchlist' && <WatchlistTab symbol={symbol} strategy={strategy} onOpenSymbol={onOpenSymbol} />}
        {panel === 'details' && <DetailsTab symbol={symbol} strategy={strategy} />}
        {panel === 'alerts' && <AlertsTab symbol={symbol} price={alertPrice} />}
      </div>
    </aside>
  );
}

function WatchlistTab({ symbol, strategy, onOpenSymbol }: { symbol: string; strategy: string; onOpenSymbol: (symbol: string) => void }) {
  const { data, isLoading } = useWatchlistDetail(strategy);
  const toggle = useWatchlistToggle();
  const [sort, setSort] = useState('symbol');
  const items = [...(data?.items ?? [])].sort((a, b) => sort === 'rank' ? (a.rank ?? Infinity) - (b.rank ?? Infinity) || a.symbol.localeCompare(b.symbol) : sort === 'change' ? Number(b.change_pct ?? -Infinity) - Number(a.change_pct ?? -Infinity) : a.symbol.localeCompare(b.symbol));
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
      <label className="flex items-center justify-between px-3 py-2 text-[10px] uppercase tracking-wide text-slate-500">Sort watchlist <select aria-label="Sort watchlist" className="bg-transparent text-xs" value={sort} onChange={(e) => setSort(e.target.value)}><option value="symbol">Symbol</option><option value="change">Daily change</option><option value="rank">Momentum rank</option></select></label>
      {isLoading && <p className="px-3 py-2 text-xs text-slate-500">Loading watchlist…</p>}
      {!isLoading && items.length === 0 && <p className="px-3 py-2 text-xs text-slate-600 dark:text-slate-400">No symbols yet. Add the open symbol with Alt+W.</p>}
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
                <span className={`tabular-nums w-14 text-right ${change === null ? 'text-slate-600 dark:text-slate-400' : change >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'}`}>
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
  return (
    <div className="px-3 py-2 space-y-3 text-xs">
      <div className="border-b border-slate-200 dark:border-slate-700 pb-2"><p className="text-[10px] uppercase tracking-widest text-indigo-700 dark:text-indigo-300 mb-1">Momentum25 · {symbol}</p><p className="text-slate-500">Latest stored daily evaluation. Open the evidence to inspect every passing and failing criterion.</p></div>
      <ExplanationSummary explanation={explanation} />
      <details><summary className="cursor-pointer font-medium">All criteria & evidence</summary><div className="mt-2 space-y-2">{explanation.rule_explanations.map((rule) => <p key={rule.rule_id} className="border-l-2 pl-2 border-slate-300 dark:border-slate-600"><strong>{rule.passed ? 'Pass' : 'Fail'}</strong> · {rule.explanation}</p>)}</div></details>
      <Link to={`/stock/${encodeURIComponent(symbol)}`} className={`inline-block text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}>
        Full research →
      </Link>
    </div>
  );
}
