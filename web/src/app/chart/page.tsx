/**
 * The chart workspace (M11): Find → Analyse → Draw → Restore.
 *
 * Chart first: the chart takes the free height. Everything the owner sets here
 * (range, moving averages, panes, drawings) is saved on the server as they
 * work, and comes back on reload or in another browser (ADR-013 §5).
 *
 * M13 adds layouts of up to 4 × 4 charts. The route's symbol is the active
 * chart's. Grid cells are compact charts; a click makes one active, and the
 * header, the dialogs and the keys act on it.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Link, Navigate, useNavigate, useParams } from 'react-router';
import { useStrategy } from '@/app/strategy-context';
import { LoadingSpinner } from '@/components/shared/Card';
import { PriceChart } from '@/components/stock/PriceChart';
import { MAX_PANES } from '@/components/stock/useCatalogueIndicators';
import { IndicatorDialog } from '@/components/workspace/IndicatorDialog';
import { SaveState } from '@/components/workspace/SaveState';
import { ShortcutsDialog } from '@/components/workspace/ShortcutsDialog';
import { SidePanel, useWatchlistDetail, useWatchlistToggle } from '@/components/workspace/SidePanel';
import { SymbolSearchDialog } from '@/components/workspace/SymbolSearchDialog';
import { MAX_COMPARE, type CompareLine } from '@/components/workspace/useCompare';
import { useChartSlot } from '@/components/workspace/useChartSlot';
import { useSecuritySearch } from '@/components/workspace/useSecuritySearch';
import { createCrosshairSync, type CrosshairSync } from '@/lib/crosshair-sync';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { focusRing } from '@/lib/theme';
import type { ChartInterval } from '@/lib/types';
import { LAYOUTS, useLayout, useRightPanel, useSymbolDrawings, useWorkspaceChart, type Layout } from '@/lib/workspace';

/** Shown on a fresh install, before the owner has opened any symbol. */
const FIRST_SYMBOL = 'RELIANCE';
/** Header, toolbar and footer around the chart, in px. */
const CHROME_HEIGHT = 224;
/** A grid cell's own header and range row, in px. */
const CELL_CHROME = 36;
const GRID_GAP = 3;
/** The single chart's toolbar rows and footnote, which a grid does not have, in px. */
const GRID_EXTRA = 26;

function useChartHeight(): number {
  const measure = () => Math.max(180, window.innerHeight - CHROME_HEIGHT - (window.innerWidth < 1024 ? 76 : 0));
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
  // A checkbox or radio takes no text, so the workspace keys still apply after a click on one.
  const field = target?.closest(
    'input:not([type="checkbox"]):not([type="radio"]), textarea, select, [contenteditable="true"]',
  );
  const fieldDialog = field?.closest('dialog');
  if (fieldDialog && !fieldDialog.open) return false;
  return !!field || !!target?.closest('dialog[open]');
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
  const grid = useLayout();
  const active = useWorkspaceChart(grid.active);

  if (!routeSymbol) {
    if (!grid.ready) return <LoadingSpinner />;
    return <Navigate replace to={`/chart/${active.chart.symbol ?? FIRST_SYMBOL}`} />;
  }
  return <ChartWorkspace symbol={routeSymbol.toUpperCase()} />;
}

const btn = `px-2 py-0.5 rounded-md text-xs text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 disabled:opacity-40 ${focusRing}`;

function CompareChips({ symbol, compare, onRemove }: { symbol: string; compare: CompareLine[]; onRemove: (symbol: string) => void }) {
  return compare.map((c) => (
    <span key={c.symbol} className="inline-flex items-center gap-1 text-xs tabular-nums" style={{ color: c.color }}>
      <span title={c.from ? `Rebased to ${symbol} on ${c.from}` : 'No shared bars in this range'}>
        {c.symbol}
        {c.change !== null && ` ${c.change >= 0 ? '+' : ''}${c.change.toFixed(2)}%`}
      </span>
      <button
        type="button"
        aria-label={`Stop comparing ${c.symbol}`}
        onClick={() => onRemove(c.symbol)}
        className={`text-slate-400 hover:text-rose-600 ${focusRing}`}
      >
        ×
      </button>
    </span>
  ));
}

type Slot = ReturnType<typeof useChartSlot>;

