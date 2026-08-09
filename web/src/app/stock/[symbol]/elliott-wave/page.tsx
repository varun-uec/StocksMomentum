'use client';

/**
 * Phase 7 — Elliott Wave Analysis screen.
 *
 * Every label and pivot comes from `GET /stocks/{symbol}/elliott-wave`; nothing
 * is computed or inferred here. This screen annotates a chart. It produces no
 * buy/sell verdict, no price objective and no score.
 */

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { LineStyle } from 'lightweight-charts';
import { getElliottWave, getOhlcv } from '@/lib/api-client';
import { Card, Badge, LoadingSpinner, ErrorMessage, PageHeader } from '@/components/shared/Card';
import {
  PriceChart,
  TIMEFRAMES,
  type ChartMarker,
  type ChartOverlayLine,
  type TimeframeId,
} from '@/components/stock/PriceChart';
import { focusRing } from '@/lib/theme';
import type { ElliottWaveCount } from '@/lib/types';

const MAX_LOOKBACK_DAYS = 2000;
const PRIMARY_COLOR = '#a855f7';
const ALTERNATIVE_COLOR = '#0ea5e9';
// Lower-opacity variants of the active count colour, so subdivisions read as
// one finer degree deeper than the primary count at a glance.
const PRIMARY_SUBDIVISION_COLOR = 'rgba(168, 85, 247, 0.45)';
const ALTERNATIVE_SUBDIVISION_COLOR = 'rgba(14, 165, 233, 0.45)';

function lookbackDaysFor(timeframe: TimeframeId): number {
  return TIMEFRAMES.find((t) => t.id === timeframe)?.days ?? MAX_LOOKBACK_DAYS;
}

