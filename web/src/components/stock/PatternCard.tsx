'use client';

/**
 * Phase 6.6 — pattern recognition.
 *
 * Bound to live `rule_explanations` where `engine_name` is `'pattern'` or
 * `'breakout'`. Status = `passed`, quality = `contribution`, description =
 * the backend `explanation` string. There is no pattern-type enum or
 * geometric detection output in this system, so no diagram is drawn — that
 * would imply detection the platform does not perform.
 */

import { Card, StatusDot } from '@/components/shared/Card';
import type { RuleExplanation, StockExplanation } from '@/lib/types';

function PatternRow({ rule }: { rule: RuleExplanation }) {
  const quality = parseFloat(rule.contribution);
  const pct = Number.isFinite(quality) ? Math.max(0, Math.min(1, quality)) * 100 : 0;
  return (
    <div className="px-2 py-2 rounded-lg bg-slate-50 dark:bg-slate-900/40">
      <div className="flex items-center gap-2 text-xs">
        <StatusDot passed={rule.passed} />
        <span className="flex-1 text-slate-700 dark:text-slate-300">{rule.explanation}</span>
        <span className="shrink-0 tabular-nums text-slate-500">{rule.contribution}</span>
      </div>
      <div className="mt-1.5 h-1 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
        <div
          className={rule.passed ? 'h-full bg-emerald-500' : 'h-full bg-slate-400'}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function PatternCard({ explanation }: { explanation: StockExplanation }) {
  const patternRules = explanation.rule_explanations.filter((r) => r.engine_name === 'pattern');
  const breakoutRules = explanation.rule_explanations.filter((r) => r.engine_name === 'breakout');

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Pattern recognition" subtitle="Bar shading shows each rule's weighted contribution">
        <div className="space-y-2">
          {patternRules.map((rule) => (
            <PatternRow key={rule.rule_id} rule={rule} />
          ))}
          {patternRules.length === 0 && (
            <p className="text-xs text-slate-500 italic">Not evaluated for this stock.</p>
          )}
        </div>
      </Card>
      <Card title="Breakout readiness">
        <div className="space-y-2">
          {breakoutRules.map((rule) => (
            <PatternRow key={rule.rule_id} rule={rule} />
          ))}
          {breakoutRules.length === 0 && (
            <p className="text-xs text-slate-500 italic">Not evaluated for this stock.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
