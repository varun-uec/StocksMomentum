/**
 * The chart workspace (M11): Find → Analyse → Draw → Restore.
 *
 * Chart first: the chart takes the free height. Everything the owner sets here
 * (range, moving averages, panes, drawings) is saved on the server as they
 * work, and comes back on reload or in another browser (ADR-013 §5).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router';
import { DEFAULT_STRATEGY, useStrategy } from '@/app/strategy-context';
import { LoadingSpinner } from '@/components/shared/Card';
import { PriceChart } from '@/components/stock/PriceChart';
import { useChartShell } from '@/components/stock/useChartShell';
import {
  MAX_PANES,
  needsBenchmark,
  useBenchmarkCloses,
  useCatalogueIndicators,
} from '@/components/stock/useCatalogueIndicators';
import { IndicatorDialog } from '@/components/workspace/IndicatorDialog';
import { SaveState } from '@/components/workspace/SaveState';
import { ShortcutsDialog } from '@/components/workspace/ShortcutsDialog';
import { SidePanel, useWatchlistDetail, useWatchlistToggle } from '@/components/workspace/SidePanel';
import { SymbolSearchDialog } from '@/components/workspace/SymbolSearchDialog';
import { useSecuritySearch } from '@/components/workspace/useSecuritySearch';
import { toBars } from '@/lib/indicators/overlays';
import { useOverlayPreferences } from '@/lib/overlay-preferences';
import { focusRing } from '@/lib/theme';
import { useRightPanel, useSymbolDrawings, useWorkspaceChart } from '@/lib/workspace';

const CHART_ID = 'main';
/** Shown on a fresh install, before the owner has opened any symbol. */
const FIRST_SYMBOL = 'RELIANCE';
/** Header, toolbar and footer around the chart, in px. */
const CHROME_HEIGHT = 300;

