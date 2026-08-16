'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTheme, type ThemeMode } from '@/app/theme-provider';
import { searchSecurities } from '@/lib/api-client';
import { focusRing } from '@/lib/theme';
import type { SecuritySearchResult } from '@/lib/types';

// Minimal SVG icons — no emoji, consistent 20×20 viewBox.
const Icons = {
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
  { href: '/watchlist', label: 'Watchlist', icon: Icons.watchlist },
  { href: '/market', label: 'Market', icon: Icons.market },
  { href: '/learn', label: 'Learn', icon: Icons.learn },
  { href: '/data', label: 'Data', icon: Icons.data },
];

const RESEARCH_TOOLS = [
  { href: '/strategies', label: 'Strategies', icon: Icons.strategies },
  { href: '/validation', label: 'Validation', icon: Icons.research },
  { href: '/historical', label: 'Historical', icon: Icons.historical },
  { href: '/analytics', label: 'Analytics', icon: Icons.analytics },
  { href: '/experiment', label: 'Experiment Lab', icon: Icons.lab },
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
function SymbolSearch({ className = '', inputClassName = 'w-28 lg:w-44' }: { className?: string; inputClassName?: string }) {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [results, setResults] = useState<SecuritySearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [searching, setSearching] = useState(false);

  const query = value.trim();

  // Debounced so a fast typist issues one request per pause, not per keystroke;
  // the abort controller drops responses for queries the user has moved past,
  // which would otherwise land out of order and show stale suggestions.
  useEffect(() => {
    if (query.length < 1) {
      setResults([]);
      setSearching(false);
      return;
    }
    const controller = new AbortController();
    setSearching(true);
    const timer = setTimeout(() => {
      searchSecurities(query, 8, controller.signal)
        .then((r) => {
          setResults(r);
          setActive(-1);
        })
        .catch(() => {
          /* aborted or offline — leave the last suggestions in place */
        })
        .finally(() => setSearching(false));
    }, 150);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const go = (symbol: string) => {
    setValue('');
    setResults([]);
    setOpen(false);
    router.push(`/stock/${encodeURIComponent(symbol.toUpperCase())}`);
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

function NavLink({
  item,
  pathname,
  onClick,
}: {
  item: NavItem;
  pathname: string;
  onClick?: () => void;
}) {
  const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(`${item.href}/`));
  return (
    <Link
      key={item.href}
      href={item.href}
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

/** Roving-focus dropdown: Arrow/Home/End move, Escape closes and restores focus. */
function ResearchToolsMenu() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const isActive = RESEARCH_TOOLS.some(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`)
  );

  const close = useCallback((restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) buttonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    itemRefs.current[active]?.focus();
  }, [open, active]);

  const openAt = (index: number) => {
    setActive(index);
    setOpen(true);
  };

  const onMenuKeyDown = (e: React.KeyboardEvent) => {
    const last = RESEARCH_TOOLS.length - 1;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => (i >= last ? 0 : i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => (i <= 0 ? last : i - 1));
    } else if (e.key === 'Home') {
      e.preventDefault();
      setActive(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      setActive(last);
    } else if (e.key === 'Escape' || e.key === 'Tab') {
      close(e.key === 'Escape');
    }
  };

  return (
    <div className="relative" onBlur={(e) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false);
    }}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => (open ? close(false) : openAt(0))}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            openAt(0);
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            openAt(RESEARCH_TOOLS.length - 1);
          }
        }}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${focusRing} ${
          isActive
            ? 'bg-indigo-100 dark:bg-indigo-600/20 text-indigo-700 dark:text-indigo-300'
            : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800'
        }`}
      >
        Research
        <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`}>
          <path fillRule="evenodd" clipRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" />
        </svg>
      </button>
      {open && (
        <ul
          role="menu"
          aria-label="Research"
          onKeyDown={onMenuKeyDown}
          className="absolute left-0 mt-1 w-48 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg py-1 z-50"
        >
          {RESEARCH_TOOLS.map((item, i) => (
            <li key={item.href} role="none">
              <Link
                ref={(el) => {
                  itemRefs.current[i] = el;
                }}
                href={item.href}
                role="menuitem"
                tabIndex={i === active ? 0 : -1}
                aria-current={pathname === item.href ? 'page' : undefined}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-2 px-3 py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
              >
                <span className="text-slate-400 dark:text-slate-500">{item.icon}</span>
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
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
    <div className="md:hidden fixed inset-0 z-[60]">
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

export function NavBar() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  // A route change should never leave a sheet open over the new page.
  useEffect(() => {
    setMoreOpen(false);
    setSearchOpen(false);
  }, [pathname]);

  const moreActive = RESEARCH_TOOLS.some(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`)
  );

  return (
    <>
      <nav className="sticky top-0 z-50 border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-950/90 backdrop-blur-md transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-14 gap-1">
            {/* Brand */}
            <Link
              href="/"
              className="flex items-center gap-2 mr-4 text-sm font-bold tracking-tight text-slate-800 dark:text-slate-200 hover:text-slate-950 dark:hover:text-white transition-colors"
            >
              <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-indigo-600 text-white text-xs font-extrabold">
                M25
              </span>
              <span className="hidden sm:inline">Momentum25</span>
            </Link>

            {/* Desktop Nav */}
            <div className="hidden md:flex items-center gap-0.5">
              {NAV_ITEMS.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
              <ResearchToolsMenu />
            </div>

            <div className="flex-1" />

            <div className="flex items-center gap-3">
              <SymbolSearch className="hidden md:block" />
              <ThemeToggle />
              <span className="hidden sm:inline text-xs text-slate-400 dark:text-slate-600 font-medium">v0.2.0</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile bottom bar. It overlays the page instead of pushing it, so the
          content never reflows when navigation opens. */}
      <nav
        aria-label="Primary"
        className="md:hidden fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-950/95 backdrop-blur-md pb-[env(safe-area-inset-bottom)]"
      >
        <ul className="flex items-stretch">
          {MOBILE_PRIMARY.map((item) => {
            const isActive =
              pathname === item.href || (item.href !== '/' && pathname.startsWith(`${item.href}/`));
            return (
              <li key={item.href} className="flex-1">
                <Link
                  href={item.href}
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

      {/* Symbol search is the fastest route to any stock, so on mobile it gets
          its own always-visible button rather than hiding inside a drawer. */}
      <button
        type="button"
        onClick={() => setSearchOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={searchOpen}
        aria-label="Search for a symbol"
        className={`md:hidden fixed right-4 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-50 w-12 h-12 rounded-full bg-indigo-600 text-white shadow-lg flex items-center justify-center ${focusRing}`}
      >
        {Icons.search}
      </button>

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
        </MobileSheet>
      )}

      {searchOpen && (
        <MobileSheet title="Search" onClose={() => setSearchOpen(false)} className="min-h-[70vh]">
          <SymbolSearch className="w-full" inputClassName="w-full" />
        </MobileSheet>
      )}
    </>
  );
}
