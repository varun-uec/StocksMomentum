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
import { Link, Navigate, useNavigate, useParams } from 'react-router';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useStrategy } from '@/app/strategy-context';
import { LoadingSpinner } from '@/components/shared/Card';
import { PriceChart, type ChartChrome, type EvidenceLayer } from '@/components/stock/PriceChart';
import { LegendChip, type EvidenceControl } from '@/components/momentum25/evidence';
import { useLatestRun } from '@/components/momentum25/run';
import { ScreenerPanel } from '@/components/momentum25/ScreenerPanel';
import { MAX_PANES } from '@/components/stock/useCatalogueIndicators';
import { IndicatorDialog } from '@/components/workspace/IndicatorDialog';
import { ReplayBar, type Replay } from '@/components/workspace/ReplayBar';
import { SaveState } from '@/components/workspace/SaveState';
import { Popover } from '@/components/shell/Popover';
import { useShell, useShellPanel } from '@/components/shell/shell-context';
import { useWatchlistDetail, useWatchlistToggle } from '@/components/workspace/SidePanel';
import { SymbolSearchDialog } from '@/components/workspace/SymbolSearchDialog';
import { MAX_COMPARE, type CompareLine } from '@/components/workspace/useCompare';
import { useChartSlot } from '@/components/workspace/useChartSlot';
import { useSecuritySearch } from '@/components/workspace/useSecuritySearch';
import { createCrosshairSync, type CrosshairSync } from '@/lib/crosshair-sync';
import { getLatestRunForStrategy, getOhlcv, listStrategies } from '@/lib/api-client';
import type { ReplayState } from '@/lib/replay';
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

type BottomState = 'closed' | 'open' | 'max';
const BOTTOM_KEY = 'wickstreet.bottomPanel';

/**
 * The bottom panel (plan 2026-10-19, step 6): the embedded Stock Screener, and
 * Strategy Studio and Research as shell navigation that remembers the chart.
 * Open or closed is a per-viewer convenience, so it lives in localStorage.
 */
