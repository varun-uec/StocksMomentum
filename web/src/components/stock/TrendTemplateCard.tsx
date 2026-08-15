'use client';

/**
 * Trend Template presentation (display only).
 *
 * The eight trend-template conditions come from the backend exactly as
 * evaluated — this component neither re-derives nor re-orders pass/fail. It
 * only groups them into the three questions an analyst actually asks:
 *
 *   1. Where is price relative to its own moving averages?
 *   2. Is the longer-term trend structure itself constructive?
 *   3. Is the stock outperforming the rest of the universe?
 *
 * Per-rule weights are read from the strategy config (`weight` in the strategy
 * JSON) purely for visual emphasis: a heavier rule is rendered more
 * prominently. PASS/FAIL is a gate status, never a buy/sell verdict.
 */

import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/shared/Card';
import { getStrategyDetail } from '@/lib/api-client';
import type { RuleExplanation } from '@/lib/types';

type GroupId = 'price_position' | 'trend_structure' | 'relative_strength';

const GROUPS: { id: GroupId; title: string; question: string; ruleIds: string[] }[] = [
  {
    id: 'price_position',
    title: 'Price position',
    question: 'Is price leading its own moving averages, and where does it sit in its 52-week range?',
    ruleIds: [
      'tt_close_above_sma150_200',
      'tt_close_above_sma50',
      'tt_above_52w_low',
      'tt_near_52w_high',
    ],
  },
  {
    id: 'trend_structure',
    title: 'Trend structure',
    question: 'Are the moving averages themselves stacked and rising?',
    ruleIds: ['tt_sma150_above_sma200', 'tt_sma200_uptrend', 'tt_sma_stack'],
  },
  {
    id: 'relative_strength',
    title: 'Relative strength',
    question: 'Is it outperforming the rest of the universe?',
    ruleIds: ['tt_rs_rating_min'],
  },
];

/** Short scannable label per rule; the backend explanation carries the numbers. */
const RULE_LABELS: Record<string, string> = {
  tt_close_above_sma150_200: 'Close above the 150- and 200-day averages',
  tt_close_above_sma50: 'Close above the 50-day average',
  tt_above_52w_low: 'Well clear of the 52-week low',
  tt_near_52w_high: 'Close to the 52-week high',
  tt_sma150_above_sma200: '150-day average above the 200-day',
  tt_sma200_uptrend: '200-day average trending up',
  tt_sma_stack: '50-day average above the 150- and 200-day',
  tt_rs_rating_min: 'RS rating at or above the minimum',
};

function RuleRow({
  rule,
  weight,
  hint,
}: {
  rule: RuleExplanation;
  weight: number | null;
  hint?: string;
}) {
  const heavy = weight !== null && weight > 1;
  return (
    <li
      className={`flex items-start gap-2.5 rounded-lg border-l-2 px-2.5 py-2 ${
        rule.passed
          ? 'border-emerald-500 bg-emerald-50/60 dark:border-emerald-500/70 dark:bg-emerald-500/5'
          : 'border-rose-400 bg-rose-50/60 dark:border-rose-500/70 dark:bg-rose-500/5'
      }`}
    >
      <span
        aria-hidden
        className={`mt-px shrink-0 text-sm leading-none ${
          rule.passed ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400'
        }`}
      >
        {rule.passed ? '✓' : '✗'}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span
            className={`${heavy ? 'text-sm font-semibold' : 'text-xs font-medium'} text-slate-800 dark:text-slate-200`}
          >
            {RULE_LABELS[rule.rule_id] ?? rule.rule_id}
          </span>
          <span className="sr-only">{rule.passed ? 'condition met' : 'condition not met'}</span>
          {heavy && (
            <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-px rounded bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">
              weight ×{weight}
            </span>
          )}
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{rule.explanation}</div>
        {!rule.passed && hint && (
          <div className="text-xs text-amber-600 dark:text-amber-400/90 mt-0.5">{hint}</div>
        )}
      </div>
    </li>
  );
}

export function TrendTemplateCard({
  rules,
  strategyName,
  hints = {},
}: {
  rules: RuleExplanation[];
  strategyName: string;
  hints?: Record<string, string>;
}) {
  const { data: strategy } = useQuery({
    queryKey: ['strategy-detail', strategyName],
    queryFn: () => getStrategyDetail(strategyName),
    staleTime: Infinity,
  });

  const weights = new Map<string, number>();
  for (const engine of strategy?.config.engines ?? []) {
    if (engine.id !== 'trend_template') continue;
    for (const rule of engine.rules) weights.set(rule.id, parseFloat(rule.weight));
  }

  if (rules.length === 0) {
    return (
      <Card title="Trend Template">
        <p className="text-xs text-slate-500 italic">Not evaluated for this stock.</p>
      </Card>
    );
  }

  const byId = new Map(rules.map((r) => [r.rule_id, r]));
  const grouped = GROUPS.map((g) => ({
    ...g,
    rules: g.ruleIds.map((id) => byId.get(id)).filter((r): r is RuleExplanation => !!r),
  })).filter((g) => g.rules.length > 0);
  // Anything the config adds that this component does not yet know about still
  // has to be shown, so it is never silently dropped from the display.
  const known = new Set(GROUPS.flatMap((g) => g.ruleIds));
  const other = rules.filter((r) => !known.has(r.rule_id));

  const passed = rules.filter((r) => r.passed).length;
  const gatePassed = passed === rules.length;

  return (
    <Card
      title="Trend Template"
      subtitle={`All ${rules.length} conditions must hold — this is a hard gate, not a score`}
      badge={{
        text: gatePassed ? `GATE PASS · ${passed}/${rules.length}` : `GATE FAIL · ${passed}/${rules.length}`,
        color: gatePassed ? 'emerald' : 'rose',
      }}
    >
      <div className="space-y-4">
        {grouped.map((group) => {
          const groupPassed = group.rules.filter((r) => r.passed).length;
          return (
            <section key={group.id}>
              <div className="flex items-baseline justify-between gap-3 mb-1.5">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300">
                  {group.title}
                </h4>
                <span className="text-xs tabular-nums text-slate-400 dark:text-slate-500 shrink-0">
                  {groupPassed}/{group.rules.length}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">{group.question}</p>
              <ul className="space-y-1.5">
                {group.rules.map((rule) => (
                  <RuleRow
                    key={rule.rule_id}
                    rule={rule}
                    weight={weights.get(rule.rule_id) ?? null}
                    hint={hints[rule.rule_id]}
                  />
                ))}
              </ul>
            </section>
          );
        })}

        {other.length > 0 && (
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300 mb-2">
              Other conditions
            </h4>
            <ul className="space-y-1.5">
              {other.map((rule) => (
                <RuleRow
                  key={rule.rule_id}
                  rule={rule}
                  weight={weights.get(rule.rule_id) ?? null}
                  hint={hints[rule.rule_id]}
                />
              ))}
            </ul>
          </section>
        )}
      </div>
    </Card>
  );
}
