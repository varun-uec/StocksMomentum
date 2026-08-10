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

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { Card, Badge, LoadingSpinner, ErrorMessage, PageHeader } from '@/components/shared/Card';
import { PriceChart } from '@/components/stock/PriceChart';
import { useChartShell } from '@/components/stock/useChartShell';
import {
  CANDIDATE_COLORS,
  describe,
  useElliottWaveChart,
} from '@/components/stock/useElliottWaveChart';
import { CountSummary, WaveDetail } from '@/components/stock/elliott-wave-panels';
import { focusRing } from '@/lib/theme';
import { DEFAULT_STRATEGY } from '@/app/strategy-context';
import { SymbolActionBar } from '@/components/stock/SymbolActionBar';
import type { ElliottWaveCount } from '@/lib/types';

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

export default function ElliottWavePage() {
  const { symbol } = useParams<{ symbol: string }>();
  const searchParams = useSearchParams();
  const strategyQuery = searchParams.get('strategy');
  // Same chart shell as /stock/[symbol]: indicator panes, moving averages and
  // drawing tools all carry across, persisted per symbol.
  const { timeframe, ready: chartReady, chartProps } = useChartShell(
    symbol ?? '',
    strategyQuery ?? DEFAULT_STRATEGY
  );
  const strategyName = strategyQuery ?? DEFAULT_STRATEGY;

  const {
    analysis,
    waveLoading,
    waveError,
    candidates,
    count,
    color,
    path,
    active,
    thresholdPct,
    setThresholdPct,
    candidateIndex,
    selectCount,
    degreePath,
    setDegreePath,
    selectedWave,
    setSelectedWave,
    markers,
    overlayLine,
    overlayLines,
    priceZone,
    visibleRange,
  } = useElliottWaveChart(symbol ?? '', timeframe, strategyName);

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
