/**
 * The Research workspace (plan 2026-10-19, workflow 5): one area for strategy
 * research, with a left list of strategies and a tab row over the research
 * routes. Each tab keeps its own route and URL, so direct links still work;
 * the selected strategy and the `?from=` return path carry across tabs.
 */

import { Link, Outlet, useLocation, useSearchParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useStrategy } from '@/app/strategy-context';
import { listStrategies } from '@/lib/api-client';
import { strategyDisplayName } from '@/lib/format';
import { focusRing } from '@/lib/theme';

const TABS = [
  { label: 'Strategies', path: '/strategies' },
  { label: 'Studio', path: '/studio' },
  { label: 'Backtest', path: '/backtest' },
  { label: 'Experiment', path: '/experiment' },
  { label: 'Validation', path: '/validation' },
  { label: 'Historical', path: '/historical' },
  { label: 'Analytics', path: '/analytics' },
];

export default function ResearchLayout() {
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const { strategyName, setStrategyName } = useStrategy();
  const { data: strategies } = useQuery({ queryKey: ['strategies', 'with-runs'], queryFn: () => listStrategies(true), staleTime: 5 * 60_000 });
  // Only the return path travels between tabs; each tab's own parameters stay with it.
  const from = params.get('from');
  const tabHref = (path: string) => (from ? `${path}?from=${encodeURIComponent(from)}` : path);

  return (
    <div className="lg:grid lg:grid-cols-[13rem_minmax(0,1fr)] min-h-full">
      <nav aria-label="Research strategies" className="hidden lg:block border-r border-[var(--ws-line)] bg-white dark:bg-slate-900 py-3">
        <h2 className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Strategies</h2>
        <ul>
          {strategies?.map((s) => (
            <li key={s.name}>
              <button
                type="button"
                aria-pressed={s.name === strategyName}
                onClick={() => setStrategyName(s.name)}
                className={`w-full text-left px-3 py-1.5 text-xs ${focusRing} ${s.name === strategyName ? 'bg-[var(--ws-muted)] font-semibold text-[var(--ws-ink)]' : 'text-slate-600 dark:text-slate-300 hover:bg-[var(--ws-muted)]'}`}
              >
                {strategyDisplayName(s.name)}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <div className="min-w-0">
        <nav aria-label="Research" className="flex items-center gap-1 px-4 sm:px-6 border-b border-[var(--ws-line)] bg-white dark:bg-slate-900 overflow-x-auto">
          {TABS.map((tab) => (
            <Link
              key={tab.path}
              to={tabHref(tab.path)}
              aria-current={pathname === tab.path ? 'page' : undefined}
              className={`px-3 py-2 text-sm font-medium border-b-2 whitespace-nowrap ${focusRing} ${pathname === tab.path ? 'border-[var(--ws-accent)] text-[var(--ws-ink)]' : 'border-transparent text-slate-500 hover:text-[var(--ws-ink)]'}`}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
        <Outlet />
      </div>
    </div>
  );
}
