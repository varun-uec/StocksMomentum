'use client';

/**
 * Phase 6.8 — suggested stop-loss, bound to `/stocks/{symbol}/live` →
 * `suggested_stop.{level,method}`, and Phase 6.5 — the trailing (chandelier)
 * variant from `trailing_stop`.
 *
 * Both are displayed as downside caps only. The platform produces no price
 * target, reward estimate or R-multiple, so none is shown or implied here —
 * including for the trailing level, whose only difference is that it ratchets
 * up with the highest high rather than staying anchored to entry.
 */

import { Badge, Card } from '@/components/shared/Card';
import type { StopLossSuggestion } from '@/lib/types';

function StopRow({
  label,
  stop,
  latestClose,
  note,
}: {
  label: string;
  stop: StopLossSuggestion | null;
  latestClose: number | null;
  note: string;
}) {
  const level = stop?.level ? parseFloat(stop.level) : null;
  const distancePct =
    level !== null && latestClose !== null && latestClose !== 0
      ? ((latestClose - level) / latestClose) * 100
      : null;

  return (
    <div className="px-3 py-2.5 rounded-lg bg-slate-50 dark:bg-slate-900/40">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
        {label}
      </div>
      {level === null ? (
        <p className="text-xs text-slate-500 italic">
          No defensible level could be computed{stop?.method ? ` (${stop.method})` : ''}.
        </p>
      ) : (
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="text-2xl font-bold tabular-nums text-slate-800 dark:text-slate-200">
            {level.toFixed(2)}
          </span>
          <Badge color="slate">{stop?.method}</Badge>
          {distancePct !== null && (
            <span className="text-xs text-slate-500 tabular-nums">
              {distancePct.toFixed(2)}% below the latest close
            </span>
          )}
        </div>
      )}
      <p className="text-xs text-slate-500 mt-1.5">{note}</p>
    </div>
  );
}

export function SuggestedStop({
  stop,
  trailingStop,
  latestClose,
}: {
  stop: StopLossSuggestion | null;
  trailingStop?: StopLossSuggestion | null;
  latestClose: number | null;
}) {
  return (
    <Card title="Suggested stop-loss" subtitle="Downside caps — neither is a target">
      <div className="space-y-3">
        <StopRow
          label="Fixed (from entry)"
          stop={stop}
          latestClose={latestClose}
          note="Anchored to the latest close, a fixed ATR multiple below it."
        />
        <StopRow
          label="Trailing (chandelier)"
          stop={trailingStop ?? null}
          latestClose={latestClose}
          note="Anchored to the highest high of the recent window, so it ratchets up as that high rises and never moves down."
        />
      </div>
      <p className="text-xs text-slate-500 mt-3">
        Risk caps, not targets: these are where further downside would be cut if the position is
        already held. They carry no reward estimate and are not predictions.
      </p>
    </Card>
  );
}
