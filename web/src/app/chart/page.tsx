/**
 * The chart workspace (M11): Find → Analyse → Draw → Restore.
 *
 * Chart first: the chart takes the free height. Everything the owner sets here
 * (range, moving averages, panes, drawings) is saved on the server as they
 * work, and comes back on reload or in another browser (ADR-013 §5).
 *
 * M13 adds layouts of up to 4 × 4 charts. The route's symbol is the active
 * chart's. Grid cells are compact charts; a click makes one active, and the
 * toolbar, the dialogs and the keys act on it.
 *
 * The toolbar sits in the shell's header bar (D23), so the chart keeps one row
 * of chrome. The plot fills its grid cell; nothing here assumes a fixed
 * chrome height.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal, flushSync } from 'react-dom';
import { Navigate, useNavigate, useParams } from 'react-router';
import { useStrategy } from '@/app/strategy-context';
import { LoadingSpinner } from '@/components/shared/Card';
import { PriceChart, type ChartChrome } from '@/components/stock/PriceChart';
import { MAX_PANES } from '@/components/stock/useCatalogueIndicators';
import { IndicatorDialog } from '@/components/workspace/IndicatorDialog';
import { SaveState } from '@/components/workspace/SaveState';
import { Popover } from '@/components/shell/Popover';
import { useShell, useShellPanel } from '@/components/shell/shell-context';
import { useWatchlistDetail, useWatchlistToggle } from '@/components/workspace/SidePanel';
import { SymbolSearchDialog } from '@/components/workspace/SymbolSearchDialog';
import { MAX_COMPARE, type CompareLine } from '@/components/workspace/useCompare';
import { useChartSlot } from '@/components/workspace/useChartSlot';
import { useSecuritySearch } from '@/components/workspace/useSecuritySearch';
import { createCrosshairSync, type CrosshairSync } from '@/lib/crosshair-sync';
import { isTyping, opensSearch } from '@/lib/shortcuts';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { focusRing } from '@/lib/theme';
import type { ChartInterval } from '@/lib/types';
import { LAYOUTS, useLayout, useSymbolDrawings, useWorkspaceChart, type Layout } from '@/lib/workspace';

/** Shown on a fresh install, before the owner has opened any symbol. */
const FIRST_SYMBOL = 'RELIANCE';
const GRID_GAP = 3;

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

const btn = `chart-toolbar-button inline-flex ${focusRing}`;

const LAYOUT_ICON = (
  <svg viewBox="0 0 20 20" className="w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="3" width="6" height="6" rx="1" /><rect x="11" y="3" width="6" height="6" rx="1" /><rect x="3" y="11" width="6" height="6" rx="1" /><rect x="11" y="11" width="6" height="6" rx="1" />
  </svg>
);