/** One grid cell: its symbol, compare chips and a compact chart. */
function CellFrame({
  chartId,
  symbol,
  slot,
  active,
  height,
  crosshair,
  onActivate,
  onSearch,
  onIndicators,
  onAlert,
}: {
  chartId: string;
  symbol: string;
  slot: Slot;
  active: boolean;
  height: number;
  crosshair?: CrosshairSync;
  onActivate: () => void;
  onSearch: () => void;
  onIndicators: () => void;
  onAlert: (price: number) => void;
}) {
  return (
    <section
      aria-label={`Chart ${chartId}: ${symbol}`}
      aria-current={active ? 'true' : undefined}
      onPointerDownCapture={onActivate}
      onFocusCapture={onActivate}
      className={`grid-cell min-w-0 rounded-sm border p-1 ${
        active ? 'border-indigo-500 ring-1 ring-indigo-500/40' : 'border-slate-200 dark:border-slate-800'
      }`}
    >
      {slot.shell.ready ? (
        <PriceChart {...slot.chartProps} chartLabel={<>
          <button type="button" onClick={onSearch} className={`font-semibold text-xs ${focusRing}`} title="Change this chart's symbol">{symbol}</button>
          <CompareChips symbol={symbol} compare={slot.compare} onRemove={(s) => slot.setCompare(slot.compareSymbols.filter((x) => x !== s))} />
        </>} height={height} compact toolRail={active} onOpenIndicators={onIndicators} onAlertAtPrice={onAlert} crosshairSync={crosshair} />
      ) : (
        <div style={{ height }} />
      )}
    </section>
  );
}

/** A grid cell other than the active one: it loads its own chart. */
function GridCell(
  props: Omit<Parameters<typeof CellFrame>[0], 'slot'> & {
    strategyName: string;
    syncedInterval?: { interval: ChartInterval; onChange: (next: ChartInterval) => void };
  },
) {
  const slot = useChartSlot(props.chartId, props.symbol, props.strategyName, props.syncedInterval);
  return <CellFrame {...props} slot={slot} />;
}

