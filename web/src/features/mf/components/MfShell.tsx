/**
 * The MF workstation shell (ui-ux doc 01): a left rail on desktop, a top bar with
 * fund search, and a bottom bar plus "More" sheet on phones. It mounts none of the
 * stock workstation's chrome. The palette comes from theme/themes.ts; light and
 * dark follow the app-wide theme setting.
 */
import { useEffect, useId, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router';
import { useTheme, type ThemeMode } from '@/app/theme-provider';
import { DEFAULT_THEME, THEMES, themeCss, type ThemeId } from '../theme/themes';
import { useScreenRevisions } from '../queries';
import { useCompareTray } from '../workspace';
import { CompareTray } from './CompareTray';
import { FundSearch } from './FundSearch';
import { I } from './icons';
import { Badge, Button, Segmented, Sheet, cx } from './ui';

const PALETTE_KEY = 'mf-palette';

function usePalette(): [ThemeId, (id: ThemeId) => void] {
  const [id, setId] = useState<ThemeId>(() => {
    try {
      const stored = localStorage.getItem(PALETTE_KEY);
      return stored && stored in THEMES ? (stored as ThemeId) : DEFAULT_THEME;
    } catch {
      return DEFAULT_THEME;
    }
  });
  const set = (next: ThemeId) => {
    setId(next);
    try {
      localStorage.setItem(PALETTE_KEY, next);
    } catch {
      // A blocked store keeps the choice for this visit only.
    }
  };
  return [id, set];
}

interface NavItem {
  to: string;
  label: string;
  icon: (p: { className?: string }) => ReactNode;
  planned?: boolean;
  end?: boolean;
}

const PRIMARY: NavItem[] = [
  { to: '/mf', label: 'Discover', icon: I.discover, end: true },
  { to: '/mf/screen', label: 'Screener', icon: I.screen },
  { to: '/mf/studio', label: 'Analytics studio', icon: I.studio },
  { to: '/mf/compare', label: 'Compare', icon: I.compare },
  { to: '/mf/simulate', label: 'Investment lab', icon: I.lab },
  { to: '/mf/portfolio', label: 'Portfolio', icon: I.portfolio },
  { to: '/mf/ask', label: 'AI research', icon: I.ask, planned: true },
];

const SPACE: NavItem[] = [
  { to: '/mf/workspace?tab=watchlists', label: 'Watchlists', icon: I.star },
  { to: '/mf/workspace?tab=screens', label: 'Saved screens', icon: I.bookmark },
  { to: '/mf/workspace?tab=notes', label: 'Research notes', icon: I.note },
  { to: '/mf/workspace?tab=alerts', label: 'Alerts', icon: I.bell },
];

function RailLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const { pathname, search } = useLocation();
  const [path, query] = item.to.split('?');
  const active = query ? pathname === path && search.includes(query) : undefined;
  const className = (isActive: boolean) =>
    cx(
      'flex h-10 items-center gap-3 rounded-[10px] px-3 text-sm transition-colors duration-150',
      isActive ? 'bg-mf-brand-soft font-semibold text-mf-brand-strong shadow-[inset_3px_0_0_rgb(var(--mf-brand))]' : 'text-mf-ink-soft hover:bg-mf-sunken hover:text-mf-ink',
    );
  const body = (
    <>
      <item.icon />
      <span className="flex-1 truncate">{item.label}</span>
      {item.planned && <Badge tone="planned">Planned</Badge>}
    </>
  );
  if (query)
    return (
      <Link to={item.to} onClick={onNavigate} aria-current={active ? 'page' : undefined} className={className(!!active)}>
        {body}
      </Link>
    );
  return (
    <NavLink to={item.to} end={item.end} onClick={onNavigate} className={({ isActive }) => className(isActive)}>
      {body}
    </NavLink>
  );
}

function Wordmark() {
  // Unique per copy: a gradient defined inside a hidden copy would not paint the other.
  const gradient = useId();
  return (
    <Link to="/mf" className="flex items-center gap-2 rounded-[8px] px-1" aria-label="Wickstreet mutual funds, home">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden="true">
        <defs>
          <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="rgb(var(--mf-brand-alt))" />
            <stop offset="1" stopColor="rgb(var(--mf-brand-strong))" />
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="9" fill={`url(#${gradient})`} />
        <path d="M7 10l3.6 12L14 13l2 6 2-6 3.4 9L25 10" fill="none" className="stroke-mf-on-brand" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="25" cy="10" r="2.6" className="fill-mf-accent" />
      </svg>
      <span className="font-display text-[21px] leading-none text-mf-ink">Wickstreet</span>
    </Link>
  );
}

