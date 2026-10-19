/**
 * Phase 6.7 — "why this stock ranks" / "what could invalidate it".
 *
 * Both lists are `explanation.rule_explanations` sorted by `contribution`:
 * top passing contributors on the left, failing rules (gate failures first)
 * on the right. No new backend data.
 */

import { Badge, Card, StatusDot } from '@/components/shared/Card';
import type { RuleExplanation, StockExplanation } from '@/lib/types';
import { focusRing } from '@/lib/theme';
import { num } from '@/lib/format';

/** Top passing rules by contribution, and failing rules with gate failures first. */
export function rankReasons(explanation: StockExplanation, count = 5) {
  const contributors = explanation.rule_explanations
    .filter((r) => r.passed)
    .slice()
    .sort((a, b) => parseFloat(b.contribution) - parseFloat(a.contribution))
    .slice(0, count);

  const detractors = explanation.rule_explanations
    .filter((r) => !r.passed)
    .slice()
    .sort((a, b) => {
      const aGate = explanation.hard_filter_failures.includes(a.rule_id) ? 1 : 0;
      const bGate = explanation.hard_filter_failures.includes(b.rule_id) ? 1 : 0;
      if (aGate !== bGate) return bGate - aGate;
      return parseFloat(b.contribution) - parseFloat(a.contribution);
    })
    .slice(0, count);
  return { contributors, detractors };
}

/** A reason's text, linked to its evidence section when the page has one; the link moves focus there. */
function Reason({ rule, evidenceId }: { rule: RuleExplanation; evidenceId?: (rule: RuleExplanation) => string | undefined }) {
  const id = evidenceId?.(rule);
  if (!id) return <span className="flex-1 text-slate-700 dark:text-slate-300">{rule.explanation}</span>;
  return (
    <a
      href={`#${id}`}
      onClick={(e) => {
        const target = document.getElementById(id);
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({ block: 'start' });
        target.focus({ preventScroll: true });
      }}
      className={`flex-1 text-slate-700 dark:text-slate-300 underline decoration-dotted underline-offset-2 hover:text-[var(--ws-accent)] ${focusRing}`}
    >
      {rule.explanation}
    </a>
  );
}

export function WhyItRanks({ explanation, evidenceId }: { explanation: StockExplanation; evidenceId?: (rule: RuleExplanation) => string | undefined }) {
  const { contributors, detractors } = rankReasons(explanation);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Why this stock ranks" subtitle="Highest weighted contributions among passing rules">
        <div className="space-y-1.5">
          {contributors.map((r) => (
            <div key={r.rule_id} className="flex items-start gap-2 text-xs">
              <StatusDot passed />
              <Reason rule={r} evidenceId={evidenceId} />
              <span className="shrink-0 tabular-nums text-slate-500">{num(r.contribution)}</span>
            </div>
          ))}
          {contributors.length === 0 && (
            <p className="text-xs text-slate-500 italic">No passing rules.</p>
          )}
        </div>
      </Card>
      <Card title="What could invalidate this" subtitle="Failing rules, mandatory gates first">
        <div className="space-y-1.5">
          {detractors.map((r) => (
            <div key={r.rule_id} className="flex items-start gap-2 text-xs">
              <StatusDot passed={false} />
              <Reason rule={r} evidenceId={evidenceId} />
              {explanation.hard_filter_failures.includes(r.rule_id) && (
                <Badge color="rose">gate</Badge>
              )}
            </div>
          ))}
          {detractors.length === 0 && (
            <p className="text-xs text-slate-500 italic">No failing rules.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
