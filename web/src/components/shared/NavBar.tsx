import { Link, useLocation, useNavigate } from 'react-router';
import { useEffect, useRef, useState } from 'react';
import { useTheme, type ThemeMode } from '@/app/theme-provider';
import { useSecuritySearch } from '@/components/workspace/useSecuritySearch';
import { Popover } from '@/components/shell/Popover';
import { focusRing } from '@/lib/theme';

// Minimal SVG icons — no emoji, consistent 20×20 viewBox.
const Icons = {
  chart: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M5 2a.75.75 0 01.75.75V5h.5A.75.75 0 017 5.75v6.5a.75.75 0 01-.75.75h-.5v4.25a.75.75 0 01-1.5 0V13h-.5A.75.75 0 013 12.25v-6.5A.75.75 0 013.75 5h.5V2.75A.75.75 0 015 2zm10 0a.75.75 0 01.75.75V7h.5a.75.75 0 01.75.75v5.5a.75.75 0 01-.75.75h-.5v3.25a.75.75 0 01-1.5 0V14h-.5a.75.75 0 01-.75-.75v-5.5A.75.75 0 0113.75 7h.5V2.75A.75.75 0 0115 2zm-5 3a.75.75 0 01.75.75V9h.5a.75.75 0 01.75.75v3.5a.75.75 0 01-.75.75h-.5v2.25a.75.75 0 01-1.5 0V14h-.5a.75.75 0 01-.75-.75v-3.5A.75.75 0 018.75 9h.5V5.75A.75.75 0 0110 5z" />
    </svg>
  ),
  dashboard: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M2 4a2 2 0 012-2h4a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2V4zm8 0a2 2 0 012-2h4a2 2 0 012 2v4a2 2 0 01-2 2h-4a2 2 0 01-2-2V4zM2 14a2 2 0 012-2h4a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2v-4zm8 0a2 2 0 012-2h4a2 2 0 012 2v4a2 2 0 01-2 2h-4a2 2 0 01-2-2v-4z" />
    </svg>
  ),
  historical: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path fillRule="evenodd" clipRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-11.25a.75.75 0 00-1.5 0v4.59c0 .3.18.57.45.68l3.5 1.5a.75.75 0 00.6-1.37l-3.05-1.3V6.75z" />
    </svg>
  ),
  strategies: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M7 3a1 1 0 000 2h6a1 1 0 100-2H7zM4 7a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1zM2 11a2 2 0 012-2h12a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2v-4z" />
    </svg>
  ),
  lab: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path fillRule="evenodd" clipRule="evenodd" d="M7 2a1 1 0 00-.707 1.707L7 4.414v3.758a1 1 0 01-.293.707l-4 4C.817 14.769 2.156 18 4.828 18h10.343c2.673 0 4.012-3.231 2.122-5.121l-4-4A1 1 0 0113 8.172V4.414l.707-.707A1 1 0 0013 2H7zm2 6.172V4h2v4.172a3 3 0 00.879 2.12l.813.814A4.002 4.002 0 0113 16H7a4.002 4.002 0 01-2.692-3.894l.813-.814A3 3 0 009 8.172z" />
    </svg>
  ),
  research: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zm6-4a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zm6-3a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" />
    </svg>
  ),
  analytics: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path fillRule="evenodd" clipRule="evenodd" d="M12 7a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L12 10.586V7zM6 2a1 1 0 00-1 1v13.5A1.5 1.5 0 006.5 18h11a1.5 1.5 0 001.5-1.5V7.243a1 1 0 00-1.707-.707L15 6.793V3a1 1 0 00-1-1H6z" />
    </svg>
  ),
  backtest: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path fillRule="evenodd" clipRule="evenodd" d="M10 2a8 8 0 108 8 1 1 0 10-2 0 6 6 0 11-6-6c1.66 0 3.16.68 4.24 1.76L12.5 7.5H18V2l-1.34 1.34A7.97 7.97 0 0010 2zm-1.5 5.13a.75.75 0 00-1.13.65v4.44a.75.75 0 001.13.65l3.83-2.22a.75.75 0 000-1.3L8.5 7.13z" />
    </svg>
  ),
  learn: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3zM3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-1.128 6.008 6.008 0 004.957-4.025l-.64-1.274A8.95 8.95 0 003.31 9.397zM8 14.072l-2.4-1.029V11.6a6.008 6.008 0 004.8 0v1.443L8 14.072zm1-8.024a1 1 0 10-2 0 1 1 0 002 0z" />
    </svg>
  ),
  market: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M3 13a1 1 0 011-1h1a1 1 0 011 1v4a1 1 0 01-1 1H4a1 1 0 01-1-1v-4zm5-4a1 1 0 011-1h1a1 1 0 011 1v8a1 1 0 01-1 1H9a1 1 0 01-1-1V9zm5-6a1 1 0 011-1h1a1 1 0 011 1v14a1 1 0 01-1 1h-1a1 1 0 01-1-1V3z" />
    </svg>
  ),
  watchlist: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M10 2.5l2.35 4.76 5.25.76-3.8 3.7.9 5.23L10 14.5l-4.7 2.45.9-5.23-3.8-3.7 5.25-.76L10 2.5z" />
    </svg>
  ),
  data: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M10 2c3.87 0 7 1.12 7 2.5S13.87 7 10 7 3 5.88 3 4.5 6.13 2 10 2zM3 7.2C4.4 8.3 7.05 9 10 9s5.6-.7 7-1.8V10c0 1.38-3.13 2.5-7 2.5S3 11.38 3 10V7.2zm0 5.5c1.4 1.1 4.05 1.8 7 1.8s5.6-.7 7-1.8v2.8c0 1.38-3.13 2.5-7 2.5s-7-1.12-7-2.5v-2.8z" />
    </svg>
  ),
  menu: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
      <path fillRule="evenodd" clipRule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" />
    </svg>
  ),
  search: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
      <path fillRule="evenodd" clipRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.45 4.39l3.08 3.08a1 1 0 01-1.41 1.42l-3.08-3.08A7 7 0 012 9z" />
    </svg>
  ),
  close: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
      <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
    </svg>
  ),
  sun: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" />
    </svg>
  ),
  moon: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
    </svg>
  ),
  monitor: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path fillRule="evenodd" clipRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 011 1v8a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM2 14a1 1 0 011-1h14a1 1 0 110 2H3a1 1 0 01-1-1z" />
    </svg>
  ),
};

