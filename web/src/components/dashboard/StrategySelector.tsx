'use client';

import { useQuery } from '@tanstack/react-query';
import { listStrategies } from '@/lib/api-client';
import { useStrategy } from '@/app/strategy-context';
import { focusRing } from '@/lib/theme';
import { strategyDisplayName } from '@/lib/format';

/**
 * The strategy selector — the one control that decides which stocks the
 * dashboard shows. Only lists strategies with a completed live run, so every
 * option is guaranteed to render real stocks rather than an empty page.
 */
export function StrategySelector() {
  const { strategyName, setStrategyName } = useStrategy();
  const { data: strategies, isLoading } = useQuery({
    queryKey: ['strategies', 'with-runs'],
    queryFn: () => listStrategies(true),
    staleTime: 5 * 60_000,
  });

  if (isLoading || !strategies || strategies.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-lg p-1">
      {strategies.map((s) => (
        <button
          key={s.name}
          type="button"
          title={s.description ?? undefined}
          onClick={() => setStrategyName(s.name)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${focusRing} ${
            strategyName === s.name
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700/60'
          }`}
        >
          {strategyDisplayName(s.name)}
        </button>
      ))}
    </div>
  );
}