function BottomPanel({ symbol, strategy, configHash, replay, onOpenSymbol }: { symbol: string; strategy: string; configHash?: string; replay?: ReplayState; onOpenSymbol: (symbol: string) => void }) {
  const { data: strategies } = useQuery({
    queryKey: ['strategies', 'workspace'],
    queryFn: () => listStrategies(false, true),
    staleTime: 30_000,
  });
  const savedConfig = strategies?.find((item) => item.config_hash === configHash && item.kind === 'user');
  const [state, setState] = useState<BottomState>(() => {
    try {
      const saved = localStorage.getItem(BOTTOM_KEY);
      return saved === 'open' || saved === 'max' ? saved : 'closed';
    } catch {
      return 'closed';
    }
  });
  const save = (next: BottomState) => {
    setState(next);
    try {
      localStorage.setItem(BOTTOM_KEY, next);
    } catch {
      // Private mode: the panel still works for this visit.
    }
  };
  const from = encodeURIComponent(`/chart/${symbol}`);
  const researchHref = savedConfig ? `/studio?from=${from}` : `/strategies?from=${from}`;
  const researchLabel = savedConfig ? 'Research in Studio' : 'Research';
  const tab = `px-2 h-6 inline-flex items-center rounded text-xs font-medium hover:bg-[var(--ws-muted)] ${focusRing}`;
  return (
    <section aria-label="Bottom panel" className="chart-bottom" data-state={state}>
      <div className="chart-bottom-bar">
        <button type="button" aria-expanded={state !== 'closed'} aria-controls="chart-bottom-body" onClick={() => save(state === 'closed' ? 'open' : 'closed')} className={`${tab} ${state !== 'closed' ? 'text-[var(--ws-accent)]' : ''}`}>
          Stock Screener
        </button>
        <Link to={`/studio?from=${from}`} className={tab}>Strategy Studio</Link>
        <Link to={researchHref} className={tab}>{researchLabel}</Link>
        <span className="flex-1" />
        <button type="button" onClick={() => save(state === 'max' ? 'open' : 'max')} aria-label={state === 'max' ? 'Restore bottom panel' : 'Maximise bottom panel'} title={state === 'max' ? 'Restore' : 'Maximise'} className={`${tab} w-6 justify-center`}>
          <span aria-hidden="true">{state === 'max' ? '⤡' : '⤢'}</span>
        </button>
        <button type="button" onClick={() => save(state === 'closed' ? 'open' : 'closed')} aria-label={state === 'closed' ? 'Expand bottom panel' : 'Collapse bottom panel'} title={state === 'closed' ? 'Expand' : 'Collapse'} className={`${tab} w-6 justify-center`}>
          <span aria-hidden="true">{state === 'closed' ? '▴' : '▾'}</span>
        </button>
      </div>
      {state !== 'closed' && (
        <div id="chart-bottom-body" className="chart-bottom-body">
          <ScreenerPanel strategy={strategy} configHash={configHash} symbol={symbol} replay={replay} onOpenSymbol={onOpenSymbol} />
        </div>
      )}
    </section>
  );
}

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
  onAlertOnDrawing,
  evidenceLayers,
  onRemoveEvidence,
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
  /** Absent in replay: alerts are paused. */
  onAlert?: (price: number) => void;
  onAlertOnDrawing?: (drawingId: string) => void;
  evidenceLayers?: EvidenceLayer[];
  onRemoveEvidence?: (id: string) => void;
}) {
  return (
    <section
      aria-label={`Chart ${chartId}: ${symbol}`}
      aria-current={active ? 'true' : undefined}
      onPointerDownCapture={onActivate}
      onFocusCapture={onActivate}
      data-plot-cell
      className={`grid-cell min-w-0 min-h-0 overflow-hidden rounded-sm border p-1 ${
        active ? 'border-[var(--ws-accent)]' : 'border-[var(--ws-line)]'
      }`}
    >
      {slot.shell.ready ? (
        <PriceChart {...slot.chartProps} chartLabel={<>
          <button type="button" onClick={onSearch} className={`font-semibold text-xs ${focusRing}`} title="Change this chart's symbol">{symbol}</button>
          <CompareChips symbol={symbol} compare={slot.compare} onRemove={(s) => slot.setCompare(slot.compareSymbols.filter((x) => x !== s))} />
        </>} height={160} autoHeight compact bare toolRail={active} chrome={active ? chrome : undefined} onOpenIndicators={onIndicators} onAlertAtPrice={onAlert} onAlertOnDrawing={onAlertOnDrawing} crosshairSync={crosshair} evidenceLayers={evidenceLayers} onRemoveEvidence={onRemoveEvidence} />
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
    strategyHash?: string;
    syncedInterval?: { interval: ChartInterval; onChange: (next: ChartInterval) => void };
    replayDate?: string;
  },
) {
  const slot = useChartSlot(props.chartId, props.symbol, props.strategyName, props.strategyHash, props.syncedInterval, props.replayDate);
  return <CellFrame {...props} slot={slot} />;
}

function ChartWorkspace({ symbol }: { symbol: string }) {
  const navigate = useNavigate();
  const { strategyName, strategyHash } = useStrategy();
  const grid = useLayout();
  const activeId = grid.active;
  const multi = grid.slots.length > 1;
  // Bar replay (plan B2): page state, never saved; every chart on the page replays the same date.
  const [replay, setReplay] = useState<Replay | null>(null);
  const replayDate = replay?.date;
  const slot = useChartSlot(activeId, symbol, strategyName, strategyHash, undefined, replayDate);
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
  const { openPanel, routeSlot, objectsSlot } = useShell();
  const latestRun = useLatestRun(strategyName, strategyHash).data;

  const alertAt = replay ? undefined : (price: number) => openPanel('alerts', price);
  const alertOn = replay ? undefined : (drawingId: string) => openPanel('alerts', undefined, drawingId);
  // Step targets: the active symbol's stored daily sessions (the shell's own cached key).
  const daily = useQuery({ queryKey: ['stock-ohlcv', symbol, '1D'], queryFn: () => getOhlcv(symbol, undefined, undefined, '1D'), enabled: !!replay });
  const sessions = useMemo(() => daily.data?.bars.map((b) => b.date) ?? [], [daily.data]);
  // Momentum25 context in replay: the newest run on or before the date, never a later one.
  const replayRun = useQuery({
    queryKey: ['replay-run', strategyName, strategyHash, replayDate],
    queryFn: () => getLatestRunForStrategy(strategyName, replayDate, strategyHash),
    enabled: !!replayDate,
    // An earlier step's run is still on or before this date, so it may stay while the next loads.
    placeholderData: keepPreviousData,
  });
  const replayRunId = replayDate ? (replayRun.data === undefined ? undefined : (replayRun.data?.id ?? null)) : undefined;
  const replayState = useMemo<ReplayState | undefined>(() => (replayDate ? { date: replayDate, runId: replayRunId } : undefined), [replayDate, replayRunId]);
  const startReplay = () => {
    const dates = shell.bars.map((b) => b.date);
    if (dates.length > 1) setReplay({ date: dates[Math.max(0, dates.length - 61)], playing: false, speed: '1×' });
  };
  const watchlist = useWatchlistDetail(strategyName, strategyHash);
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

  // Assessment's "Show on chart" layers: page state per chart, never saved (plan C).
  const [evidence, setEvidence] = useState<Record<string, { symbol: string; layers: EvidenceLayer[] }>>({});
  const layersOf = (chartId: string) => (evidence[chartId]?.symbol === symbolOf(chartId) ? evidence[chartId].layers : []);
  const removeEvidence = (chartId: string, id: string) =>
    setEvidence((all) => ({ ...all, [chartId]: { symbol: all[chartId].symbol, layers: all[chartId].layers.filter((l) => l.id !== id) } }));
  const slotKey = grid.slots.join(',');
  useEffect(() => {
    // A layout change that removes a chart drops its layers.
    setEvidence((all) => Object.fromEntries(Object.entries(all).filter(([id]) => slotKey.split(',').includes(id))));
  }, [slotKey]);
  const activeLayers = layersOf(activeId);
  const evidenceControl = useMemo<EvidenceControl>(
    () => ({
      shown: activeLayers.map((l) => l.id),
      toggle: (layer) =>
        setEvidence((all) => {
          const current = all[activeId]?.symbol === symbol ? all[activeId].layers : [];
          const layers = current.some((l) => l.id === layer.id) ? current.filter((l) => l.id !== layer.id) : [...current, layer];
          return { ...all, [activeId]: { symbol, layers } };
        }),
      elsewhere: grid.slots.filter((id) => id !== activeId && layersOf(id).length > 0 && symbolOf(id) === symbol),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [evidence, activeId, symbol, slotKey, grid.sync.symbol],
  );
  // Dense layouts release the panel's width; it then opens over the charts.
  useShellPanel({ symbol, assessment: true, saved: true, inline: grid.slots.length < 9, objects: true, evidence: evidenceControl, replay: replayState });
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
    objects: objectsSlot,
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
  const replayButton = (done?: () => void) => (
    <button type="button" onClick={() => { done?.(); if (replay) setReplay(null); else startReplay(); }} aria-pressed={!!replay} disabled={!replay && shell.bars.length < 2} title={replay ? 'Exit bar replay' : 'Bar replay: step through past sessions'} className={btn}>
      <span aria-hidden="true" className="mr-1">⏮</span>Replay
    </button>
  );
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
        <button type="button" onClick={() => openPanel('alerts')} disabled={!!replay} title={replay ? 'Alerts are paused in replay' : 'Create an alert for this symbol'} className={btn}>
          Alert
        </button>
      )}
      {!folded.compare && replayButton()}
      {!folded.history && <span ref={setHistorySlot} className="contents" />}
      <span className="flex-1" />
      {!folded.compare && <LayoutPopover grid={grid} multi={multi} />}
      {!xl && (
        <Popover label="More chart controls" icon={<span aria-hidden="true" className="text-base leading-none">⋯</span>} panelClassName="right-0 w-60 p-1 flex flex-col items-stretch gap-1">
          {(close) => (
            <>
              {folded.compare && <button type="button" onClick={() => { close(); openSearch('', true); }} disabled={compareFull} title={compareTitle} className={`${btn} justify-start`}>Compare</button>}
              {folded.indicators && <button type="button" onClick={() => { close(); setIndicatorsOpen(true); }} className={`${btn} justify-start`}>{indicatorsLabel}</button>}
              {folded.compare && <button type="button" onClick={() => { close(); openPanel('alerts'); }} disabled={!!replay} className={`${btn} justify-start`}>Alert</button>}
              {folded.compare && replayButton(close)}
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
    <div className="chart-page" data-layout={grid.layout.id}>
      {routeSlot && createPortal(toolbar, routeSlot)}
      <div className="chart-body">
      <div ref={setRailSlot} className="chart-rail" />
      {!multi ? (
        <div className="chart-stage" data-plot-cell>
          {shell.ready ? (
            <PriceChart {...slot.chartProps} legendTitle={`${symbol} · ${slot.chartProps.interval ?? '1D'} · NSE`} legendChip={<LegendChip symbol={symbol} strategy={strategyName} runId={replayState ? (replayState.runId ?? undefined) : latestRun?.id} onOpen={() => openPanel('details')} />} evidenceLayers={activeLayers} onRemoveEvidence={(id) => removeEvidence(activeId, id)} onOpenIndicators={() => setIndicatorsOpen(true)} onAlertAtPrice={alertAt} onAlertOnDrawing={alertOn} autoHeight toolRail chrome={chrome} />
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
              onAlertOnDrawing: alertOn,
              evidenceLayers: layersOf(chartId),
              onRemoveEvidence: (id: string) => removeEvidence(chartId, id),
            };
            return <GridCell key={chartId} {...cell} chrome={chrome} strategyName={strategyName} strategyHash={strategyHash} syncedInterval={syncedInterval} replayDate={replayDate} />;
          })}
        </div>
      )}
      </div>
      {replay && <ReplayBar replay={replay} sessions={sessions} loading={slot.shell.chartProps.isLoading || daily.isLoading} onChange={setReplay} onExit={() => setReplay(null)} />}
      <div className="chart-rangebar">
        <span ref={setRangeSlot} className="chart-slot contents" />
        <span className="hidden md:inline text-[10px] uppercase tracking-wider text-slate-500">EOD · NSE</span>
        <span className="hidden sm:inline text-[10px] text-slate-500">
          Charts by{' '}
          <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="underline">TradingView Lightweight Charts™</a>
        </span>
      </div>
      {sm && <BottomPanel symbol={symbol} strategy={strategyName} configHash={strategyHash} replay={replayState} onOpenSymbol={(next) => navigate(`/chart/${encodeURIComponent(next)}`)} />}
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
    </div>
  );
}
