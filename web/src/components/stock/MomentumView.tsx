'use client';

/**
 * Phase 6.3 — Momentum view: the Trend Template checklist plus per-engine
 * sub-scores, both from the *live* explanation
 * (`explanation.rule_explanations` filtered to `engine_name === 'trend_template'`,
 * and `explanation.engine_explanations`).
 */

import { Card, StatusDot } from '@/components/shared/Card';
import type { StockExplanation } from '@/lib/types';
import { num } from '@/lib/format';

export function MomentumView({ explanation }: { explanation: StockExplanation }) {
  const trendRules = explanation.rule_explanations.filter(
    (r) => r.engine_name === 'trend_template'
  );
  const passed = trendRules.filter((r) => r.passed).length;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card
        title="Trend Template checklist"
        subtitle={`${passed}/${trendRules.length} conditions met`}
      >
        <div className="space-y-2">
          {trendRules.map((rule) => (
            <div key={rule.rule_id} className="flex items-start gap-2 text-xs">
              <span
                className={
                  rule.passed
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-rose-600 dark:text-rose-400'
                }
                aria-hidden
              >
                {rule.passed ? '✓' : '✗'}
              </span>
              <span className="sr-only">{rule.passed ? 'Met' : 'Not met'}</span>
              <span className="text-slate-700 dark:text-slate-300">{rule.explanation}</span>
            </div>
          ))}
          {trendRules.length === 0 && (
            <p className="text-xs text-slate-500 italic">Not evaluated for this stock.</p>
          )}
        </div>
      </Card>

      <Card title="Engine sub-scores" subtitle="Score and weighted contribution per engine">
        <div className="space-y-1.5">
          {explanation.engine_explanations.map((engine) => (
            <div
              key={engine.engine_name}
              className="flex items-center justify-between gap-3 px-2 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-900/40"
            >
              <div className="flex items-center gap-2 min-w-0">
                <StatusDot passed={engine.passed} />
                <span className="text-xs text-slate-700 dark:text-slate-300 capitalize truncate">
                  {engine.engine_name.replace(/_/g, ' ')}
                </span>
              </div>
              <div className="text-xs tabular-nums text-slate-600 dark:text-slate-400 shrink-0">
                score {num(engine.score)} · contribution {num(engine.contribution)}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
