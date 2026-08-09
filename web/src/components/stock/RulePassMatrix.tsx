'use client';

import type { RuleExplanation } from '@/lib/types';

/**
 * A compact heatmap-style grid of every evaluated rule, grouped by engine, so
 * the full pass/fail picture can be scanned in under a second instead of
 * reading a long list top to bottom.
 */
export function RulePassMatrix({
  rules,
  gateFailures = [],
}: {
  rules: RuleExplanation[];
  /** Rule ids that failed a hard gate — flagged so a blocking failure is not
   *  visually indistinguishable from an ordinary scoring miss. */
  gateFailures?: string[];
}) {
  const gate = new Set(gateFailures);
  const byEngine = new Map<string, RuleExplanation[]>();
  for (const rule of rules) {
    const list = byEngine.get(rule.engine_name) ?? [];
    list.push(rule);
    byEngine.set(rule.engine_name, list);
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-4 text-xs text-slate-400 dark:text-slate-500 pb-1">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-emerald-500 dark:bg-emerald-400" /> passed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-rose-300 dark:bg-rose-900/70" /> failed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-rose-300 dark:bg-rose-900/70 ring-2 ring-rose-500" /> blocks
          qualification
        </span>
      </div>
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
                  aria-label={`${rule.rule_id}: ${rule.passed ? 'passed' : 'failed'}${
                    gate.has(rule.rule_id) ? ', blocks qualification' : ''
                  }`}
                  title={`${rule.rule_id}: ${rule.passed ? 'passed' : 'failed'}${
                    gate.has(rule.rule_id) ? ' (blocks qualification)' : ''
                  } — ${rule.explanation}`}
                  className={`w-4 h-4 rounded-sm ${
                    rule.passed
                      ? 'bg-emerald-500 dark:bg-emerald-400'
                      : 'bg-rose-300 dark:bg-rose-900/70'
                  } ${gate.has(rule.rule_id) ? 'ring-2 ring-rose-500' : ''}`}
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
