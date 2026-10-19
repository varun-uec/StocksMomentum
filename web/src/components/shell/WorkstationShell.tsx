/**
 * The workstation shell around every route (plan 2026-10-19, D23).
 *
 * One header bar: the ☰ app menu, the Wickstreet mark, symbol search and a
 * route slot that each route fills with its own controls. /chart fills it with
 * the chart toolbar, so the chart keeps one row of chrome. The status edge at
 * the bottom carries the chart library credit on every route. Phones keep the
 * bottom navigation.
 */

import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { AppMenu, PhoneNav, SymbolSearch } from '@/components/shared/NavBar';
import { ShortcutsDialog } from '@/components/workspace/ShortcutsDialog';
import { SymbolSearchDialog } from '@/components/workspace/SymbolSearchDialog';
import { ConflictBanner } from '@/components/workspace/SaveState';
import { isTyping, opensSearch } from '@/lib/shortcuts';
import { focusRing } from '@/lib/theme';
import { ShellContext, type ShellApi } from './shell-context';

const SEARCH_ICON = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
    <path fillRule="evenodd" clipRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.45 4.39l3.08 3.08a1 1 0 01-1.41 1.42l-3.08-3.08A7 7 0 012 9z" />
  </svg>
);

export function WorkstationShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const onChart = pathname.startsWith('/chart');
  const [routeSlot, setRouteSlot] = useState<HTMLElement | null>(null);
  const [search, setSearch] = useState<{ open: boolean; initial: string }>({ open: false, initial: '' });
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const shell = useMemo<ShellApi>(() => ({ routeSlot }), [routeSlot]);

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

  return (
    <ShellContext.Provider value={shell}>
      <div className="ws-shell">
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
        </header>
        <ConflictBanner />
        <div className="ws-body">
          <div className="ws-main">{children}</div>
        </div>
        <footer className="ws-status">
          <span>End of day · NSE</span>
          <span className="flex-1" />
          <span>
            Charts by{' '}
            <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="underline hover:text-[var(--ws-ink)]">
              TradingView Lightweight Charts™
            </a>
          </span>
          <Link to="/about" className="underline hover:text-[var(--ws-ink)]">About Wickstreet</Link>
        </footer>
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