// The investor surface sits at the top level: today's dashboard, the
// watchlist, market breadth and the learn hub. The quant surfaces (historical
// replay, strategy comparison, validation, analytics, the experiment lab) are
// tools for building or auditing a strategy, not for daily use, so they stay
// behind the "Research" menu.
const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: Icons.dashboard },
  { href: '/chart', label: 'Chart', icon: Icons.chart },
  { href: '/watchlist', label: 'Watchlist', icon: Icons.watchlist },
  { href: '/market', label: 'Market', icon: Icons.market },
  { href: '/learn', label: 'Learn', icon: Icons.learn },
  { href: '/data', label: 'Data', icon: Icons.data },
];

const RESEARCH_TOOLS = [
  { href: '/strategies', label: 'Strategies', icon: Icons.strategies },
  { href: '/studio', label: 'Strategy Studio', icon: Icons.lab },
  { href: '/validation', label: 'Validation', icon: Icons.research },
  { href: '/historical', label: 'Historical', icon: Icons.historical },
  { href: '/analytics', label: 'Analytics', icon: Icons.analytics },
  { href: '/experiment', label: 'Experiment Lab', icon: Icons.lab },
  { href: '/backtest', label: 'Backtest', icon: Icons.backtest },
];

// The ☰ app menu: the workflows first, then help and settings.
const APP_ROUTES: NavItem[] = [
  { href: '/chart', label: 'Chart', icon: Icons.chart },
  { href: '/', label: 'Screener', icon: Icons.dashboard },
  { href: '/market', label: 'Markets', icon: Icons.market },
  { href: '/watchlist', label: 'Watchlist', icon: Icons.watchlist },
];
const HELP_ROUTES: NavItem[] = [
  { href: '/learn', label: 'Learn', icon: Icons.learn },
  { href: '/data', label: 'Data', icon: Icons.data },
  { href: '/about', label: 'About', icon: Icons.research },
];

// The bottom bar on mobile. "More" opens the research sheet.
const MOBILE_PRIMARY = NAV_ITEMS.slice(0, 3);

const THEME_OPTIONS: { mode: ThemeMode; icon: React.ReactNode; label: string }[] = [
  { mode: 'light', icon: Icons.sun, label: 'Light theme' },
  { mode: 'dark', icon: Icons.moon, label: 'Dark theme' },
  { mode: 'system', icon: Icons.monitor, label: 'Match system theme' },
];

