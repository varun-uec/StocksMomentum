/**
 * The Assessment panel (plan 2026-10-19, workflow 2): Momentum25's view of the
 * context symbol in the run in view. It replaces the chart's Details tab and
 * the screener's detail card. Every query keys on (symbol, strategy, run), and
 * none keeps the previous key's data, so the panel never shows another
 * symbol's or run's result while the next one loads.
 */

import { lazy, Suspense } from 'react';
import { Link, useLocation } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Badge, StatusDot } from '@/components/shared/Card';
import { ExplanationSummary } from '@/components/workspace/ExplanationSummary';
import { ProvenanceLine, useLatestRun } from '@/components/momentum25/run';
import { getLiveStockAnalysis, getOhlcv, getRun, getStockExplanation } from '@/lib/api-client';
import { useChartColors } from '@/lib/useChartColors';
import { num } from '@/lib/format';
import { focusRing } from '@/lib/theme';
import type { RuleExplanation } from '@/lib/types';
import { evidenceLayer, type EvidenceControl } from '@/components/momentum25/evidence';
import type { ReplayState } from '@/lib/replay';

const YearClosesChart = lazy(() => import('@/components/momentum25/YearClosesChart'));

const link = `text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`;

/** The current path, for a "Back" link on the page a link opens (same-origin paths only). */
export function useFromParam(): string {
  const { pathname, search } = useLocation();
  return encodeURIComponent(pathname + search);
}

