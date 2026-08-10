'use client';

/**
 * The strategy rail: which preset is active, what its rules currently say, and
 * every bar where one of them fired.
 *
 * The score is a view over the displayed bars. It is not stored, not part of
 * the composite score, and not part of the ranking.
 */

import { PRESETS, type RuleState, type Signal } from '@/lib/strategies';
import { focusRing } from '@/lib/theme';

const DIRECTION_STYLE: Record<Signal['direction'], string> = {
  long: 'text-emerald-600 dark:text-emerald-400',
  short: 'text-rose-600 dark:text-rose-400',
  exit: 'text-amber-600 dark:text-amber-400',
};

export function StrategyPanel({
  presetId,
  edited,
  onPresetChange,
  score,
  rules,
  signals,
  showSignals,
  onShowSignalsChange,
  onSignalClick,
}: {
  presetId: string;
  edited: boolean;
  onPresetChange: (id: string) => void;
  score: number;
  rules: RuleState[];
  /** Oldest first, as the rules print them. */
  signals: Signal[];
  showSignals: boolean;
  onShowSignalsChange: (on: boolean) => void;
  onSignalClick: (signal: Signal) => void;
}) {
  const preset = PRESETS.find((p) => p.id === presetId) ?? PRESETS[0];
  const newestFirst = [...signals].reverse();

  return (
    <div className="space-y-4">
      <div>
        <select
          value={presetId}
          onChange={(e) => onPresetChange(e.target.value)}
          className={`w-full px-2 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm ${focusRing}`}
        >
          {PRESETS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
        <p className="text-[11px] text-slate-500 mt-1">
          {preset.description}
          {edited && <span className="text-amber-600 dark:text-amber-400"> · edited</span>}
        </p>
      </div>

      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500">
          Signal score · {preset.label}
        </div>
        <div className="text-2xl font-semibold tabular-nums text-slate-800 dark:text-slate-200">
          {score}
          <span className="text-sm text-slate-400"> / 100</span>
        </div>
        <p className="text-[11px] text-slate-500">
          50 is neutral. Each rule moves it by its direction, weighted by how many sessions ago it
          last fired, over a 60-session window. Computed in this browser from the bars on screen.
        </p>
      </div>

      <ul className="space-y-1">
        {rules.map((rule) => (
          <li key={rule.ruleId} className="text-[11px]">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-slate-600 dark:text-slate-400">{rule.label}</span>
              <span className="tabular-nums text-slate-500">
                {rule.contribution >= 0 ? '+' : ''}
                {rule.contribution.toFixed(1)}
              </span>
            </div>
            <div className="text-[10px] text-slate-400 dark:text-slate-500">
              {rule.latest
                ? `${rule.latest.direction} · ${rule.latest.date} · ${rule.ageBars} sessions ago`
                : 'never fired in the loaded range'}
            </div>
          </li>
        ))}
      </ul>

      <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 cursor-pointer">
        <input
          type="checkbox"
          checked={showSignals}
          onChange={(e) => onShowSignalsChange(e.target.checked)}
          className="w-3 h-3 accent-indigo-500"
        />
        Mark signals on the chart
      </label>

      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
          Signal log · {signals.length}
        </div>
        {newestFirst.length === 0 && (
          <p className="text-xs text-slate-500">No rule fired inside the loaded range.</p>
        )}
        <ul className="max-h-72 overflow-y-auto space-y-0.5 pr-1">
          {newestFirst.map((signal) => (
            <li key={`${signal.ruleId}-${signal.date}-${signal.direction}`}>
              <button
                type="button"
                onClick={() => onSignalClick(signal)}
                className={`w-full text-left px-2 py-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
              >
                <div className="flex items-baseline gap-2 text-[11px]">
                  <span className={`font-semibold uppercase ${DIRECTION_STYLE[signal.direction]}`}>
                    {signal.direction}
                  </span>
                  <span className="text-slate-700 dark:text-slate-300">{signal.label}</span>
                  <span className="ml-auto tabular-nums text-slate-500">{signal.date}</span>
                </div>
                <div className="text-[10px] text-slate-500">{signal.detail}</div>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