function AppearanceSettings({ palette, setPalette }: { palette: ThemeId; setPalette: (id: ThemeId) => void }) {
  const { mode, setMode } = useTheme();
  return (
    <div className="space-y-6">
      <div>
        <p className="mb-2 text-sm font-medium">Light or dark</p>
        <Segmented<ThemeMode>
          label="Light or dark"
          size="md"
          value={mode}
          onChange={setMode}
          options={[
            { value: 'light', label: 'Light' },
            { value: 'dark', label: 'Dark' },
            { value: 'system', label: 'System' },
          ]}
        />
      </div>
      <fieldset>
        <legend className="mb-2 text-sm font-medium">Colour theme</legend>
        <div className="grid gap-2">
          {(Object.keys(THEMES) as ThemeId[]).map((id) => (
            <label key={id} className={cx('flex cursor-pointer items-center gap-3 rounded-[12px] border p-3', palette === id ? 'border-mf-brand bg-mf-brand-soft' : 'border-mf-line')}>
              <input type="radio" name="mf-palette" checked={palette === id} onChange={() => setPalette(id)} />
              <span className="flex gap-1" aria-hidden="true">
                {(['brand', 'brandAlt', 'paper', 'loss'] as const).map((role) => (
                  <span key={role} className="h-5 w-5 rounded-full border border-mf-line-strong" style={{ background: THEMES[id].light[role] }} />
                ))}
              </span>
              <span className="text-sm">{THEMES[id].label}</span>
            </label>
          ))}
        </div>
        <p className="mt-2 text-xs text-mf-muted">Your choice is kept in this browser.</p>
      </fieldset>
    </div>
  );
}

const PHONE: NavItem[] = [
  { to: '/mf', label: 'Discover', icon: I.discover, end: true },
  { to: '/mf/screen', label: 'Screener', icon: I.screen },
  { to: '/mf/compare', label: 'Compare', icon: I.compare },
  { to: '/mf/workspace', label: 'My space', icon: I.star },
];

/** True while the page scrolls down past the first screen; false on any upward scroll or near the top. */
function useHideOnScrollDown(): boolean {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      if (Math.abs(y - last) < 8) return;
      setHidden(y > last && y > 120);
      last = y;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  return hidden;
}

