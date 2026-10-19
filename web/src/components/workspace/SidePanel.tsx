/**
 * The workstation's right panel (M12, moved into the shell 2026-10-19): the
 * watchlist, Momentum25's view of the context symbol, and alerts. It reads
 * the same queries as the watchlist and stock pages, so all three agree.
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertsTab, useAlerts } from '@/components/workspace/AlertsTab';
import { AssessmentPanel } from '@/components/momentum25/AssessmentPanel';
import type { EvidenceControl } from '@/components/momentum25/evidence';
import { addToWatchlist, getWatchlistDetail, removeFromWatchlist } from '@/lib/api-client';
import { StatusDot } from '@/components/shared/Card';
import { num } from '@/lib/format';
import { focusRing } from '@/lib/theme';
import type { RightPanel } from '@/lib/workspace';

export type PanelTab = NonNullable<RightPanel>;

const icon = (path: React.ReactNode) => (
  <svg viewBox="0 0 20 20" className="w-[18px] h-[18px]" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    {path}
  </svg>
);

/** The panel tabs. The `details` id is the Assessment; its saved value predates the name. */
export const PANEL_TABS: { id: PanelTab; label: string; icon: React.ReactNode }[] = [
  { id: 'watchlist', label: 'Watchlist', icon: icon(<path d="M4 5h12M4 10h12M4 15h8" />) },
  { id: 'details', label: 'Assessment', icon: icon(<><circle cx="10" cy="10" r="7" /><path d="M10 9v5M10 6.5v.01" /></>) },
  { id: 'alerts', label: 'Alerts', icon: icon(<><circle cx="10" cy="11" r="6" /><path d="M10 8v3l2 1.5M4 4l2-1.5M16 4l-2-1.5" /></>) },
  { id: 'objects', label: 'Object tree', icon: icon(<><path d="M5 4v12M5 7h4M5 12h4" /><rect x="10" y="5" width="6" height="4" rx="1" /><rect x="10" y="10" width="6" height="4" rx="1" /></>) },
];

/**
 * The panel tabs: a vertical icon strip on desktop, a row in the sheet on
 * narrow screens. Arrows, Home and End move between tabs.
 */
