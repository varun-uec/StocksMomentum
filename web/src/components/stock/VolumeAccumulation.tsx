'use client';

/**
 * Phase 6.5 — volume & accumulation.
 *
 * Rules/engine from the live explanation where `engine_name ===
 * 'volume_accumulation'`, plus `indicators.avg_volume50` and
 * `indicators.rel_volume`.
 */

import { Card, StatusDot } from '@/components/shared/Card';
import type { IndicatorSnapshot, StockExplanation } from '@/lib/types';
import { num } from '@/lib/format';

function fmtInt(value: string | null): string {
  if (value === null) return '—';
  const n = parseFloat(value);
  return Number.isFinite(n) ? Math.round(n).toLocaleString('en-IN') : '—';
}

export function VolumeAccumulation({
  explanation,
  indicators,
}: {
  explanation: StockExplanation;
  indicators: IndicatorSnapshot;
}) {
  const rules = explanation.rule_explanations.filter(
    (r) => r.engine_name === 'volume_accumulation'
  );
  const engine = explanation.engine_explanations.find(
    (e) => e.engine_name === 'volume_accumulation'
  );

  return (
    <Card
      title="Volume & accumulation"
      subtitle={
        engine
          ? `${engine.rules_passed}/${engine.rule_count} rules passed · score ${num(engine.score)}`
          : undefined
      }
    >
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-900/40">
          <div className="text-xs text-slate-500">50-day average volume</div>
          <div className="text-sm font-semibold tabular-nums text-slate-800 dark:text-slate-200">
            {fmtInt(indicators.avg_volume50)}
          </div>
        </div>
        <div className="px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-900/40">
          <div className="text-xs text-slate-500">Relative volume</div>
          <div className="text-sm font-semibold tabular-nums text-slate-800 dark:text-slate-200">
            {indicators.rel_volume === null
              ? '—'
              : `${parseFloat(indicators.rel_volume).toFixed(2)}x`}
          </div>
        </div>
      </div>

      <div className="space-y-2">
        {rules.map((rule) => (
          <div key={rule.rule_id} className="flex items-start gap-2 text-xs">
            <div className="mt-0.5">
              <StatusDot passed={rule.passed} />
            </div>
            <div className="flex-1 text-slate-700 dark:text-slate-300">{rule.explanation}</div>
            <div className="shrink-0 tabular-nums text-slate-500">{num(rule.contribution)}</div>
          </div>
        ))}
        {rules.length === 0 && (
          <p className="text-xs text-slate-500 italic">Not evaluated for this stock.</p>
        )}
      </div>
    </Card>
  );
}
