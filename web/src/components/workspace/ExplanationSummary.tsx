import { Badge, StatusDot } from '@/components/shared/Card';
import { investmentReadiness } from '@/components/stock/readiness';
import { rankReasons } from '@/components/stock/WhyItRanks';
import { num } from '@/lib/format';
import type { StockExplanation } from '@/lib/types';

/**
 * Momentum25's view of one symbol in a few lines: readiness, scores, gate
 * failures, the top reasons it ranks and what could invalidate it. Used by the
 * chart's side panel and the screener's detail panel.
 */
export function ExplanationSummary({ explanation }: { explanation: StockExplanation }) {
  const readiness = investmentReadiness(explanation);
  const { contributors, detractors } = rankReasons(explanation, 3);
  return (
    <div className="space-y-3 text-xs">
      <div className="space-y-1">
        <Badge color={readiness.color}>{readiness.label}</Badge>
        <dl className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-slate-600 dark:text-slate-300">
          {explanation.rank !== null && (
            <>
              <dt>Rank</dt>
              <dd className="text-right tabular-nums">#{explanation.rank}</dd>
            </>
          )}
          <dt>Momentum score</dt>
          <dd className="text-right tabular-nums">{num(explanation.momentum_score)}</dd>
          <dt>Setup score</dt>
          <dd className="text-right tabular-nums">{num(explanation.buy_setup_score)}</dd>
          <dt>Gate failures</dt>
          <dd className="text-right tabular-nums">{explanation.hard_filter_failures.length}</dd>
        </dl>
      </div>
      <section aria-label={explanation.rank === null ? 'Why it is not ranked' : 'Why it ranks'}>
        <h3 className="font-semibold mb-1">{explanation.rank === null ? 'Why it is not ranked' : 'Why it ranks'}</h3>
        {contributors.length === 0 && <p className="text-slate-500">No passing rules.</p>}
        {contributors.map((r) => (
          <p key={r.rule_id} className="flex items-start gap-1.5 text-slate-700 dark:text-slate-300">
            <span className="mt-1 shrink-0">
              <StatusDot passed />
            </span>
            <span>{r.explanation}</span>
          </p>
        ))}
      </section>
      <section aria-label="What could invalidate this">
        <h3 className="font-semibold mb-1">What could invalidate this</h3>
        {detractors.length === 0 && <p className="text-slate-500">No failing rules.</p>}
        {detractors.map((r) => (
          <p key={r.rule_id} className="flex items-start gap-1.5 text-slate-700 dark:text-slate-300">
            <span className="mt-1 shrink-0">
              <StatusDot passed={false} />
            </span>
            <span className="flex-1">{r.explanation}</span>
            {explanation.hard_filter_failures.includes(r.rule_id) && (
              <span className="shrink-0">
                <Badge color="rose">gate</Badge>
              </span>
            )}
          </p>
        ))}
      </section>
    </div>
  );
}