export function PanelTabs({
  tabs,
  selected,
  onSelect,
  vertical,
}: {
  tabs: typeof PANEL_TABS;
  selected: PanelTab | null;
  onSelect: (tab: PanelTab) => void;
  vertical: boolean;
}) {
  const unseen = useAlerts().data?.unseen ?? 0;
  const [prev, next] = vertical ? ['ArrowUp', 'ArrowDown'] : ['ArrowLeft', 'ArrowRight'];
  const focusIndex = Math.max(0, tabs.findIndex((t) => t.id === selected));
  return (
    <div role="tablist" aria-label="Panel" aria-orientation={vertical ? 'vertical' : 'horizontal'} className={vertical ? 'ws-strip' : 'flex gap-1 flex-1'}>
      {tabs.map((tab, i) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={selected === tab.id}
          aria-label={tab.label}
          title={tab.label}
          tabIndex={i === focusIndex ? 0 : -1}
          id={`workspace-tab-${tab.id}`}
          aria-controls="workspace-panel-content"
          onKeyDown={(e) => {
            const to = e.key === next ? (i + 1) % tabs.length : e.key === prev ? (i + tabs.length - 1) % tabs.length : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : -1;
            if (to >= 0) {
              e.preventDefault();
              onSelect(tabs[to].id);
              document.getElementById(`workspace-tab-${tabs[to].id}`)?.focus();
            }
          }}
          onClick={() => onSelect(tab.id)}
          className={`relative ${vertical ? 'ws-strip-tab' : 'px-2 py-1 rounded-md text-xs font-medium'} ${focusRing} ${
            selected === tab.id ? 'bg-indigo-100 dark:bg-indigo-600/25 text-indigo-700 dark:text-indigo-300' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          {vertical ? tab.icon : tab.label}
          {tab.id === 'alerts' && unseen > 0 && (
            <span aria-label={`${unseen} new`} className={`${vertical ? 'absolute top-0.5 right-0.5' : 'ml-1'} px-1 rounded-full bg-rose-600 text-white text-[10px] leading-4`}>
              {unseen}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

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

/** The open panel: a header with its tabs (narrow) or its title, and the tab's content. */
export function SidePanel({
  panel,
  symbol,
  strategy,
  onOpenSymbol,
  onClose,
  tabs,
  alertPrice,
  objectsRef,
  runId,
  evidence,
  onOpenChart,
  onCreateAlert,
}: {
  panel: PanelTab;
  /** The route's context symbol, if it has one. */
  symbol?: string;
  strategy: string;
  onOpenSymbol: (symbol: string) => void;
  onClose: () => void;
  /** Tabs shown in the header when there is no icon strip (narrow screens). */
  tabs?: React.ReactNode;
  /** A price picked on the chart for a new alert. */
  alertPrice?: number;
  /** Receives the Object tree's body, which the active chart fills. */
  objectsRef?: (el: HTMLElement | null) => void;
  /** The route's run in view, for the Assessment; the latest run when absent. */
  runId?: number;
  /** "Show on chart" for the active chart (/chart only). */
  evidence?: EvidenceControl;
  /** Assessment's "Open in chart"; absent on /chart. */
  onOpenChart?: (symbol: string) => void;
  onCreateAlert?: () => void;
}) {
  const label = PANEL_TABS.find((t) => t.id === panel)?.label;
  return (
    <aside aria-label="Side panel" className="flex flex-col h-full min-h-0 border-l border-[var(--ws-line)] bg-white dark:bg-slate-900">
      <div className="flex items-center gap-1 px-2 h-9 shrink-0 border-b border-[var(--ws-line)]">
        {tabs ?? <h2 className="flex-1 text-xs font-semibold">{label}</h2>}
        <button type="button" onClick={onClose} aria-label="Close panel" title="Close panel" className={`w-6 h-6 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}>
          ×
        </button>
      </div>
      <div id="workspace-panel-content" role="tabpanel" aria-labelledby={`workspace-tab-${panel}`} aria-label={label} className="flex-1 min-h-0 overflow-y-auto">
        {panel === 'watchlist' && <WatchlistTab symbol={symbol} strategy={strategy} runId={runId} onOpenSymbol={onOpenSymbol} />}
        {panel === 'details' && symbol && (
          <AssessmentPanel key={`${symbol}:${strategy}:${runId}`} symbol={symbol} strategy={strategy} runId={runId} evidence={evidence} onOpenChart={onOpenChart && (() => onOpenChart(symbol))} onCreateAlert={onCreateAlert} />
        )}
        {panel === 'alerts' && <AlertsTab symbol={symbol} price={alertPrice} />}
        {panel === 'objects' && <div ref={objectsRef} className="p-2" />}
      </div>
    </aside>
  );
}

/** Dense rows: Symbol, Last, Chg%, Rank, Qualified. Ranks come from the strategy's latest run, which the header names. */
function WatchlistTab({ symbol, strategy, runId, onOpenSymbol }: { symbol?: string; strategy: string; runId?: number; onOpenSymbol: (symbol: string) => void }) {
  const { data, isLoading } = useWatchlistDetail(strategy);
  const toggle = useWatchlistToggle();
  const [sort, setSort] = useState('symbol');
  const items = [...(data?.items ?? [])].sort((a, b) => sort === 'rank' ? (a.rank ?? Infinity) - (b.rank ?? Infinity) || a.symbol.localeCompare(b.symbol) : sort === 'change' ? Number(b.change_pct ?? -Infinity) - Number(a.change_pct ?? -Infinity) : a.symbol.localeCompare(b.symbol));
  const listed = items.some((i) => i.symbol === symbol);

  return (
    <div>
      {symbol && (
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
      )}
      <label className="flex items-center justify-between px-3 py-2 text-[10px] uppercase tracking-wide text-slate-500">Sort watchlist <select aria-label="Sort watchlist" className="bg-transparent text-xs" value={sort} onChange={(e) => setSort(e.target.value)}><option value="symbol">Symbol</option><option value="change">Daily change</option><option value="rank">Momentum rank</option></select></label>
      {isLoading && <p className="px-3 py-2 text-xs text-slate-500">Loading watchlist…</p>}
      {!isLoading && items.length === 0 && <p className="px-3 py-2 text-xs text-slate-600 dark:text-slate-400">No symbols yet. Add the open symbol with Alt+W.</p>}
      {data && (
        <p data-testid="watchlist-run" className={`px-3 pb-1 text-[11px] ${runId !== undefined && data.run_id !== runId ? 'text-amber-700 dark:text-amber-400' : 'text-slate-500'}`}>
          {data.run_id === null ? `${strategy} · no completed run` : runId !== undefined && data.run_id !== runId ? `Watchlist ranks: run #${data.run_id} (latest), not this view's run #${runId}` : `Ranks: ${strategy} · run #${data.run_id}`}
        </p>
      )}
      {items.length > 0 && (
        <div aria-hidden="true" className="flex gap-2 px-3 py-1 text-[10px] uppercase tracking-wide text-slate-500 border-b border-[var(--ws-line)]">
          <span className="flex-1">Symbol</span>
          <span className="w-16 text-right">Last</span>
          <span className="w-14 text-right">Chg%</span>
          <span className="w-9 text-right">Rank</span>
          <span className="w-7 text-right">Q</span>
        </div>
      )}
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
                <span className="tabular-nums w-16 text-right">{item.close === null ? '—' : num(item.close)}</span>
                <span className={`tabular-nums w-14 text-right ${change === null ? 'text-slate-600 dark:text-slate-400' : change >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'}`}>
                  {change === null ? '—' : `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`}
                </span>
                <span className="tabular-nums w-9 text-right text-slate-500">{item.rank === null ? '—' : `#${item.rank}`}</span>
                <span className="w-7 text-right">
                  {item.in_latest_run ? <StatusDot passed={item.rank !== null} /> : <span aria-hidden="true">—</span>}
                  <span className="sr-only">{!item.in_latest_run ? 'not in the run' : item.rank !== null ? 'qualified' : 'not qualified'}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