export function MfShell({ children }: { children: ReactNode }) {
  const [palette, setPalette] = usePalette();
  const { resolvedTheme, setMode } = useTheme();
  const [settings, setSettings] = useState(false);
  const [more, setMore] = useState(false);
  const [phoneSearch, setPhoneSearch] = useState(false);
  const { pathname } = useLocation();
  const picked = useCompareTray().funds.length;
  const navHidden = useHideOnScrollDown();

  // ScrollRestoration owns the scroll position, so Back returns to the same row.
  useEffect(() => {
    setMore(false);
    setPhoneSearch(false);
  }, [pathname]);

  return (
    <div className="mf-root">
      <style>{themeCss(THEMES[palette])}</style>
      <a href="#mf-main" className="sr-only z-[100] rounded bg-mf-surface px-3 py-2 focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
        Skip to content
      </a>

      {/* Desktop rail */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[232px] flex-col border-r border-mf-line bg-mf-surface/70 px-3 py-4 backdrop-blur lg:flex">
        <div className="px-2 pb-5">
          <Wordmark />
        </div>
        <nav aria-label="Mutual fund research" className="mf-scroll flex-1 overflow-y-auto">
          <ul className="space-y-0.5">
            {PRIMARY.map((item) => (
              <li key={item.to}>
                <RailLink item={item} />
              </li>
            ))}
          </ul>
          <p className="mt-6 px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-mf-muted">Your space</p>
          <ul className="space-y-0.5">
            {SPACE.map((item) => (
              <li key={item.to}>
                <RailLink item={item} />
              </li>
            ))}
          </ul>
        </nav>
        <div className="space-y-0.5 border-t border-mf-line pt-3">
          <Link to="/" className="flex h-10 items-center gap-3 rounded-[10px] px-3 text-sm text-mf-ink-soft hover:bg-mf-sunken">
            <I.stocks />
            Momentum25 · Stocks
          </Link>
          <button type="button" onClick={() => setSettings(true)} className="flex h-10 w-full items-center gap-3 rounded-[10px] px-3 text-sm text-mf-ink-soft hover:bg-mf-sunken">
            <I.settings />
            Appearance
          </button>
        </div>
      </aside>

      <div className="lg:pl-[232px]">
        {/* Top bar */}
        <header className="sticky top-0 z-20 border-b border-mf-line bg-mf-paper/85 backdrop-blur">
          <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-3 px-4 sm:px-6 lg:px-8">
            <div className="lg:hidden">
              <Wordmark />
            </div>
            <FundSearch shortcut className="hidden max-w-xl flex-1 sm:block" placeholder="Search funds, AMFI codes or ISINs" />
            <div className="ml-auto flex items-center gap-1">
              <button type="button" onClick={() => setPhoneSearch(true)} aria-label="Search funds" className="grid h-11 w-11 place-items-center rounded-full text-mf-ink-soft hover:bg-mf-sunken sm:hidden">
                <I.search />
              </button>
              <button
                type="button"
                onClick={() => setMode(resolvedTheme === 'dark' ? 'light' : 'dark')}
                aria-label={resolvedTheme === 'dark' ? 'Use light theme' : 'Use dark theme'}
                className="grid h-11 w-11 place-items-center rounded-full text-mf-ink-soft hover:bg-mf-sunken"
              >
                {resolvedTheme === 'dark' ? <I.sun /> : <I.moon />}
              </button>
              <button type="button" onClick={() => setSettings(true)} aria-label="Appearance settings" className="grid h-11 w-11 place-items-center rounded-full text-mf-ink-soft hover:bg-mf-sunken lg:hidden">
                <I.settings />
              </button>
            </div>
          </div>
        </header>

        <main id="mf-main" tabIndex={-1} className="mf-main mx-auto max-w-[1440px] px-4 pb-6 pt-3 outline-none sm:px-6 sm:pt-6 lg:px-8 lg:pb-28 lg:pt-8">
          <MixedSnapshots />
          {children}
        </main>
      </div>

      <CompareTray />

      {/* Phone navigation: it slides away while the reader scrolls down, so it never covers a chart for long. */}
      <nav aria-label="Mutual fund research" className={cx('fixed inset-x-0 bottom-0 z-30 border-t border-mf-line bg-mf-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur transition-transform duration-200 focus-within:translate-y-0 motion-reduce:transition-none lg:hidden', navHidden && 'translate-y-full')}>
        <ul className="flex">
          {PHONE.map((item) => (
            <li key={item.to} className="flex-1">
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) => cx('flex h-16 flex-col items-center justify-center gap-1 text-[11px]', isActive ? 'font-medium text-mf-brand-strong' : 'text-mf-muted')}
              >
                <span className="relative">
                  <item.icon className="h-5 w-5" />
                  {/* On phones the compare selection lives here, not in a tray over the page. */}
                  {item.to === '/mf/compare' && picked > 0 && (
                    <span className="absolute -right-2.5 -top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-mf-brand px-1 text-[10px] font-semibold leading-none text-mf-on-brand">
                      {picked}
                      <span className="sr-only"> funds picked</span>
                    </span>
                  )}
                </span>
                {item.label}
              </NavLink>
            </li>
          ))}
          <li className="flex-1">
            <button type="button" onClick={() => setMore(true)} aria-expanded={more} className="flex h-16 w-full flex-col items-center justify-center gap-1 text-[11px] text-mf-muted">
              <I.more className="h-5 w-5" />
              More
            </button>
          </li>
        </ul>
      </nav>

      <Sheet open={more} onClose={() => setMore(false)} title="More">
        <ul className="space-y-0.5">
          {[...PRIMARY.filter((i) => !PHONE.some((p) => p.to === i.to)), ...SPACE].map((item) => (
            <li key={item.to}>
              <RailLink item={item} onNavigate={() => setMore(false)} />
            </li>
          ))}
          <li>
            <Link to="/" className="flex h-10 items-center gap-3 rounded-[10px] px-3 text-sm text-mf-ink-soft hover:bg-mf-sunken">
              <I.stocks />
              Momentum25 · Stocks
            </Link>
          </li>
        </ul>
      </Sheet>
      <Sheet open={phoneSearch} onClose={() => setPhoneSearch(false)} title="Search funds" side="center">
        <FundSearch autoFocus />
        <p className="mt-3 text-xs text-mf-muted">Type at least two letters of a name, an AMFI code or an ISIN.</p>
      </Sheet>
      <Sheet open={settings} onClose={() => setSettings(false)} title="Appearance">
        <AppearanceSettings palette={palette} setPalette={setPalette} />
      </Sheet>
    </div>
  );
}

/** A warning when this page's sections came from different daily snapshots (audit A-15). */
function MixedSnapshots() {
  const { revisions, refresh } = useScreenRevisions();
  if (revisions.length < 2) return null;
  return (
    <div role="alert" className="mb-5 flex flex-wrap items-center gap-3 rounded-[12px] border border-mf-warning/40 bg-mf-warning-soft px-4 py-3 text-sm text-mf-ink">
      <I.info className="h-4 w-4 shrink-0 text-mf-warning" />
      <p className="min-w-0 flex-1">
        New data was published while this page loaded. Its sections mix snapshots {revisions.join(' and ')}, so figures may not agree. Refresh to put every section on snapshot {revisions[revisions.length - 1]}.
      </p>
      <Button size="sm" variant="primary" onClick={refresh}>
        Refresh every section
      </Button>
    </div>
  );
}