export function AssessmentPanel({
  symbol,
  strategy,
  configHash,
  runId: viewRunId,
  replay,
  evidence,
  onOpenChart,
  onCreateAlert,
}: {
  symbol: string;
  strategy: string;
  configHash?: string;
  /** The view's run; the strategy's latest run when absent. */
  runId?: number;
  /**
   * Bar replay: the newest run on or before the replay date, with no live
   * fallback and no later bars; "Not available in replay" when there is none.
   */
  replay?: ReplayState;
  /** "Show on chart" for criteria whose evidence the chart can draw (/chart only). */
  evidence?: EvidenceControl;
  /** "Open in chart"; absent on /chart, where the chart is already open. */
  onOpenChart?: () => void;
  onCreateAlert?: () => void;
}) {
  const from = useFromParam();
  const latest = useLatestRun(strategy, configHash);
  const runId = replay ? (replay.runId ?? undefined) : viewRunId;
  const pinned = useQuery({ queryKey: ['run', runId], queryFn: () => getRun(runId!), enabled: runId !== undefined });
  const run = replay?.runId === null ? null : runId !== undefined ? pinned.data : replay ? undefined : latest.data;
  const runInView = run?.id;
  const ranked = useQuery({
    queryKey: ['stock-explanation', symbol, strategy, configHash, runInView],
    queryFn: () => getStockExplanation(symbol, runInView, strategy, configHash),
    enabled: runInView !== undefined,
    retry: false,
  });
  // A symbol outside the run gets a live evaluation, labelled as such: it has no rank.
  const live = useQuery({
    queryKey: ['stock-live', symbol, strategy, configHash],
    queryFn: () => getLiveStockAnalysis(symbol, false, strategy, configHash),
    enabled: !replay && (run === null || ranked.isError),
  });

  // The symbol's own last stored bar: when it is newer than the run, the numbers below predate it.
  const asOf = run?.run_date.slice(0, 10);
  const lastBar = useQuery({ queryKey: ['assessment-last-bar', symbol, asOf], queryFn: () => getOhlcv(symbol, asOf), enabled: !!asOf && !replay }).data?.bars.at(-1)?.date;
  const stale = !!asOf && !!lastBar && lastBar > asOf;

  const explanation = ranked.data ?? live.data?.explanation ?? undefined;
  const isLive = !ranked.data && !!live.data;
  const loading = (run === undefined && (latest.isLoading || pinned.isLoading || replay?.runId === undefined)) || ranked.isLoading || (live.isLoading && live.fetchStatus !== 'idle');
  const label = isLive
    ? 'Live analysis, not a ranking'
    : replay
      ? `Replay — newest run on or before ${replay.date}`
      : viewRunId !== undefined && latest.data && viewRunId !== latest.data.id
        ? `Historical — as of ${asOf}`
        : undefined;

  return (
    <div className="px-3 py-2 space-y-3 text-xs" data-testid="assessment">
      <header className="space-y-1 border-b border-[var(--ws-line)] pb-2">
        <div className="flex items-baseline gap-2">
          <h3 data-testid="assessment-symbol" className="text-sm font-semibold">{symbol}</h3>
          {explanation && !isLive && (
            <span className="tabular-nums font-semibold" data-testid="assessment-rank">
              {explanation.rank ? `#${explanation.rank}` : 'Not ranked'}
            </span>
          )}
          {explanation && <Badge color={explanation.overall_passed ? 'emerald' : 'rose'}>{explanation.overall_passed ? 'Qualified' : 'Gate failed'}</Badge>}
          {explanation && <span className="ml-auto tabular-nums text-slate-500" title="Momentum score">{num(explanation.momentum_score)}</span>}
        </div>
        {isLive ? (
          <p className="text-slate-500">Live analysis of the stored daily bars: {symbol} is not in this run, so it has no rank.{live.data?.universe_exclusion ? ` It is outside the screening universe because ${live.data.universe_exclusion}.` : ''}</p>
        ) : null}
        <ProvenanceLine strategy={strategy} run={run} label={label} />
        {replay?.runId === null && (
          <p role="note" data-testid="assessment-replay" className="text-slate-600 dark:text-slate-400">
            Not available in replay: no {strategy} run is dated on or before {replay.date}.
          </p>
        )}
        {stale && !isLive && (
          <p role="note" className="text-amber-700 dark:text-amber-400">
            Run #{run!.id} is as of {asOf}; {symbol}&apos;s stored bars run to {lastBar}. This assessment does not include the later bars.
          </p>
        )}
      </header>

      {onOpenChart && <YearCloses symbol={symbol} />}
      {loading && <p className="text-slate-500">Loading the assessment of {symbol}…</p>}
      {!loading && !explanation && run !== null && (
        <p className="text-slate-500">
          {replay ? `${symbol} is not in run #${run?.id}, the newest run on or before ${replay.date}.` : `No Momentum25 evaluation for ${symbol}: not enough stored history.`}
        </p>
      )}

      {explanation && (
        <>
          <ExplanationSummary explanation={explanation} />
          {evidence && evidence.elsewhere.length > 0 && <p className="text-slate-500">Evidence shown on chart {evidence.elsewhere.join(', ')}.</p>}
          <section aria-label="Criteria">
            <h4 className="font-semibold mb-1">Criteria</h4>
            <ul className="space-y-1">
              {explanation.rule_explanations.map((rule) => (
                <li key={rule.rule_id}>
                  <Criterion rule={rule} gate={explanation.hard_filter_failures.includes(rule.rule_id)} evidence={evidence} />
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

      <div className="flex flex-wrap gap-3 pt-1">
        {onOpenChart && (
          <button type="button" onClick={onOpenChart} className={link}>
            Open in chart
          </button>
        )}
        {/* Both lead to today's data and alerts, which replay hides. */}
        {!replay && (
          <Link to={`/stock/${encodeURIComponent(symbol)}?strategy=${encodeURIComponent(strategy)}&from=${from}`} className={link}>
            Full analysis →
          </Link>
        )}
        {onCreateAlert && !replay && (
          <button type="button" onClick={onCreateAlert} className={link}>
            Create alert
          </button>
        )}
      </div>
    </div>
  );
}

function oneYearAgo(): string {
  const d = new Date();
  d.setUTCFullYear(d.getUTCFullYear() - 1);
  return d.toISOString().slice(0, 10);
}

/** The last year of closes, for views without a chart (the screener's former detail card). */
function YearCloses({ symbol }: { symbol: string }) {
  const colors = useChartColors();
  const { data } = useQuery({ queryKey: ['screener-mini-chart', symbol], queryFn: () => getOhlcv(symbol, oneYearAgo()) });
  const closes = (data?.bars ?? []).map((b) => ({ date: b.date, close: parseFloat(b.close) }));
  return (
    <div className="h-24" aria-label={`${symbol}, last year of closes`} role="img">
      {closes.length > 1 && (
        <Suspense fallback={null}>
          <YearClosesChart closes={closes} tooltipBg={colors.tooltipBg} tooltipBorder={colors.tooltipBorder} />
        </Suspense>
      )}
    </div>
  );
}

/** One criterion; it expands in place to its evidence values. */
function Criterion({ rule, gate, evidence }: { rule: RuleExplanation; gate: boolean; evidence?: EvidenceControl }) {
  const layer = evidence && evidenceLayer(rule.rule_id);
  const shown = !!layer && evidence.shown.includes(layer.id);
  return (
    <details className="group">
      <summary className={`flex items-start gap-1.5 cursor-pointer list-none ${focusRing}`}>
        <span className="mt-1 shrink-0">
          <StatusDot passed={rule.passed} />
        </span>
        <span className="flex-1">{rule.explanation}</span>
        {gate && <Badge color="rose">gate</Badge>}
      </summary>
      <dl className="mt-1 ml-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-slate-600 dark:text-slate-300 tabular-nums">
        <dt>Result</dt>
        <dd>{rule.passed ? 'Pass' : 'Fail'}</dd>
        <dt>Value</dt>
        <dd>{rule.actual_value ?? '—'}</dd>
        <dt>Threshold</dt>
        <dd>{rule.threshold ?? '—'}</dd>
        <dt>Engine</dt>
        <dd>{rule.engine_name}</dd>
        <dt>Weight</dt>
        <dd>{rule.weight}</dd>
        <dt>Contribution</dt>
        <dd>{rule.contribution}</dd>
      </dl>
      {layer && (
        <button type="button" aria-pressed={shown} onClick={() => evidence.toggle(layer)} className={`mt-1 ml-4 ${link}`}>
          {shown ? `Hide ${layer.label} from chart` : `Show ${layer.label} on chart`}
        </button>
      )}
    </details>
  );
}
