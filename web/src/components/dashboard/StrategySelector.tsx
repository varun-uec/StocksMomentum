'use client';

import { useEffect } from 'react';
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

  useEffect(() => {
    // A stale localStorage selection (e.g. a removed strategy) would otherwise
    // render a permanently empty dashboard. Fall back to the first option.
    if (strategies && strategies.length > 0 && !strategies.some((s) => s.name === strategyName)) {
      setStrategyName(strategies[0].name);
    }
  }, [strategies, strategyName, setStrategyName]);

  const singleOption = !!strategies && strategies.length === 1;
  const { data: allStrategies } = useQuery({
    queryKey: ['strategies', 'all'],
    queryFn: () => listStrategies(false),
    staleTime: 5 * 60_000,
    enabled: singleOption,
  });

  if (isLoading || !strategies || strategies.length === 0) {
    return null;
  }

  const selected = strategies.some((s) => s.name === strategyName)
    ? strategyName
    : strategies[0].name;

  return (
    <div className="flex flex-col gap-0.5">
      <label
        htmlFor="strategy-selector"
        className="text-[11px] font-medium text-slate-500 dark:text-slate-400"
      >
        Strategy
      </label>
      <select
        id="strategy-selector"
        value={selected}
        disabled={singleOption}
        title={strategies.find((s) => s.name === selected)?.description ?? undefined}
        onChange={(e) => setStrategyName(e.target.value)}
        className={`rounded-lg border border-slate-200 dark:border-slate-700/60 bg-slate-100 dark:bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200 disabled:opacity-70 disabled:cursor-not-allowed ${focusRing}`}
      >
        {strategies.map((s) => (
          <option key={s.name} value={s.name}>
            {strategyDisplayName(s.name)}
          </option>
        ))}
      </select>
      {singleOption && (
        <span className="text-[11px] text-slate-400 dark:text-slate-500">
          {allStrategies
            ? `1 of ${allStrategies.length} strategies has a completed run`
            : 'Only one strategy has a completed run'}
        </span>
      )}
    </div>
  );
}