function useChartHeight(): number {
  const measure = () => Math.max(320, window.innerHeight - CHROME_HEIGHT);
  const [height, setHeight] = useState(measure);
  useEffect(() => {
    const onResize = () => setHeight(measure());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return height;
}

/** True when the key goes to a field or an open dialog, not to the workspace. */
function isTyping(e: KeyboardEvent): boolean {
  const target = e.target as HTMLElement | null;
  return !!target?.closest('input, textarea, select, [contenteditable="true"], dialog');
}

/** True when a key press should open symbol search instead of typing somewhere. */
function opensSearch(e: KeyboardEvent): { initial: string } | null {
  if (isTyping(e)) return null;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') return { initial: '' };
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  if (e.key === '/') return { initial: '' };
  if (/^[a-z0-9]$/i.test(e.key)) return { initial: e.key };
  return null;
}

export default function ChartPage() {
  const { symbol: routeSymbol } = useParams();
  const workspace = useWorkspaceChart(CHART_ID);

  if (!routeSymbol) {
    if (!workspace.ready) return <LoadingSpinner />;
    return <Navigate replace to={`/chart/${workspace.chart.symbol ?? FIRST_SYMBOL}`} />;
  }
  return <ChartWorkspace symbol={routeSymbol.toUpperCase()} />;
}

function ChartWorkspace({ symbol }: { symbol: string }) {
  const navigate = useNavigate();
  const height = useChartHeight();
  const shell = useChartShell(symbol, DEFAULT_STRATEGY, CHART_ID, { intervals: true });
  const workspace = useWorkspaceChart(CHART_ID);
  const drawings = useSymbolDrawings(symbol);
  const [search, setSearch] = useState<{ open: boolean; initial: string }>({ open: false, initial: '' });
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [indicatorsOpen, setIndicatorsOpen] = useState(false);
  const { strategyName } = useStrategy();
  const { overlays, update: updateOverlays } = useOverlayPreferences(CHART_ID);
  const bars = useMemo(() => toBars(shell.bars), [shell.bars]);
  const benchmark = useBenchmarkCloses(symbol, strategyName, needsBenchmark(overlays.indicators));
  const catalogue = useCatalogueIndicators(bars, overlays.indicators, shell.chartProps, benchmark);
  const { panel, setPanel } = useRightPanel();
  const watchlist = useWatchlistDetail(strategyName);
  const toggleWatchlist = useWatchlistToggle();
  const listed = watchlist.data?.items.some((i) => i.symbol === symbol) ?? false;
  // The key handler is registered once; refs give it the current values.
  const keyState = useRef({ symbol, listed, ready: !!watchlist.data, toggle: toggleWatchlist.mutate });
  keyState.current = { symbol, listed, ready: !!watchlist.data, toggle: toggleWatchlist.mutate };

  // Remember the open symbol, so `/chart` and the next visit reopen it.
  useEffect(() => {
    if (workspace.ready && workspace.chart.symbol !== symbol) workspace.update({ symbol });
  }, [workspace.ready, workspace.chart.symbol, symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.code === 'KeyW' && !isTyping(e)) {
        e.preventDefault();
        const { symbol: current, listed: inList, ready, toggle } = keyState.current;
        if (ready) toggle({ symbol: current, add: !inList });
        return;
      }
      if (e.altKey && e.code === 'KeyI' && !isTyping(e)) {
        e.preventDefault();
        setIndicatorsOpen(true);
        return;
      }
      if (e.key === '?' && !isTyping(e)) {
        e.preventDefault();
        setShortcutsOpen(true);
        return;
      }
      const open = opensSearch(e);
      if (!open) return;
      e.preventDefault();
      setSearch({ open: true, initial: open.initial });
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const name = useSecuritySearch(symbol, 1).results.find((r) => r.symbol === symbol)?.name;
  const last = shell.bars.at(-1);
  const prev = shell.bars.at(-2);
  const change = last && prev ? (parseFloat(last.close) / parseFloat(prev.close) - 1) * 100 : null;

  return (
    <main className="max-w-screen-2xl mx-auto px-2 sm:px-4 py-3">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-2">
        <h1 className="text-lg font-bold tracking-tight">
          <button
            type="button"
            onClick={() => setSearch({ open: true, initial: '' })}
            title="Change symbol (type, /, or Ctrl/⌘+K)"
            className="hover:text-indigo-600 dark:hover:text-indigo-400"
          >
            {symbol}
          </button>
        </h1>
        {name && <span className="text-sm text-slate-500 dark:text-slate-400">{name}</span>}
        {last && <span className="text-sm font-semibold tabular-nums">{parseFloat(last.close).toFixed(2)}</span>}
        {change !== null && (
          <span className={`text-sm tabular-nums ${change >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
            {change >= 0 ? '+' : ''}
            {change.toFixed(2)}%
          </span>
        )}
        <span className="flex-1" />
        <SaveState documents={[workspace, drawings]} />
        <button
          type="button"
          onClick={() => setIndicatorsOpen(true)}
          title="Indicators (Alt+I)"
          className={`px-2 py-0.5 rounded-md text-xs text-slate-500 border border-slate-200 dark:border-slate-700 ${focusRing}`}
        >
          Indicators{overlays.indicators.length > 0 ? ` · ${overlays.indicators.length}` : ''}
        </button>
        <button
          type="button"
          onClick={() => setShortcutsOpen(true)}
          aria-label="Keyboard shortcuts"
          title="Keyboard shortcuts (?)"
          className={`w-6 h-6 rounded-md text-xs text-slate-500 border border-slate-200 dark:border-slate-700 ${focusRing}`}
        >
          ?
        </button>
        <button
          type="button"
          onClick={() => setPanel(panel ? null : 'watchlist')}
          aria-pressed={panel !== null}
          className={`hidden lg:inline-block px-2 py-0.5 rounded-md text-xs border border-slate-200 dark:border-slate-700 ${focusRing} ${
            panel ? 'text-indigo-700 dark:text-indigo-300' : 'text-slate-500'
          }`}
        >
          Panel
        </button>
      </header>

      <div className="flex gap-3">
        <div className="flex-1 min-w-0">
          {shell.ready ? (
            <PriceChart
              {...shell.chartProps}
              {...catalogue.paneProps}
              overlayLines={catalogue.lines}
              onOpenIndicators={() => setIndicatorsOpen(true)}
              height={height}
              toolRail
            />
          ) : <LoadingSpinner />}
        </div>
        {panel && (
          <div className="hidden lg:block w-72 shrink-0">
            <SidePanel
              symbol={symbol}
              strategy={strategyName}
              panel={panel}
              onPanel={setPanel}
              onOpenSymbol={(next) => navigate(`/chart/${encodeURIComponent(next)}`)}
              height={height + 120}
            />
          </div>
        )}
      </div>
      <ShortcutsDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <IndicatorDialog
        open={indicatorsOpen}
        onClose={() => setIndicatorsOpen(false)}
        active={overlays.indicators}
        onChange={(indicators) => updateOverlays({ indicators, presetEdited: true })}
        legend={catalogue.legend}
        paneCount={catalogue.paneCount}
        maxPanes={MAX_PANES}
      />

      <SymbolSearchDialog
        open={search.open}
        initialText={search.initial}
        onChoose={(next) => navigate(`/chart/${encodeURIComponent(next)}`)}
        onClose={() => setSearch((s) => ({ ...s, open: false }))}
      />
    </main>
  );
}
