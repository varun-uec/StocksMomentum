'use client';

/**
 * Elliott Wave analysis screen (separate research surface).
 *
 * Every label, pivot, ratio, personality check and confidence number comes from
 * `GET /stocks/{symbol}/elliott-wave`; nothing is computed or inferred here.
 * This screen annotates a chart and explains a labelling. It produces no
 * buy/sell verdict and no score, and nothing it displays is an input to the
 * Momentum25 score, ranking or gates.
 */

import { useCallback, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { LineStyle } from 'lightweight-charts';
import { getElliottWave } from '@/lib/api-client';
import { Card, Badge, LoadingSpinner, ErrorMessage, PageHeader } from '@/components/shared/Card';
import {
  PriceChart,
  type ChartMarker,
  type ChartOverlayLine,
} from '@/components/stock/PriceChart';
import { lookbackDaysFor, useChartShell } from '@/components/stock/useChartShell';
import { focusRing } from '@/lib/theme';
import { DEFAULT_STRATEGY } from '@/app/strategy-context';
import { SymbolActionBar } from '@/components/stock/SymbolActionBar';
import type {
  ElliottEvidenceStatus,
  ElliottSubdivision,
  ElliottWaveCount,
  ElliottWaveLabel,
} from '@/lib/types';

const MAX_LOOKBACK_DAYS = 2000;

/** One colour per ranked candidate, so a count keeps its identity everywhere. */
const CANDIDATE_COLORS = ['#a855f7', '#0ea5e9', '#f59e0b'];
/** Lower-opacity variants, so the degree below the selected one reads as finer. */
const CANDIDATE_FAINT = [
  'rgba(168, 85, 247, 0.45)',
  'rgba(14, 165, 233, 0.45)',
  'rgba(245, 158, 11, 0.45)',
];

const STATUS_STYLE: Record<ElliottEvidenceStatus, string> = {
  supporting: 'text-emerald-600 dark:text-emerald-400',
  contradicting: 'text-rose-600 dark:text-rose-400',
  'not measurable': 'text-slate-400 dark:text-slate-500',
};

/** A level of the degree hierarchy: the count itself, or a nested subdivision. */
interface DegreeNode {
  degree: string;
  pattern: string;
  variant: string | null;
  labels: ElliottWaveLabel[];
  subdivisions: ElliottSubdivision[];
}

function rootNode(count: ElliottWaveCount): DegreeNode {
  return {
    degree: count.degree,
    pattern: count.pattern,
    variant: count.variant,
    labels: count.labels,
    subdivisions: count.subdivisions,
  };
}

function subNode(subdivision: ElliottSubdivision): DegreeNode {
  return {
    degree: subdivision.degree,
    pattern: subdivision.pattern,
    variant: subdivision.variant,
    labels: subdivision.labels,
    subdivisions: subdivision.subdivisions,
  };
}

/** Walk `path` (subdivision indices) down from the count, collecting each level. */
function nodesAlong(count: ElliottWaveCount, path: number[]): DegreeNode[] {
  const nodes = [rootNode(count)];
  let subdivisions = count.subdivisions;
  for (const index of path) {
    const child = subdivisions[index];
    if (!child) break;
    nodes.push(subNode(child));
    subdivisions = child.subdivisions;
  }
  return nodes;
}

function describe(node: DegreeNode): string {
  return node.variant ? `${node.variant} ${node.pattern}` : node.pattern;
}

function Evidence({ status, children }: { status: ElliottEvidenceStatus; children: React.ReactNode }) {
  return (
    <li className="text-xs text-slate-600 dark:text-slate-400">
      <span className={`font-semibold ${STATUS_STYLE[status]}`}>
        {status === 'supporting' ? '✓' : status === 'contradicting' ? '✕' : '–'}
      </span>{' '}
      {children}
    </li>
  );
}

/** The persistent explanation of why the top count ranks where it does. */
function RankingPanel({
  rationale,
  method,
  components,
  confidence,
}: {
  rationale: string[];
  method: string;
  components: ElliottWaveCount['confidence_components'];
  confidence: string;
}) {
  const [showMethod, setShowMethod] = useState(false);
  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500">
          Labelling confidence
        </div>
        <div className="text-2xl font-semibold tabular-nums text-slate-800 dark:text-slate-200">
          {parseFloat(confidence).toFixed(0)}
          <span className="text-sm text-slate-400"> / 100</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1">
          How cleanly the price action fits this labelling — a measure of fit to Elliott Wave
          theory, not a forecast and not a probability of profit.
        </p>
      </div>

      <ul className="space-y-1">
        {components.map((component) => (
          <li key={component.name} className="text-xs">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-slate-600 dark:text-slate-400">{component.name}</span>
              <span className="tabular-nums text-slate-500">
                {parseFloat(component.points).toFixed(1)} / {parseFloat(component.weight).toFixed(0)}
              </span>
            </div>
            <div className="text-[10px] text-slate-400 dark:text-slate-500">{component.detail}</div>
          </li>
        ))}
      </ul>

      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
          Why this count ranks where it does
        </div>
        <ul className="space-y-1">
          {rationale.map((line) => (
            <li key={line} className="text-xs text-slate-600 dark:text-slate-400">
              · {line}
            </li>
          ))}
        </ul>
      </div>

      <button
        type="button"
        onClick={() => setShowMethod((v) => !v)}
        className={`text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}
      >
        {showMethod ? 'Hide the ranking method' : 'How counts are ranked'}
      </button>
      {showMethod && (
        <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">{method}</p>
      )}
    </div>
  );
}

/** Everything measured about one selected wave. */
function WaveDetail({
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

function CountSummary({ count, color }: { count: ElliottWaveCount; color: string }) {
  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500">Current position</div>
        <div className="text-lg font-semibold" style={{ color }}>
          {count.current_position}
        </div>
        <div className="text-xs text-slate-500 mt-1">
          {describe(count)} · {count.family} · {count.direction === 'up' ? 'upward' : 'downward'} ·{' '}
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

export default function ElliottWavePage() {
  const { symbol } = useParams<{ symbol: string }>();
  const searchParams = useSearchParams();
  const strategyQuery = searchParams.get('strategy');
  const [thresholdPct, setThresholdPct] = useState(5);
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [degreePath, setDegreePath] = useState<number[]>([]);
  const [selectedWave, setSelectedWave] = useState<number | null>(null);

  // Same chart shell as /stock/[symbol]: indicator panes, moving averages and
  // drawing tools all carry across, persisted per symbol.
  const { timeframe, ready: chartReady, chartProps } = useChartShell(
    symbol ?? '',
    strategyQuery ?? DEFAULT_STRATEGY
  );

  const strategyName = strategyQuery ?? DEFAULT_STRATEGY;

  const {
    data: analysis,
    isLoading: waveLoading,
    error: waveError,
  } = useQuery({
    queryKey: ['elliott-wave', symbol, timeframe, thresholdPct, strategyName],
    queryFn: () =>
      getElliottWave(
        symbol,
        lookbackDaysFor(timeframe, MAX_LOOKBACK_DAYS),
        thresholdPct,
        strategyName
      ),
    enabled: !!symbol,
  });

  const candidates = analysis?.candidates ?? [];
  const count = candidates[candidateIndex] ?? candidates[0] ?? null;
  const colorIndex = Math.min(candidateIndex, CANDIDATE_COLORS.length - 1);
  const color = CANDIDATE_COLORS[colorIndex];
  const faint = CANDIDATE_FAINT[colorIndex];

  const path = useMemo(
    () => (count ? nodesAlong(count, degreePath) : []),
    [count, degreePath]
  );
  const active = path[path.length - 1] ?? null;

  const selectCount = useCallback((index: number) => {
    setCandidateIndex(index);
    setDegreePath([]);
    setSelectedWave(null);
  }, []);

  const markers = useMemo<ChartMarker[]>(() => {
    if (!active || !count) return [];
    const own: ChartMarker[] = active.labels
      .filter((l) => l.label !== '0')
      .map((l) => ({
        date: l.bar_date,
        text: l.label,
        position: count.direction === 'up' ? 'aboveBar' : 'belowBar',
        color,
      }));
    const finer: ChartMarker[] = active.subdivisions.flatMap((subdivision) =>
      subdivision.labels
        .filter((l) => l.label !== '0')
        .map((l) => ({
          date: l.bar_date,
          text: `(${l.label})`,
          position: count.direction === 'up' ? 'aboveBar' : ('belowBar' as const),
          color: faint,
          size: 0.7,
        }))
    );
    return [...own, ...finer];
  }, [active, count, color, faint]);

  const overlayLine = useMemo(
    () =>
      (active?.labels ?? []).map((l) => ({
        date: l.bar_date,
        price: parseFloat(l.price),
        color,
      })),
    [active, color]
  );

  const overlayLines = useMemo<ChartOverlayLine[]>(
    () =>
      (active?.subdivisions ?? []).map((subdivision) => ({
        points: subdivision.labels.map((l) => ({
          date: l.bar_date,
          price: parseFloat(l.price),
        })),
        color: faint,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
      })),
    [active, faint]
  );

  const priceZone = useMemo(
    () =>
      count?.projection && degreePath.length === 0
        ? {
            low: parseFloat(count.projection.low),
            high: parseFloat(count.projection.high),
            title: 'Projected zone',
            color,
          }
        : null,
    [count, degreePath, color]
  );

  // Selecting a wave scrolls the chart to that leg; clearing it restores the
  // full loaded range.
  const visibleRange = useMemo(() => {
    if (!active || selectedWave === null || selectedWave < 1) return null;
    return {
      from: active.labels[selectedWave - 1].bar_date,
      to: active.labels[selectedWave].bar_date,
    };
  }, [active, selectedWave]);

  if (!symbol) return <ErrorMessage message="No symbol supplied." />;

  const backHref = `/stock/${symbol}${strategyQuery ? `?strategy=${strategyQuery}` : ''}`;
  const selectedLabel =
    active && selectedWave !== null ? active.labels[selectedWave].label : null;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title={`${symbol} — Elliott Wave Analysis`}
        subtitle="Labelled wave count over the stored daily price history"
      >
        {count && <Badge color="indigo">{count.degree} degree</Badge>}
        <SymbolActionBar symbol={symbol} strategyName={strategyQuery} current="elliott-wave" />
        <Link
          href={backHref}
          className={`text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}
        >
          ← Back to research
        </Link>
      </PageHeader>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <p className="text-xs text-slate-500">
          Chart annotation only — this view produces no buy/sell verdict and no score.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <label
            className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400"
            title="The smallest reversal that confirms a pivot, and so the finest degree labelled. The top degree is coarsened away from it automatically."
          >
            Finest degree (reversal threshold)
            <input
              type="range"
              min={2}
              max={20}
              step={1}
              value={thresholdPct}
              onChange={(e) => {
                setThresholdPct(Number(e.target.value));
                selectCount(0);
              }}
              className="accent-indigo-500"
            />
            <span className="tabular-nums font-semibold">{thresholdPct}%</span>
          </label>

          {candidates.length > 1 && (
            <div className="flex items-center gap-1" role="group" aria-label="Competing counts">
              {candidates.map((candidate, index) => (
                <button
                  key={`${candidate.pattern}-${candidate.labels[0].bar_date}`}
                  type="button"
                  onClick={() => selectCount(index)}
                  aria-pressed={index === candidateIndex}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${focusRing} ${
                    index === candidateIndex
                      ? 'border-current'
                      : 'border-slate-300 dark:border-slate-700 text-slate-500'
                  }`}
                  style={index === candidateIndex ? { color: CANDIDATE_COLORS[index] } : undefined}
                >
                  {index === 0 ? 'Top count' : `Alternate ${index}`}: {describe(candidate)} ·{' '}
                  {parseFloat(candidate.labelling_confidence).toFixed(0)}
                </button>
              ))}
            </div>
          )}
        </div>

        {count && path.length > 0 && (
          <nav className="flex flex-wrap items-center gap-1 text-xs" aria-label="Wave degree">
            {path.map((node, level) => (
              <span key={`${node.degree}-${level}`} className="flex items-center gap-1">
                {level > 0 && <span className="text-slate-400">▸</span>}
                <button
                  type="button"
                  onClick={() => {
                    setDegreePath(degreePath.slice(0, level));
                    setSelectedWave(null);
                  }}
                  aria-current={level === path.length - 1 ? 'true' : undefined}
                  className={`px-2 py-1 rounded-md font-medium ${focusRing} ${
                    level === path.length - 1
                      ? 'bg-indigo-100 dark:bg-indigo-600/25 text-indigo-700 dark:text-indigo-300'
                      : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  {node.degree} · {describe(node)}
                </button>
              </span>
            ))}
            {selectedWave !== null && (
              <button
                type="button"
                onClick={() => setSelectedWave(null)}
                className={`ml-2 px-2 py-1 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
              >
                Show full range
              </button>
            )}
          </nav>
        )}

        <Card>
          {chartReady && (
            <PriceChart
              {...chartProps}
              height={620}
              markers={markers}
              overlayLine={overlayLine}
              overlayLines={overlayLines}
              priceZone={priceZone}
              visibleRange={visibleRange}
              footnote={
                active && count
                  ? `${describe(active)} at ${active.degree} degree, spanning ${active.labels[0].bar_date} to ${active.labels[active.labels.length - 1].bar_date}, within ${analysis?.bars_analyzed ?? 0} bars analysed; ${analysis?.pivots.length ?? 0} confirmed pivots at the top degree's ${analysis?.top_degree_threshold_pct ?? thresholdPct}% reversal threshold, subdivided down to ${thresholdPct}%. Parenthesised labels are the next finer degree. Dashed bounds mark the projected completion zone.`
                  : `${analysis?.pivots.length ?? 0} confirmed pivots at a ${analysis?.top_degree_threshold_pct ?? thresholdPct}% reversal threshold.`
              }
            />
          )}
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card
            title={candidateIndex === 0 ? 'Top-ranked count' : `Alternate count ${candidateIndex}`}
            subtitle={
              candidates.length > 1
                ? `${candidates.length} counts satisfy the rules; they are ranked, not merely listed.`
                : undefined
            }
          >
            {waveLoading && <LoadingSpinner text="Labelling the wave structure…" />}
            {waveError && (
              <ErrorMessage message={`The wave analysis for ${symbol} could not be loaded.`} />
            )}
            {!waveLoading && !waveError && !count && (
              <p className="text-xs text-slate-500">No count is asserted at this threshold.</p>
            )}
            {count && <CountSummary count={count} color={color} />}
          </Card>

          <Card title="Waves" subtitle="Select a wave to inspect its evidence and zoom to its leg">
            {active && (
              <ul className="space-y-1">
                {active.labels.map((label, index) => {
                  if (index === 0) return null;
                  const child = active.subdivisions.find((s) => s.of_label === label.label);
                  return (
                    <li key={`${label.label}-${label.bar_date}`}>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            setSelectedWave(selectedWave === index ? null : index)
                          }
                          aria-pressed={selectedWave === index}
                          className={`flex-1 text-left px-2 py-1 rounded-md text-xs ${focusRing} ${
                            selectedWave === index
                              ? 'bg-indigo-50 dark:bg-indigo-600/20'
                              : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                          }`}
                        >
                          <span className="font-semibold" style={{ color }}>
                            Wave {label.label}
                          </span>{' '}
                          <span className="text-slate-500 tabular-nums">
                            {label.bar_date} · {parseFloat(label.price).toFixed(2)}
                          </span>
                        </button>
                        {child && (
                          <button
                            type="button"
                            onClick={() => {
                              setDegreePath([
                                ...degreePath,
                                active.subdivisions.indexOf(child),
                              ]);
                              setSelectedWave(null);
                            }}
                            title={`${child.position_fit.name} — ${child.position_fit.detail}`}
                            className={`px-2 py-1 rounded-md text-[10px] font-medium text-indigo-600 dark:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`}
                          >
                            ↳ {child.degree}
                          </button>
                        )}
                      </div>
                      {selectedWave === index && count && degreePath.length === 0 && (
                        <div className="mt-2 mb-3 ml-2 pl-3 border-l border-slate-200 dark:border-slate-800">
                          <WaveDetail count={count} label={label.label} color={color} />
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {active && degreePath.length > 0 && (
              <p className="text-[11px] text-slate-500 mt-3">
                Personality and Fibonacci evidence is measured for the top degree of a count;
                finer degrees are labelling depth only.
              </p>
            )}
          </Card>

          <Card title="Ranking">
            {count && (
              <RankingPanel
                rationale={analysis?.ranking_rationale ?? []}
                method={analysis?.ranking_method ?? ''}
                components={count.confidence_components}
                confidence={count.labelling_confidence}
              />
            )}
          </Card>
        </div>

        <Card title="Pivots and notes">
          <ul className="space-y-1 mb-3">
            {(analysis?.notes ?? []).map((note) => (
              <li key={note} className="text-xs text-slate-600 dark:text-slate-400">
                {note}
              </li>
            ))}
          </ul>
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-xs tabular-nums">
              <thead className="text-slate-500">
                <tr>
                  <th className="text-left font-medium py-1">Date</th>
                  <th className="text-left font-medium py-1">Type</th>
                  <th className="text-right font-medium py-1">Price</th>
                </tr>
              </thead>
              <tbody>
                {(analysis?.pivots ?? []).map((p) => (
                  <tr
                    key={`${p.bar_date}-${p.kind}`}
                    className="border-t border-slate-200 dark:border-slate-800"
                  >
                    <td className="py-1">{p.bar_date}</td>
                    <td className="py-1">{p.kind === 'H' ? 'Swing high' : 'Swing low'}</td>
                    <td className="py-1 text-right">{parseFloat(p.price).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