function ThemeToggle() {
  const { mode, setMode } = useTheme();
  return (
    <div className="flex items-center gap-0.5 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-0.5">
      {THEME_OPTIONS.map((opt) => (
        <button
          key={opt.mode}
          type="button"
          onClick={() => setMode(opt.mode)}
          aria-label={opt.label}
          aria-pressed={mode === opt.mode}
          title={opt.label}
          className={`w-7 h-7 flex items-center justify-center rounded-md text-xs transition-colors ${focusRing} ${
            mode === opt.mode
              ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-300 shadow-sm'
              : 'text-slate-500 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          {opt.icon}
        </button>
      ))}
    </div>
  );
}

/**
 * Direct symbol lookup. Without this the only route to a stock's research page
 * is finding it in a ranked list, which is impossible for any symbol that did
 * not qualify in the latest run.
 */
export function SymbolSearch({ className = '', inputClassName = 'w-28 lg:w-44' }: { className?: string; inputClassName?: string }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [value, setValue] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const { query, results, searching } = useSecuritySearch(value);
  useEffect(() => setActive(-1), [results]);

  // On the chart workspace a search changes the chart; elsewhere it opens the stock's research page.
  const go = (symbol: string) => {
    setValue('');
    setOpen(false);
    const base = pathname.startsWith('/chart') ? '/chart' : '/stock';
    navigate(`${base}/${encodeURIComponent(symbol.toUpperCase())}`);
  };

  return (
    <div className={`relative ${className}`}>
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          // Enter takes the highlighted suggestion, else the best match, else
          // whatever was typed — so a known-good symbol never needs the list.
          const chosen = results[active] ?? results[0];
          const symbol = chosen ? chosen.symbol : query.toUpperCase();
          if (symbol) go(symbol);
        }}
      >
        <label htmlFor="symbol-search" className="sr-only">
          Look up a symbol
        </label>
        <input
          id="symbol-search"
          name="symbol"
          type="search"
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls="symbol-search-results"
          aria-autocomplete="list"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (!results.length) return;
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setActive((i) => (i + 1) % results.length);
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setActive((i) => (i <= 0 ? results.length - 1 : i - 1));
            } else if (e.key === 'Escape') {
              setOpen(false);
            }
          }}
          placeholder="Symbol or company…"
          title="Search by NSE symbol or company name"
          className={`${inputClassName} px-2.5 py-1.5 rounded-md text-xs uppercase tracking-wide bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 placeholder:normal-case placeholder:tracking-normal placeholder:text-slate-400 ${focusRing}`}
        />
      </form>

      {open && query.length > 0 && (
        <ul
          id="symbol-search-results"
          role="listbox"
          className="absolute right-0 mt-1 w-72 max-w-[calc(100vw-2rem)] max-h-80 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg py-1 z-50"
        >
          {results.map((r, i) => (
            <li key={r.symbol} role="option" aria-selected={i === active}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => go(r.symbol)}
                onMouseEnter={() => setActive(i)}
                className={`w-full text-left px-3 py-1.5 ${
                  i === active ? 'bg-indigo-50 dark:bg-indigo-600/20' : ''
                }`}
              >
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {r.symbol}
                </span>
                <span className="block text-[11px] text-slate-500 dark:text-slate-400 truncate">
                  {r.name}
                </span>
              </button>
            </li>
          ))}
          {!results.length && (
            <li className="px-3 py-2 text-[11px] text-slate-500 dark:text-slate-400">
              {searching ? 'Searching…' : `No listed security matches “${query}”.`}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

export function NavLink({
  item,
  pathname,
  onClick,
  from,
}: {
  item: NavItem;
  pathname: string;
  onClick?: () => void;
  /** The view it opens from, so the target offers "Back to chart". */
  from?: string;
}) {
  const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(`${item.href}/`));
  return (
    <Link
      key={item.href}
      to={from ? `${item.href}?from=${encodeURIComponent(from)}` : item.href}
      onClick={onClick}
      aria-current={isActive ? 'page' : undefined}
      // The visible label is hidden below `lg`, leaving an icon-only link.
      aria-label={item.label}
      className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${focusRing} ${
        isActive
          ? 'bg-indigo-100 dark:bg-indigo-600/20 text-indigo-700 dark:text-indigo-300'
          : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800'
      }`}
    >
      <span className={isActive ? 'text-indigo-600 dark:text-indigo-300' : 'text-slate-400 dark:text-slate-500'}>
        {item.icon}
      </span>
      {item.label}
    </Link>
  );
}

/**
 * A mobile slide-over. Focus moves in on open, Tab is trapped inside, Escape
 * closes it and focus returns to whatever opened it.
 */
function MobileSheet({
  title,
  onClose,
  children,
  className = '',
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const focusable = () =>
      Array.from(
        panelRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input, [tabindex]:not([tabindex="-1"])'
        ) ?? []
      );
    focusable()[0]?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusable();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous?.focus();
    };
  }, [onClose]);

  return (
    <div className="lg:hidden fixed inset-0 z-[60]">
      <div className="absolute inset-0 bg-slate-900/50" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] ${className}`}
      >
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={`Close ${title}`}
            className={`p-1.5 rounded-md text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
          >
            {Icons.close}
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** The ☰ app menu in the header bar: every route, the theme, the keyboard shortcuts and the chart library credit. */
export function AppMenu({ onShortcuts }: { onShortcuts: () => void }) {
  const { pathname } = useLocation();
  return (
    <Popover label="App menu" icon={Icons.menu} nav panelClassName="left-0 w-60 py-1">
      {(close) => (
        <>
          <ul>
            {APP_ROUTES.map((item) => <li key={item.href}><NavLink item={item} pathname={pathname} onClick={close} /></li>)}
          </ul>
          <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Research</p>
          <ul>
            {RESEARCH_TOOLS.map((item) => <li key={item.href}><NavLink item={item} pathname={pathname} onClick={close} from={pathname.startsWith('/chart') ? pathname : undefined} /></li>)}
          </ul>
          <ul className="mt-1 pt-1 border-t border-[var(--ws-line)]">
            {HELP_ROUTES.map((item) => <li key={item.href}><NavLink item={item} pathname={pathname} onClick={close} /></li>)}
          </ul>
          <div className="mt-1 pt-2 px-3 pb-1 border-t border-[var(--ws-line)] flex items-center justify-between gap-2">
            <span className="text-xs text-slate-500">Theme</span>
            <ThemeToggle />
          </div>
          <button type="button" onClick={() => { close(); onShortcuts(); }} className={`w-full text-left px-3 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-[var(--ws-muted)] ${focusRing}`}>
            Keyboard shortcuts <span className="text-slate-500">?</span>
          </button>
          <p className="px-3 pt-1 pb-2 text-[11px] text-slate-500">
            Charts by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="underline">TradingView Lightweight Charts™</a>
          </p>
        </>
      )}
    </Popover>
  );
}

/** Phone navigation: the bottom bar and its "More" sheet, below `lg` on every route. */
export function PhoneNav() {
  const { pathname } = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);

  // A route change should never leave a sheet open over the new page.
  useEffect(() => setMoreOpen(false), [pathname]);

  const moreActive = RESEARCH_TOOLS.some(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`)
  );

  return (
    <>
      {/* It overlays the page instead of pushing it, so the content never
          reflows when navigation opens. */}
      <nav
        aria-label="Primary"
        className="lg:hidden fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-950/95 backdrop-blur-md pb-[env(safe-area-inset-bottom)]"
      >
        <ul className="flex items-stretch">
          {MOBILE_PRIMARY.map((item) => {
            const isActive =
              pathname === item.href || (item.href !== '/' && pathname.startsWith(`${item.href}/`));
            return (
              <li key={item.href} className="flex-1">
                <Link
                  to={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  className={`flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium ${focusRing} ${
                    isActive
                      ? 'text-indigo-600 dark:text-indigo-300'
                      : 'text-slate-500 dark:text-slate-400'
                  }`}
                >
                  {item.icon}
                  {item.label}
                </Link>
              </li>
            );
          })}
          <li className="flex-1">
            <button
              type="button"
              onClick={() => setMoreOpen(true)}
              aria-haspopup="dialog"
              aria-expanded={moreOpen}
              className={`w-full flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium ${focusRing} ${
                moreActive ? 'text-indigo-600 dark:text-indigo-300' : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              {Icons.menu}
              More
            </button>
          </li>
        </ul>
      </nav>

      {moreOpen && (
        <MobileSheet title="More" onClose={() => setMoreOpen(false)}>
          <div className="space-y-1">
            {NAV_ITEMS.slice(3).map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} onClick={() => setMoreOpen(false)} />
            ))}
          </div>
          <div className="pt-2 mt-2 border-t border-slate-200 dark:border-slate-800 space-y-1">
            <div className="px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-600">
              Research
            </div>
            {RESEARCH_TOOLS.map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} onClick={() => setMoreOpen(false)} />
            ))}
          </div>
          <div className="pt-2 mt-2 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between px-3">
            <span className="text-xs text-slate-500">Theme</span>
            <ThemeToggle />
          </div>
        </MobileSheet>
      )}
    </>
  );
}