function fromDateFor(timeframe: TimeframeId): string | undefined {
  const days = TIMEFRAMES.find((t) => t.id === timeframe)?.days;
  if (!days) return undefined;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function CountSummary({
  count,
  color,
  showSubwaves,
}: {
  count: ElliottWaveCount;
  color: string;
  showSubwaves: boolean;
}) {
  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500">Current position</div>
        <div className="text-lg font-semibold" style={{ color }}>
          {count.current_position}
        </div>
        <div className="text-xs text-slate-500 mt-1">
          {count.pattern === 'impulse' ? 'Impulse (1-5)' : 'Correction (A-B-C)'} ·{' '}
          {count.direction === 'up' ? 'upward' : 'downward'} · {count.degree} degree
        </div>
      </div>
      {showSubwaves && count.subdivisions.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
            Finer-degree structure (parenthesised on the chart)
          </div>
          <ul className="space-y-1">
            {count.subdivisions.map((subdivision) => (
              <li key={subdivision.of_label} className="ml-3 text-xs text-slate-600 dark:text-slate-400">
                <span style={{ color }}>
                  Wave {subdivision.of_label}
                </span>{' '}
                · {subdivision.degree} degree ·{' '}
                {subdivision.labels
                  .filter((l) => l.label !== '0')
                  .map((l) => `(${l.label})`)
                  .join(' ')}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!count.is_current && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          This structure ended before the latest confirmed pivot, so it describes history
          rather than the structure now in progress.
        </p>
      )}
      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">Rules applied</div>
        <ul className="space-y-1">
          {count.rules_applied.map((rule) => (
            <li key={rule} className="text-xs text-slate-600 dark:text-slate-400">
              · {rule}
            </li>
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
  const [timeframe, setTimeframe] = useState<TimeframeId>('1Y');
  const [thresholdPct, setThresholdPct] = useState(5);
  const [showAlternative, setShowAlternative] = useState(false);
  const [showSubwaves, setShowSubwaves] = useState(false);

  const { data: ohlcv, isLoading: ohlcvLoading } = useQuery({
    queryKey: ['stock-ohlcv', symbol, timeframe],
    queryFn: () => getOhlcv(symbol, fromDateFor(timeframe)),
    enabled: !!symbol,
  });

  const {
    data: analysis,
    isLoading: waveLoading,
    error: waveError,
  } = useQuery({
    queryKey: ['elliott-wave', symbol, timeframe, thresholdPct],
    queryFn: () => getElliottWave(symbol, lookbackDaysFor(timeframe), thresholdPct),
    enabled: !!symbol,
  });

  const shownCount = showAlternative ? (analysis?.alternative ?? null) : (analysis?.primary ?? null);
  const color = showAlternative ? ALTERNATIVE_COLOR : PRIMARY_COLOR;
  const subdivisionColor = showAlternative
    ? ALTERNATIVE_SUBDIVISION_COLOR
    : PRIMARY_SUBDIVISION_COLOR;

  const markers = useMemo<ChartMarker[]>(() => {
    const parentMarkers: ChartMarker[] = (shownCount?.labels ?? [])
      .filter((l) => l.label !== '0')
      .map((l) => ({
        date: l.bar_date,
        text: l.label,
        position: shownCount?.direction === 'up' ? 'aboveBar' : 'belowBar',
        color,
      }));
    if (!showSubwaves || !shownCount) return parentMarkers;
    const subdivisionMarkers: ChartMarker[] = shownCount.subdivisions.flatMap((subdivision) =>
      subdivision.labels
        .filter((l) => l.label !== '0')
        .map((l) => ({
          date: l.bar_date,
          text: `(${l.label})`,
          position: shownCount.direction === 'up' ? 'aboveBar' : 'belowBar',
          color: subdivisionColor,
          size: 0.7,
        }))
    );
    return [...parentMarkers, ...subdivisionMarkers];
  }, [shownCount, color, subdivisionColor, showSubwaves]);

  const overlayLine = useMemo(
    () =>
      (shownCount?.labels ?? []).map((l) => ({
        date: l.bar_date,
        price: parseFloat(l.price),
        color,
      })),
    [shownCount, color]
  );

  const overlayLines = useMemo<ChartOverlayLine[]>(() => {
    if (!showSubwaves || !shownCount) return [];
    return shownCount.subdivisions.map((subdivision) => ({
      points: subdivision.labels.map((l) => ({
        date: l.bar_date,
        price: parseFloat(l.price),
      })),
      color: subdivisionColor,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
    }));
  }, [shownCount, subdivisionColor, showSubwaves]);

  if (!symbol) return <ErrorMessage message="No symbol supplied." />;

  const backHref = `/stock/${symbol}${strategyQuery ? `?strategy=${strategyQuery}` : ''}`;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader title={`${symbol} — Elliott Wave Analysis`} subtitle="Labelled wave count over the stored daily price history">
        {analysis?.primary && (
          <Badge color="indigo">{analysis.primary.degree} degree</Badge>
        )}
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
          <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
            Pivot reversal threshold
            <input
              type="range"
              min={2}
              max={20}
              step={1}
              value={thresholdPct}
              onChange={(e) => setThresholdPct(Number(e.target.value))}
              className="accent-indigo-500"
            />
            <span className="tabular-nums font-semibold">{thresholdPct}%</span>
          </label>
          {analysis?.alternative && (
            <button
              type="button"
              onClick={() => setShowAlternative((v) => !v)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-300 dark:border-slate-700 ${focusRing}`}
              style={{ color }}
            >
              {showAlternative ? 'Show primary count' : 'Show alternative count'}
            </button>
          )}
          {shownCount && (
            <button
              type="button"
              onClick={() => setShowSubwaves((v) => !v)}
              disabled={shownCount.subdivisions.length === 0}
              title={
                shownCount.subdivisions.length === 0
                  ? 'No leg of this count contains enough confirmed pivots to label a finer degree.'
                  : undefined
              }
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-300 dark:border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed ${focusRing}`}
            >
              {showSubwaves ? 'Hide subwaves' : 'Show subwaves'}
            </button>
          )}
        </div>

        <Card>
          <PriceChart
            bars={ohlcv?.bars ?? []}
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
            isLoading={ohlcvLoading}
            height={620}
            markers={markers}
            overlayLine={overlayLine}
            overlayLines={overlayLines}
            footnote={
              shownCount
                ? `${showAlternative ? 'Alternative' : 'Primary'} count spans ${shownCount.labels[0].bar_date} to ${shownCount.labels[shownCount.labels.length - 1].bar_date} (${shownCount.degree} degree), within ${analysis?.bars_analyzed ?? 0} bars analysed; ${analysis?.pivots.length ?? 0} confirmed pivots at a ${thresholdPct}% reversal threshold.`
                : `${analysis?.pivots.length ?? 0} confirmed pivots at a ${thresholdPct}% reversal threshold.`
            }
          />
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card
            title={showAlternative ? 'Alternative count' : 'Primary count'}
            subtitle={
              analysis?.alternative
                ? 'The pivots support two valid counts; both are shown, neither is preferred.'
                : undefined
            }
          >
            {waveLoading && <LoadingSpinner text="Labelling the wave structure…" />}
            {waveError && (
              <ErrorMessage message={`The wave analysis for ${symbol} could not be loaded.`} />
            )}
            {!waveLoading && !waveError && !shownCount && (
              <p className="text-xs text-slate-500">
                No count is asserted at this threshold.
              </p>
            )}
            {shownCount && (
              <CountSummary count={shownCount} color={color} showSubwaves={showSubwaves} />
            )}
          </Card>

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
                    <tr key={`${p.bar_date}-${p.kind}`} className="border-t border-slate-200 dark:border-slate-800">
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
    </div>
  );
}