/** The layout chooser and, with more than one chart, what the charts share. */
function LayoutPopover({ grid, multi, className }: { grid: ReturnType<typeof useLayout>; multi: boolean; className?: string }) {
  return (
    <Popover label="Layout" panelLabel="Layout and sync" className={className} title={`Layout: ${grid.layout.label}`} icon={LAYOUT_ICON} panelClassName="right-0 w-56 p-2 text-xs">
      {(close) => (
        <>
          <fieldset>
            <legend className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Layout</legend>
            {LAYOUTS.map((l) => (
              <label key={l.id} className="flex items-center gap-2 px-1 py-1 rounded cursor-pointer hover:bg-[var(--ws-muted)]">
                <input
                  type="radio"
                  name="layout"
                  value={l.id}
                  checked={grid.layout.id === l.id}
                  onChange={() => { grid.setLayout(l.id as Layout); close(); }}
                  className="accent-indigo-600"
                />
                {l.label}
              </label>
            ))}
          </fieldset>
          {multi && (
            <div role="group" aria-label="Sync" className="mt-2 pt-2 border-t border-[var(--ws-line)]">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Sync</p>
              {(['symbol', 'interval', 'crosshair'] as const).map((key) => (
                <label key={key} className="flex items-center gap-2 px-1 py-1 cursor-pointer">
                  <input type="checkbox" checked={grid.sync[key]} onChange={(e) => grid.setSync({ [key]: e.target.checked })} className="accent-indigo-600" />
                  {key[0].toUpperCase() + key.slice(1)}
                </label>
              ))}
            </div>
          )}
        </>
      )}
    </Popover>
  );
}

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
  chrome,
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
  /** The page's chrome slots, for the active cell only. */
  chrome?: ChartChrome;
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
      data-plot-cell
      className={`grid-cell min-w-0 min-h-0 overflow-hidden rounded-sm border p-1 ${
        active ? 'border-indigo-500 ring-1 ring-indigo-500/40' : 'border-slate-200 dark:border-slate-800'
      }`}
    >
      {slot.shell.ready ? (
        <PriceChart {...slot.chartProps} chartLabel={<>
          <button type="button" onClick={onSearch} className={`font-semibold text-xs ${focusRing}`} title="Change this chart's symbol">{symbol}</button>
          <CompareChips symbol={symbol} compare={slot.compare} onRemove={(s) => slot.setCompare(slot.compareSymbols.filter((x) => x !== s))} />
        </>} height={160} autoHeight compact toolRail={active} chrome={active ? chrome : undefined} onOpenIndicators={onIndicators} onAlertAtPrice={onAlert} crosshairSync={crosshair} />
      ) : (
        <div className="h-full" />
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
  const { strategyName } = useStrategy();
  const grid = useLayout();
  const activeId = grid.active;
  const multi = grid.slots.length > 1;
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
  const [indicatorsOpen, setIndicatorsOpen] = useState(false);
  const { openPanel, routeSlot } = useShell();
  // Dense layouts release the panel's width; it then opens over the charts.
  useShellPanel({ symbol, assessment: true, saved: true, inline: grid.slots.length < 9 });
  const alertAt = (price: number) => openPanel('alerts', price);
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
  const [railSlot, setRailSlot] = useState<HTMLElement | null>(null);
  const [toolbarSlot, setToolbarSlot] = useState<HTMLElement | null>(null);
  const [chartTypeSlot, setChartTypeSlot] = useState<HTMLElement | null>(null);
  const [historySlot, setHistorySlot] = useState<HTMLElement | null>(null);
  const [settingsSlot, setSettingsSlot] = useState<HTMLElement | null>(null);
  const [menuChartTypeSlot, setMenuChartTypeSlot] = useState<HTMLElement | null>(null);
  const [menuHistorySlot, setMenuHistorySlot] = useState<HTMLElement | null>(null);
  const [menuSettingsSlot, setMenuSettingsSlot] = useState<HTMLElement | null>(null);
  const [rangeSlot, setRangeSlot] = useState<HTMLElement | null>(null);
  const sm = useMediaQuery('(min-width: 640px)');
  const lg = useMediaQuery('(min-width: 1024px)');
  const xl = useMediaQuery('(min-width: 1280px)');
  const chrome: ChartChrome = {
    rail: railSlot,
    toolbar: toolbarSlot,
    chartType: lg ? chartTypeSlot : menuChartTypeSlot,
    history: xl ? historySlot : menuHistorySlot,
    settings: xl ? settingsSlot : menuSettingsSlot,
    rangeBar: rangeSlot,
    resetKey: grid.layout.id,
  };
  const activate = (chartId: string) => {
    if (chartId === activeId) return;
    const next = symbolOf(chartId);
    // The rail is the active chart's: if focus is on one of its buttons, keep
    // it on the same button of the new active chart, never on the page body.
    const focused = document.activeElement;
    const railLabel = focused && railSlot?.contains(focused) ? focused.getAttribute('aria-label') : null;
    flushSync(() => grid.setActive(chartId));
    if (railLabel) {
      const target = railSlot?.querySelector<HTMLElement>(`[aria-label="${CSS.escape(railLabel)}"]`)
        ?? document.querySelector<HTMLElement>(`[aria-label^="Chart ${chartId}:"] [data-testid="price-chart"]`);
      target?.focus();
    }
    if (next !== symbol) navigate(`/chart/${encodeURIComponent(next)}`);
  };
  const syncedInterval = grid.sync.interval
    ? { interval: shell.chartProps.interval, onChange: (next: ChartInterval) => workspace.update({ interval: next }) }
    : undefined;

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

  const compareFull = compareSymbols.length >= MAX_COMPARE;
  const compareTitle = `Compare with another symbol (up to ${MAX_COMPARE})`;
  const indicatorsLabel = `Indicators${overlays.indicators.length > 0 ? ` · ${overlays.indicators.length}` : ''}`;
  // TradingView's priority order: what does not fit folds into the ⋯ menu.
  // Chart groups render into whichever slot is current, inline or in the menu.
  const folded = { compare: !lg, chartType: !lg, history: !xl, settings: !xl, indicators: !sm, save: !sm };
  const toolbar = (
    <div className="chart-toolbar">
      <h1 className="text-[15px] font-bold tracking-tight">
        <button
          type="button"
          onClick={() => openSearch('')}
          title="Change symbol (type, /, or Ctrl/⌘+K)"
          className={`px-1.5 rounded hover:bg-[var(--ws-muted)] ${focusRing}`}
        >
          {symbol}
        </button>
      </h1>
      {name && <span className="symbol-company hidden 2xl:inline text-xs text-slate-500 dark:text-slate-400 truncate max-w-48">{name}</span>}
      {last && <span className="hidden sm:inline text-xs font-semibold tabular-nums">{parseFloat(last.close).toFixed(2)}</span>}
      {change !== null && (
        <span className={`hidden sm:inline text-xs tabular-nums ${change >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'}`}>
          {change >= 0 ? '+' : ''}
          {change.toFixed(2)}%
        </span>
      )}
      <span className="chart-toolbar-sep" />
      {!folded.compare && (
        <button type="button" onClick={() => openSearch('', true)} disabled={compareFull} title={compareTitle} className={btn}>
          <span aria-hidden="true">+ </span>Compare
        </button>
      )}
      <span ref={setToolbarSlot} className="contents" />
      {!folded.chartType && <span ref={setChartTypeSlot} className="contents" />}
      {!multi && xl && <CompareChips symbol={symbol} compare={compare} onRemove={(s) => setCompare(compareSymbols.filter((x) => x !== s))} />}
      {!folded.indicators && (
        <>
          <span className="chart-toolbar-sep" />
          <button type="button" onClick={() => setIndicatorsOpen(true)} title="Indicators (Alt+I)" className={btn}>
            <span aria-hidden="true" className="italic font-serif">fx </span>{indicatorsLabel}
          </button>
        </>
      )}
      {!folded.compare && (
        <button type="button" onClick={() => openPanel('alerts')} title="Create an alert for this symbol" className={btn}>
          Alert
        </button>
      )}
      {!folded.history && <span ref={setHistorySlot} className="contents" />}
      <span className="flex-1" />
      {!folded.compare && <LayoutPopover grid={grid} multi={multi} />}
      {!xl && (
        <Popover label="More chart controls" icon={<span aria-hidden="true" className="text-base leading-none">⋯</span>} panelClassName="right-0 w-60 p-1 flex flex-col items-stretch gap-1">
          {(close) => (
            <>
              {folded.compare && <button type="button" onClick={() => { close(); openSearch('', true); }} disabled={compareFull} title={compareTitle} className={`${btn} justify-start`}>Compare</button>}
              {folded.indicators && <button type="button" onClick={() => { close(); setIndicatorsOpen(true); }} className={`${btn} justify-start`}>{indicatorsLabel}</button>}
              {folded.compare && <button type="button" onClick={() => { close(); openPanel('alerts'); }} className={`${btn} justify-start`}>Alert</button>}
              {folded.compare && <div className="flex items-center gap-2 px-2 py-1 text-xs">Layout <LayoutPopover grid={grid} multi={multi} /></div>}
              {folded.chartType && <div ref={setMenuChartTypeSlot} className="flex items-center gap-2 px-2 py-1 text-xs" />}
              <div ref={setMenuHistorySlot} className="flex items-center gap-1 px-1 py-1" />
              <div ref={setMenuSettingsSlot} className="flex items-center gap-1 px-1 py-1" />
              {folded.save && <div className="px-2 py-1"><SaveState documents={[workspace, drawings]} /></div>}
            </>
          )}
        </Popover>
      )}
      {!folded.save && <SaveState documents={[workspace, drawings]} />}
      {!folded.settings && <span ref={setSettingsSlot} className="contents" />}
    </div>
  );

  return (
    <main className="chart-page" data-layout={grid.layout.id}>
      {routeSlot && createPortal(toolbar, routeSlot)}
      <div className="chart-body">
      <div ref={setRailSlot} className="chart-rail" />
      {!multi ? (
        <div className="chart-stage" data-plot-cell>
          {shell.ready ? (
            <PriceChart {...slot.chartProps} legendTitle={`${symbol} · ${slot.chartProps.interval ?? '1D'} · NSE`} onOpenIndicators={() => setIndicatorsOpen(true)} onAlertAtPrice={alertAt} autoHeight toolRail chrome={chrome} />
          ) : (
            <LoadingSpinner />
          )}
        </div>
      ) : (
        <div
          className="chart-stage grid"
          style={{ gap: GRID_GAP, gridTemplateColumns: `repeat(${grid.layout.cols}, minmax(0, 1fr))`, gridTemplateRows: `repeat(${grid.layout.rows}, minmax(0, 1fr))` }}
        >
          {grid.slots.map((chartId) => {
            const cell = {
              chartId,
              symbol: symbolOf(chartId),
              active: chartId === activeId,
              crosshair: grid.sync.crosshair ? crosshair : undefined,
              onActivate: () => activate(chartId),
              onSearch: () => openSearch(''),
              onIndicators: () => setIndicatorsOpen(true),
              onAlert: alertAt,
            };
            return <GridCell key={chartId} {...cell} chrome={chrome} strategyName={strategyName} syncedInterval={syncedInterval} />;
          })}
        </div>
      )}
      </div>
      <div className="chart-rangebar">
        <span ref={setRangeSlot} className="chart-slot contents" />
      </div>
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
