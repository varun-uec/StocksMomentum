'use client';

/**
 * The Elliott Wave explanation panels, moved out of the page module so both
 * the Elliott Wave route and the unified analysis screen render the same ones.
 * Pure move: no logic and no markup changed.
 */

import { describe, type DegreeNode } from '@/components/stock/useElliottWaveChart';
import type { ElliottEvidenceStatus, ElliottWaveCount } from '@/lib/types';

const STATUS_STYLE: Record<ElliottEvidenceStatus, string> = {
  supporting: 'text-emerald-600 dark:text-emerald-400',
  contradicting: 'text-rose-600 dark:text-rose-400',
  'not measurable': 'text-slate-400 dark:text-slate-500',
};

export function Evidence({
  status,
  children,
}: {
  status: ElliottEvidenceStatus;
  children: React.ReactNode;
}) {
  return (
    <li className="text-xs text-slate-600 dark:text-slate-400">
      <span className={`font-semibold ${STATUS_STYLE[status]}`}>
        {status === 'supporting' ? '✓' : status === 'contradicting' ? '✕' : '–'}
      </span>{' '}
      {children}
    </li>
  );
}

/** Everything measured about one selected wave. */
export function WaveDetail({
  count,
  label,
  color,
}: {
  count: ElliottWaveCount;
  label: string;
  color: string;
}) {
  const personality = count.personality.filter((check) => check.wave === label);
  const needle = `wave ${label} `;
  const ratios = [...count.price_relationships, ...count.time_relationships].filter((rel) =>
    rel.name.startsWith(needle)
  );

  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold" style={{ color }}>
        Wave {label}
      </div>

      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
          Personality corroboration
        </div>
        {personality.length === 0 ? (
          <p className="text-xs text-slate-500">
            No volume or momentum characteristic is defined for this position.
          </p>
        ) : (
          <ul className="space-y-1">
            {personality.map((check) => (
              <Evidence key={check.expectation} status={check.status}>
                {check.expectation} — <span className="text-slate-500">{check.detail}</span>
              </Evidence>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
          Fibonacci relationships
        </div>
        {ratios.length === 0 ? (
          <p className="text-xs text-slate-500">No documented ratio involves this wave.</p>
        ) : (
          <ul className="space-y-1">
            {ratios.map((rel) => (
              <li key={`${rel.kind}-${rel.name}`} className="text-xs text-slate-600 dark:text-slate-400">
                <span className="uppercase text-[10px] tracking-wider text-slate-400">
                  {rel.kind}
                </span>{' '}
                {rel.name}: <span className="tabular-nums">{parseFloat(rel.observed).toFixed(3)}</span>{' '}
                <span className="text-slate-500">
                  (nearest {rel.nearest}, {(parseFloat(rel.proximity) * 100).toFixed(0)}% proximity)
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function CountSummary({ count, color }: { count: ElliottWaveCount; color: string }) {
  const node: DegreeNode = {
    degree: count.degree,
    pattern: count.pattern,
    variant: count.variant,
    labels: count.labels,
    subdivisions: count.subdivisions,
  };
  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500">Current position</div>
        <div className="text-lg font-semibold" style={{ color }}>
          {count.current_position}
        </div>
        <div className="text-xs text-slate-500 mt-1">
          {describe(node)} · {count.family} · {count.direction === 'up' ? 'upward' : 'downward'} ·{' '}
          {count.degree} degree
        </div>
      </div>

      {!count.is_current && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          This structure ended before the latest confirmed pivot, so no completion zone is
          projected.
        </p>
      )}

      {count.projection && (
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500">
            Projected completion zone
          </div>
          <div className="text-sm font-semibold text-slate-800 dark:text-slate-200 tabular-nums">
            {parseFloat(count.projection.low).toFixed(2)} –{' '}
            {parseFloat(count.projection.high).toFixed(2)}
          </div>
          <div className="text-xs text-slate-500">{count.projection.basis}</div>
          <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
            Elliott Wave analytical projection; not part of the Momentum25 score or ranking.
          </p>
        </div>
      )}

      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">Rules satisfied</div>
        <ul className="space-y-1">
          {count.rules_applied.map((rule) => (
            <li key={rule} className="text-xs text-slate-600 dark:text-slate-400">
              · {rule}
            </li>
          ))}
        </ul>
      </div>

      {count.allowances.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
            Interpretation this label required
          </div>
          <ul className="space-y-1">
            {count.allowances.map((allowance) => (
              <li key={allowance} className="text-xs text-amber-700 dark:text-amber-400">
                · {allowance}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
          Guidelines measured
        </div>
        <ul className="space-y-1">
          {count.guideline_checks.map((check) => (
            <Evidence key={check.name} status={check.status}>
              {check.name} — <span className="text-slate-500">{check.detail}</span>
            </Evidence>
          ))}
        </ul>
      </div>
    </div>
  );
}