function ChartWorkspace({ symbol }: { symbol: string }) {
  const navigate = useNavigate();
  const height = useChartHeight();
  const { strategyName } = useStrategy();
  const grid = useLayout();
  const activeId = grid.active;
  const multi = grid.slots.length > 1;
  const narrow = useMediaQuery('(max-width: 1023px)');
  const slot = useChartSlot(activeId, symbol, strategyName);
  const { shell, chart: workspace, overlays, updateOverlays, catalogue, compare, compareSymbols, setCompare } = slot;
  const drawings = useSymbolDrawings(symbol);
  const crosshair = useMemo(createCrosshairSync, []);
  const [search, setSearch] = useState<{ open: boolean; initial: string; compare?: boolean }>({
    open: false,
    initial: '',
  });
  const searchOpenRef = useRef(false);
  const openSearch = (initial: string, compare = false) => {
    // Key events can arrive before the native dialog takes focus. Set the ref
    // synchronously so a fast typist's next character cannot replace the first.
    searchOpenRef.current = true;
    setSearch({ open: true, initial, compare });
  };
  const closeSearch = () => {
    searchOpenRef.current = false;
    setSearch((s) => ({ ...s, open: false, compare: false }));
  };
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [indicatorsOpen, setIndicatorsOpen] = useState(false);
  const { panel, setPanel } = useRightPanel();
  const [panelOverlay, setPanelOverlay] = useState(false);
  const [alertPrice, setAlertPrice] = useState<number>();
  const alertAt = (price: number) => {
    setAlertPrice(price);
    setPanel('alerts');
    setPanelOverlay(window.innerWidth < 1024);
  };
  const watchlist = useWatchlistDetail(strategyName);
  const toggleWatchlist = useWatchlistToggle();
  const listed = watchlist.data?.items.some((i) => i.symbol === symbol) ?? false;
  // The key handler is registered once; refs give it the current values.
  const keyState = useRef({ symbol, listed, ready: !!watchlist.data, toggle: toggleWatchlist.mutate });
  keyState.current = { symbol, listed, ready: !!watchlist.data, toggle: toggleWatchlist.mutate };

  // Remember a symbol the route opens on the active chart, so `/chart` and the
  // next visit reopen it. Only a route change writes: activating a cell changes
  // the active chart first (see `activate`), and must not copy the old symbol in.
  const routed = useRef<string | null>(null);
  useEffect(() => {
    if (!workspace.ready || routed.current === symbol) return;
    routed.current = symbol;
    if (workspace.chart.symbol !== symbol) workspace.update({ symbol });
  }, [workspace.ready, workspace.chart.symbol, symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  /** A cell's symbol: the route's when it is active or symbols are synced, else its own. */
  const symbolOf = (chartId: string) =>
    chartId === activeId || grid.sync.symbol ? symbol : (grid.charts[chartId]?.symbol ?? symbol);
  const activate = (chartId: string) => {
    if (chartId === activeId) return;
    const next = symbolOf(chartId);
    flushSync(() => grid.setActive(chartId));
    if (next !== symbol) navigate(`/chart/${encodeURIComponent(next)}`);
  };
  const syncedInterval = grid.sync.interval
    ? { interval: shell.chartProps.interval, onChange: (next: ChartInterval) => workspace.update({ interval: next }) }
    : undefined;
  const cellHeight = Math.max(
    90,
    Math.floor((height + GRID_EXTRA - (grid.layout.rows - 1) * GRID_GAP) / grid.layout.rows) - CELL_CHROME,
  );

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
      if (searchOpenRef.current) {
        // showModal() can briefly leave focus on the dialog or the chart before
        // its input receives autofocus. Buffer keys in that gap; once the
        // search input is the target, let the native input handle them.
        const target = e.target as HTMLElement | null;
        const inSearchInput = !!target?.closest('input[aria-label="Symbol or company"]');
        if (!inSearchInput && !e.ctrlKey && !e.metaKey && !e.altKey && /^[a-z0-9]$/i.test(e.key)) {
          e.preventDefault();
          setSearch((s) => ({ ...s, initial: s.initial + e.key }));
        }
        return;
      }
      const open = opensSearch(e);
      if (!open) return;
      e.preventDefault();
      openSearch(open.initial);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const name = useSecuritySearch(symbol, 1).results.find((r) => r.symbol === symbol)?.name;
  const last = shell.bars.at(-1);
  const prev = shell.bars.at(-2);
  const change = last && prev ? (parseFloat(last.close) / parseFloat(prev.close) - 1) * 100 : null;

  return (
    <main className="chart-workspace w-full mx-auto px-2 sm:px-3 py-2">
      <header className="workspace-header flex flex-wrap items-center gap-x-3 gap-y-1 mb-2">
        <h1 className="text-lg font-bold tracking-tight">
          <button
            type="button"
            onClick={() => openSearch('')}
            title="Change symbol (type, /, or Ctrl/⌘+K)"
            className="hover:text-indigo-600 dark:hover:text-indigo-400"
          >
            {symbol}
          </button>
        </h1>
        {name && <span className="symbol-company hidden xl:inline text-sm text-slate-500 dark:text-slate-400">{name}</span>}
        {last && <span className="text-sm font-semibold tabular-nums">{parseFloat(last.close).toFixed(2)}</span>}
        {change !== null && (
          <span className={`text-sm tabular-nums ${change >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'}`}>
            {change >= 0 ? '+' : ''}
            {change.toFixed(2)}%
          </span>
        )}
        {!multi && (
          <CompareChips symbol={symbol} compare={compare} onRemove={(s) => setCompare(compareSymbols.filter((x) => x !== s))} />
        )}
        <span className="hidden sm:inline text-[10px] uppercase tracking-wider text-slate-500">NSE · EOD</span>
        <span className="flex-1" />
        <select
          aria-label="Layout"
          value={grid.layout.id}
          onChange={(e) => grid.setLayout(e.target.value as Layout)}
          className={`rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-1.5 py-0.5 text-xs ${focusRing}`}
        >
          {LAYOUTS.map((l) => (
            <option key={l.id} value={l.id}>
              {l.label}
            </option>
          ))}
        </select>
        {multi && (
          <span role="group" aria-label="Sync" className="inline-flex items-center gap-2 text-xs text-slate-500">
            Sync
            {(['symbol', 'interval', 'crosshair'] as const).map((key) => (
              <label key={key} className="inline-flex items-center gap-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={grid.sync[key]}
                  onChange={(e) => grid.setSync({ [key]: e.target.checked })}
                  className="w-3 h-3 accent-indigo-500"
                />
                {key[0].toUpperCase() + key.slice(1)}
              </label>
            ))}
          </span>
        )}
        <button
          type="button"
          onClick={() => openSearch('', true)}
          disabled={compareSymbols.length >= MAX_COMPARE}
          title={`Compare with another symbol (up to ${MAX_COMPARE})`}
          className={btn}
        >
          Compare
        </button>
        <button type="button" className={`${btn} hidden sm:inline-block`} onClick={() => { setPanel('details'); setPanelOverlay(window.innerWidth < 1024); }}>Analyse</button>
        <Link to={`/stock/${encodeURIComponent(symbol)}`} className={`${btn} hidden md:inline-block`}>Research</Link>
        <SaveState documents={[workspace, drawings]} />
        <button type="button" onClick={() => setIndicatorsOpen(true)} title="Indicators (Alt+I)" className={btn}>
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
          onClick={() => { if (window.innerWidth < 1024 || grid.slots.length >= 9) { setPanelOverlay(!panelOverlay); if (!panel) setPanel('watchlist'); } else setPanel(panel ? null : 'watchlist'); }}
          aria-pressed={!!panel && ((!narrow && grid.slots.length < 9) || panelOverlay)}
          className={`inline-block px-2 py-0.5 rounded-md text-xs border border-slate-200 dark:border-slate-700 ${focusRing} ${
            panel ? 'text-indigo-700 dark:text-indigo-300' : 'text-slate-500'
          }`}
        >
          {panel && ((!narrow && grid.slots.length < 9) || panelOverlay) ? 'Hide panel' : 'Panel'}
        </button>
      </header>

      <div className="flex gap-2">
        <div className="flex-1 min-w-0">
          {!multi ? (
            shell.ready ? (
              <PriceChart
                {...slot.chartProps}
                onOpenIndicators={() => setIndicatorsOpen(true)}
                onAlertAtPrice={alertAt}
                height={height}
                autoHeight
                toolRail
              />
            ) : (
              <LoadingSpinner />
            )
          ) : (
            <div
              className="grid"
              style={{ gap: GRID_GAP, gridTemplateColumns: `repeat(${grid.layout.cols}, minmax(0, 1fr))` }}
            >
              {grid.slots.map((chartId) => {
                const cell = {
                  chartId,
                  symbol: symbolOf(chartId),
                  active: chartId === activeId,
                  height: cellHeight,
                  crosshair: grid.sync.crosshair ? crosshair : undefined,
                  onActivate: () => activate(chartId),
                  onSearch: () => openSearch(''),
                  onIndicators: () => setIndicatorsOpen(true),
                  onAlert: alertAt,
                };
                return <GridCell key={chartId} {...cell} strategyName={strategyName} syncedInterval={syncedInterval} />;
              })}
            </div>
          )}
        </div>
        {panel && (grid.slots.length < 9 || panelOverlay) && (
          <div className="workspace-panel w-72 shrink-0" data-open={panelOverlay}>
            <SidePanel
              symbol={symbol}
              strategy={strategyName}
              panel={panel}
              onPanel={(next) => { setPanel(next); if (!next) setPanelOverlay(false); }}
              onOpenSymbol={(next) => navigate(`/chart/${encodeURIComponent(next)}`)}
              height={height + 64}
              alertPrice={alertPrice}
            />
          </div>
        )}
      </div>
      <ShortcutsDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <IndicatorDialog
        open={indicatorsOpen}
        onClose={() => setIndicatorsOpen(false)}
        active={overlays.indicators}
        anchorDate={shell.chartProps.initialWindow?.from}
        onChange={(indicators) => updateOverlays({ indicators, presetEdited: true })}
        legend={catalogue.legend}
        paneCount={catalogue.paneCount}
        maxPanes={MAX_PANES}
      />

      <SymbolSearchDialog
        open={search.open}
        initialText={search.initial}
        label={search.compare ? 'Compare with' : undefined}
        onChoose={(next) => {
          if (!search.compare) navigate(`/chart/${encodeURIComponent(next)}`);
          else if (next !== symbol && !compareSymbols.includes(next)) setCompare([...compareSymbols, next]);
        }}
        onClose={closeSearch}
      />
    </main>
  );
}
