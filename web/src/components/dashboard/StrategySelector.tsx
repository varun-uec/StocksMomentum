import { useQuery } from '@tanstack/react-query';
import { listStrategies } from '@/lib/api-client';
import { useStrategy } from '@/app/strategy-context';
import { focusRing } from '@/lib/theme';
import { strategyDisplayName } from '@/lib/format';

/** Pick a current predefined or saved config, including strategies without a run. */
export function StrategySelector() {
  const { strategyName, strategyHash, setStrategyName } = useStrategy();
  const { data: strategies, isLoading } = useQuery({
    queryKey: ['strategies', 'workspace'],
    queryFn: () => listStrategies(false, true),
    staleTime: 30_000,
  });
  const { data: completed } = useQuery({
    queryKey: ['strategies', 'workspace', 'with-runs'],
    queryFn: () => listStrategies(true, true),
    staleTime: 30_000,
  });

  const selected = strategies?.find((s) => s.config_hash === strategyHash)
    ?? strategies?.find((s) => s.name === strategyName)
    ?? strategies?.[0];

  if (isLoading || !strategies || strategies.length === 0 || !selected) return null;
  const completedHashes = new Set((completed ?? []).map((s) => s.config_hash));

  return (
    <div className="flex flex-wrap lg:flex-nowrap items-center gap-x-1.5 gap-y-0.5">
      <label htmlFor="strategy-selector" className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
        Strategy
      </label>
      <select
        id="strategy-selector"
        value={selected.config_hash}
        disabled={strategies.length === 1}
        aria-describedby="strategy-selector-note"
        title={selected.description ?? undefined}
        onChange={(e) => {
          const next = strategies.find((s) => s.config_hash === e.target.value);
          if (next) setStrategyName(next.name, next.config_hash);
        }}
        className={`rounded-lg border border-slate-200 dark:border-slate-700/60 bg-slate-100 dark:bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200 disabled:opacity-70 disabled:cursor-not-allowed ${focusRing}`}
      >
        {strategies.map((s) => (
          <option key={s.config_hash} value={s.config_hash}>
            {strategyDisplayName(s.name)}{s.kind === 'user' ? ` · v${s.version}` : ''}{completedHashes.has(s.config_hash) ? '' : ' · no run'}
          </option>
        ))}
      </select>
      <span id="strategy-selector-note" className="text-[11px] text-slate-600 dark:text-slate-400 lg:whitespace-nowrap">
        Select a strategy to view its run, or run screening when none exists.
      </span>
    </div>
  );
}
