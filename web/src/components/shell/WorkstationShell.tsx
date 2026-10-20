/**
 * The workstation shell around every route (plan 2026-10-19, D23, D24).
 *
 * One header bar: the ☰ app menu, the Wickstreet mark, symbol search and a
 * route slot that each route fills with its own controls. /chart fills it with
 * the chart toolbar, so the chart keeps one row of chrome. On the right, an
 * icon strip opens the panel for the route's context symbol. The status edge
 * at the bottom carries the chart library credit on every route. Phones keep
 * the bottom navigation.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { useStrategy } from '@/app/strategy-context';
import { AppMenu, PhoneNav, SymbolSearch } from '@/components/shared/NavBar';
import { ShortcutsDialog } from '@/components/workspace/ShortcutsDialog';
import { PANEL_TABS, PanelTabs, SidePanel, type PanelTab } from '@/components/workspace/SidePanel';
import { SymbolSearchDialog } from '@/components/workspace/SymbolSearchDialog';
import { ConflictBanner } from '@/components/workspace/SaveState';
import { isTyping, opensSearch } from '@/lib/shortcuts';
import { focusRing } from '@/lib/theme';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useRightPanel, type RightPanel } from '@/lib/workspace';
import { ShellContext, type PanelContext, type ShellApi } from './shell-context';

const SEARCH_ICON = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
    <path fillRule="evenodd" clipRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.45 4.39l3.08 3.08a1 1 0 01-1.41 1.42l-3.08-3.08A7 7 0 012 9z" />
  </svg>
);

/**
 * The right panel's state. /chart uses the panel saved with the workspace and
 * shows it inline on wide screens. Other routes open it as an overlay and
 * start closed on each visit, so it never reflows their page (D24).
 */
function useRightDock(context: PanelContext) {
  const { pathname } = useLocation();
  const saved = useRightPanel();
  const [localPanel, setLocalPanel] = useState<RightPanel>(null);
  const [overlay, setOverlay] = useState(false);
  const [alertPrice, setAlertPrice] = useState<number>();
  const desktop = useMediaQuery('(min-width: 1024px)');
  const wide = useMediaQuery('(min-width: 1280px)');

  useEffect(() => {
    setLocalPanel(null);
    setOverlay(false);
    setAlertPrice(undefined);
  }, [pathname]);

  const inline = desktop && wide && !!context.saved && context.inline !== false;
  const stored = context.saved ? saved.panel : localPanel;
  const setStored = context.saved ? saved.setPanel : setLocalPanel;
  const tabs = PANEL_TABS.filter((t) => (t.id === 'details' ? context.symbol && context.assessment : t.id === 'objects' ? context.objects : true));
  // A tab the route cannot show falls back to the watchlist; the saved choice is kept.
  const panel: PanelTab | null = stored ? (tabs.some((t) => t.id === stored) ? stored : 'watchlist') : null;
  const visible = !!panel && (inline || overlay);

  const open = (tab: PanelTab) => {
    setStored(tab);
    if (!inline) setOverlay(true);
  };
  const close = () => {
    setStored(null);
    setOverlay(false);
  };
  return {
    desktop,
    inline,
    tabs,
    panel,
    visible,
    alertPrice,
    open,
    close,
    /** A strip icon: open its tab, or collapse the panel when it is the open one. */
    select: (tab: PanelTab) => (visible && panel === tab ? (inline ? setStored(null) : setOverlay(false)) : open(tab)),
    /** The narrow-screen "Panel" button. */
    toggle: () => (visible ? setOverlay(false) : open(panel ?? 'watchlist')),
    openWithPrice: (tab: PanelTab, price?: number) => {
      setAlertPrice(price);
      open(tab);
    },
  };
}

