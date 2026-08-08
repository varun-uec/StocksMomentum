'use client';

import type { RuleExplanation } from '@/lib/types';

/**
 * A compact heatmap-style grid of every evaluated rule, grouped by engine, so
 * the full pass/fail picture can be scanned in under a second instead of
 * reading a long list top to bottom.
 */
export function RulePassMatrix({ rules }: { rules: RuleExplanation[] }) {
  const byEngine = new Map<string, RuleExplanation[]>();
  for (const rule of rules) {
    const list = byEngine.get(rule.engine_name) ?? [];
    list.push(rule);
    byEngine.set(rule.engine_name, list);
  }

  return (
    <div className="space-y-2">
      {Array.from(byEngine.entries()).map(([engine, engineRules]) => {
        const passed = engineRules.filter((r) => r.passed).length;
        return (
          <div key={engine} className="flex items-center gap-2">
            <div className="w-28 sm:w-32 shrink-0 text-xs text-slate-500 dark:text-slate-400 capitalize truncate">
              {engine.replace(/_/g, ' ')}
            </div>
            <div className="flex gap-1 flex-wrap">
              {engineRules.map((rule) => (
                <div
                  key={rule.rule_id}
                  role="img"
                  aria-label={`${rule.rule_id}: ${rule.passed ? 'passed' : 'failed'}`}
                  title={`${rule.rule_id}: ${rule.passed ? 'passed' : 'failed'} — ${rule.explanation}`}
                  className={`w-4 h-4 rounded-sm ${
                    rule.passed
                      ? 'bg-emerald-500 dark:bg-emerald-400'
                      : 'bg-rose-300 dark:bg-rose-900/70'
                  }`}
                />
              ))}
            </div>
            <div className="ml-auto text-xs text-slate-400 dark:text-slate-500 tabular-nums">
              {passed}/{engineRules.length}
            </div>
          </div>
        );
      })}
    </div>
  );
}
