'use client';

import type { EngineExplanation } from '@/lib/types';
import { chartPalette } from '@/lib/theme';

/** Horizontal bars showing each engine's score (0-1 scale, shown as %) at a glance. */
export function EngineContributionBars({ engines }: { engines: EngineExplanation[] }) {
  return (
    <div className="space-y-2.5">
      {engines.map((engine) => {
        const score = Math.max(0, Math.min(1, parseFloat(engine.score)));
        const pct = Math.round(score * 100);
        const color = engine.passed ? chartPalette.success : chartPalette.warning;
        return (
          <div key={engine.engine_name} className="flex items-center gap-3">
            <div className="w-28 sm:w-36 shrink-0 text-xs text-slate-600 dark:text-slate-400 capitalize truncate">
              {engine.engine_name.replace(/_/g, ' ')}
            </div>
            <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, backgroundColor: color }}
              />
            </div>
            <div className="w-10 shrink-0 text-xs text-right tabular-nums text-slate-500 dark:text-slate-400">
              {pct}%
            </div>
          </div>
        );
      })}
    </div>
  );
}