export function WorkstationShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { strategyName } = useStrategy();
  const onChart = pathname.startsWith('/chart');
  const [routeSlot, setRouteSlot] = useState<HTMLElement | null>(null);
  const [objectsSlot, setObjectsSlot] = useState<HTMLElement | null>(null);
  const [panelContext, setPanelContextState] = useState<PanelContext>({});
  const [search, setSearch] = useState<{ open: boolean; initial: string }>({ open: false, initial: '' });
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const dock = useRightDock(panelContext);
  // Routes keep the API in effects and handlers; a ref keeps it stable across renders.
  const dockRef = useRef(dock);
  dockRef.current = dock;
  const shell = useMemo<ShellApi>(
    () => ({
      routeSlot,
      objectsSlot,
      setPanelContext: setPanelContextState,
      openPanel: (tab: PanelTab, price?: number) => dockRef.current.openWithPrice(tab, price),
    }),
    [routeSlot, objectsSlot],
  );

  useEffect(() => setSearch((s) => ({ ...s, open: false })), [pathname]);

  // `?` lists the shortcuts everywhere. Off the chart, typing, `/` or Ctrl/⌘+K
  // opens symbol search; the chart page handles those keys itself.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === '?' && !isTyping(e)) {
        e.preventDefault();
        setShortcutsOpen(true);
        return;
      }
      if (onChart) return;
      const open = opensSearch(e);
      if (!open) return;
      e.preventDefault();
      setSearch({ open: true, initial: open.initial });
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onChart]);

  const panel = dock.visible && dock.panel && (
    <div className="ws-dock-panel" data-overlay={!dock.inline}>
      <SidePanel
        panel={dock.panel}
        symbol={panelContext.symbol}
        strategy={strategyName}
        onOpenSymbol={(next) => navigate(`/chart/${encodeURIComponent(next)}`)}
        onClose={dock.close}
        alertPrice={dock.alertPrice}
        objectsRef={setObjectsSlot}
        runId={panelContext.runId}
        evidence={panelContext.evidence}
        replay={panelContext.replay}
        onOpenChart={onChart ? undefined : (next) => navigate(`/chart/${encodeURIComponent(next)}`)}
        onCreateAlert={() => dock.open('alerts')}
        tabs={dock.desktop ? undefined : <PanelTabs tabs={dock.tabs} selected={dock.panel} onSelect={dock.open} vertical={false} />}
      />
    </div>
  );

  return (
    <ShellContext.Provider value={shell}>
      <div className="ws-shell" data-route={onChart ? 'chart' : undefined}>
        <header className="ws-header">
          <nav aria-label="Workstation" className="flex items-center gap-1 shrink-0">
            <AppMenu onShortcuts={() => setShortcutsOpen(true)} />
            <Link to="/" className={`flex items-center gap-1.5 px-1 rounded ${focusRing}`}>
              <span aria-hidden="true" className="flex items-center justify-center w-6 h-6 rounded bg-indigo-600 text-white text-[11px] font-extrabold">W</span>
              <span className="brand-name sr-only xl:not-sr-only">wickstreet<span className="text-indigo-600">.</span></span>
            </Link>
          </nav>
          <SymbolSearch className="hidden lg:block shrink-0" inputClassName="w-36 xl:w-44" />
          <div ref={setRouteSlot} className="ws-route-slot" />
          <button
            type="button"
            onClick={() => setSearch({ open: true, initial: '' })}
            aria-haspopup="dialog"
            aria-expanded={search.open}
            aria-label="Search for a symbol"
            className={`lg:hidden ws-icon-button ${focusRing}`}
          >
            {SEARCH_ICON}
          </button>
          {!dock.desktop && (
            <button type="button" onClick={dock.toggle} aria-pressed={dock.visible} className={`workstation-button ${focusRing}`}>
              {dock.visible ? 'Hide panel' : 'Panel'}
            </button>
          )}
        </header>
        <ConflictBanner />
        <div className="ws-body">
          <div className="ws-main">{children}</div>
          {dock.desktop ? (
            <div className="ws-dock">
              {panel}
              <PanelTabs tabs={dock.tabs} selected={dock.visible ? dock.panel : null} onSelect={dock.select} vertical />
            </div>
          ) : (
            panel
          )}
        </div>
        {!onChart && <footer className="ws-status">
          <span className="hidden sm:inline">End of day · NSE</span>
          <span className="flex-1" />
          <span>
            Charts by{' '}
            <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="underline hover:text-[var(--ws-ink)]">
              TradingView Lightweight Charts™
            </a>
          </span>
          <Link to="/about" className="underline hover:text-[var(--ws-ink)]">About Wickstreet</Link>
        </footer>}
        <PhoneNav />
      </div>
      <ShortcutsDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <SymbolSearchDialog
        open={search.open}
        initialText={search.initial}
        onClose={() => setSearch((s) => ({ ...s, open: false }))}
        onChoose={(symbol) => navigate(`${onChart ? '/chart' : '/stock'}/${encodeURIComponent(symbol)}`)}
      />
    </ShellContext.Provider>
  );
}
