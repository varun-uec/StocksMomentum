'use client';

/**
 * Phase 6.6 — pattern recognition, plus Phase 8 classical chart-pattern
 * detection.
 *
 * The two upper cards are bound to live `rule_explanations` where
 * `engine_name` is `'pattern'` or `'breakout'`. Status = `passed`, quality =
 * `contribution`, description = the backend `explanation` string.
 *
 * The lower card runs `POST /stocks/{symbol}/chart-patterns` — and only on an
 * explicit click. Detection never runs on page load. Everything shown comes
 * from that response: pattern name, completion score, the structural criteria
 * that were and were not met, and the geometry drawn on the chart. No target
 * price, no price objective, and no buy/sell call is derived from any pattern;
 * detection also plays no part in the ranking or composite score.
 */

import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Card, StatusDot } from '@/components/shared/Card';
import { detectChartPatterns } from '@/lib/api-client';
import { focusRing } from '@/lib/theme';
import type {
  ChartPatternAnalysis,
  DetectedPattern,
  OHLCVBarDTO,
  RuleExplanation,
  StockExplanation,
} from '@/lib/types';
import {
  PriceChart,
  type ChartOverlayLine,
  type TimeframeId,
} from '@/components/stock/PriceChart';

const GEOMETRY_COLORS = ['#a855f7', '#0ea5e9', '#f59e0b', '#10b981'];

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

function PatternCandidate({
  pattern,
  selected,
  onSelect,
}: {
  pattern: DetectedPattern;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        selected
          ? 'border-indigo-400 dark:border-indigo-500 bg-indigo-50/60 dark:bg-indigo-900/20'
          : 'border-slate-200 dark:border-slate-700/50'
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className={`w-full flex items-baseline justify-between gap-3 text-left ${focusRing}`}
      >
        <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
          {pattern.display_name}
        </span>
        <span className="text-xs text-slate-500 tabular-nums shrink-0">
          {pattern.completion_score}/100 criteria met · {pattern.starts_on} → {pattern.ends_on}
        </span>
      </button>
      <ul className="mt-2 space-y-1">
        {pattern.criteria.map((c) => (
          <li key={c.label} className="flex items-start gap-2 text-xs">
            <span className={c.met ? 'text-emerald-500' : 'text-slate-400'}>{c.met ? '✓' : '✗'}</span>
            <span className="text-slate-700 dark:text-slate-300">
              {c.label}
              {c.required && <span className="text-slate-400"> (required)</span>}
              <span className="text-slate-500"> — {c.detail}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ChartPatternSection({
  symbol,
  bars,
  timeframe,
  onTimeframeChange,
  lookbackDays,
}: {
  symbol: string;
  bars: OHLCVBarDTO[];
  timeframe: TimeframeId;
  onTimeframeChange: (id: TimeframeId) => void;
  lookbackDays: number;
}) {
  const [selected, setSelected] = useState(0);
  const detection = useMutation<ChartPatternAnalysis>({
    // The endpoint accepts 60–2000 sessions; short chart timeframes are widened
    // to the shortest history a formation can occupy rather than rejected.
    mutationFn: () => detectChartPatterns(symbol, Math.min(2000, Math.max(60, lookbackDays)), 5),
    onSuccess: () => setSelected(0),
  });

  const analysis = detection.data;
  const shown = analysis?.patterns[selected];

  const overlayLines = useMemo<ChartOverlayLine[]>(
    () =>
      (shown?.geometry ?? []).map((line, i) => ({
        color: GEOMETRY_COLORS[i % GEOMETRY_COLORS.length],
        points: line.points.map((p) => ({ date: p.bar_date, price: parseFloat(p.price) })),
      })),
    [shown]
  );

  return (
    <Card
      title="Chart patterns"
      subtitle="Classical formations, detected only when you ask for them"
      badge={
        analysis
          ? {
              text: `${analysis.patterns.length} candidate${analysis.patterns.length === 1 ? '' : 's'}`,
              color: 'bg-slate-100 text-slate-600 dark:bg-slate-700/60 dark:text-slate-300',
            }
          : undefined
      }
    >
      <div className="space-y-4">
        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => detection.mutate()}
            disabled={detection.isPending}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-60 ${focusRing}`}
          >
            {detection.isPending ? 'Detecting…' : 'Detect patterns'}
          </button>
          <span className="text-xs text-slate-500">
            {analysis
              ? `Analysed ${analysis.bars_analyzed} bars up to ${analysis.as_of ?? '—'} at a ${parseFloat(analysis.threshold_pct)}% pivot threshold.`
              : 'Nothing is computed until you click.'}
          </span>
        </div>

        {detection.error && (
          <p className="text-xs text-rose-600 dark:text-rose-400">
            Pattern detection for {symbol} could not be completed.
          </p>
        )}

        {analysis && analysis.patterns.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">
            No clear pattern detected.
          </p>
        )}

        {analysis && analysis.patterns.length > 1 && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            More than one formation fits this price action. Select a candidate to draw its
            geometry — these are alternative readings of the same bars, not confirmations of
            each other.
          </p>
        )}

        {analysis && (
          <div className="space-y-2">
            {analysis.patterns.map((pattern, i) => (
              <PatternCandidate
                key={`${pattern.pattern}-${pattern.starts_on}`}
                pattern={pattern}
                selected={i === selected}
                onSelect={() => setSelected(i)}
              />
            ))}
          </div>
        )}

        {shown && (
          <div>
            <PriceChart
              bars={bars}
              timeframe={timeframe}
              onTimeframeChange={onTimeframeChange}
              height={320}
              overlayLines={overlayLines}
              footnote={`${shown.display_name} geometry: ${shown.geometry.map((g) => g.name).join(', ')}. Widen the timeframe if part of the formation falls outside the visible range.`}
            />
          </div>
        )}

        {analysis?.notes.length ? (
          <ul className="space-y-1">
            {analysis.notes.map((note) => (
              <li key={note} className="text-xs text-slate-500">
                · {note}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </Card>
  );
}

export function PatternCard({
  explanation,
  symbol,
  bars,
  timeframe,
  onTimeframeChange,
  lookbackDays,
}: {
  explanation: StockExplanation;
  symbol: string;
  bars: OHLCVBarDTO[];
  timeframe: TimeframeId;
  onTimeframeChange: (id: TimeframeId) => void;
  lookbackDays: number;
}) {
  const patternRules = explanation.rule_explanations.filter((r) => r.engine_name === 'pattern');
  const breakoutRules = explanation.rule_explanations.filter((r) => r.engine_name === 'breakout');

  return (
    <div className="space-y-6">
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
      <ChartPatternSection
        symbol={symbol}
        bars={bars}
        timeframe={timeframe}
        onTimeframeChange={onTimeframeChange}
        lookbackDays={lookbackDays}
      />
    </div>
  );
}
