'use client';

/**
 * Phase 7 — Elliott Wave Analysis screen.
 *
 * Every label, pivot and projection bound comes from
 * `GET /stocks/{symbol}/elliott-wave`; nothing is computed or inferred here.
 * This screen annotates a chart. It produces no buy/sell verdict and no score.
 */

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { getElliottWave, getOhlcv } from '@/lib/api-client';
import { Card, Badge, LoadingSpinner, ErrorMessage, PageHeader } from '@/components/shared/Card';
import {
  PriceChart,
  TIMEFRAMES,
  type ChartMarker,
  type TimeframeId,
} from '@/components/stock/PriceChart';
import { focusRing } from '@/lib/theme';
import type { ElliottWaveCount } from '@/lib/types';

const MAX_LOOKBACK_DAYS = 2000;
const PRIMARY_COLOR = '#a855f7';
const ALTERNATIVE_COLOR = '#0ea5e9';

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

function CountSummary({ count, color }: { count: ElliottWaveCount; color: string }) {
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
        </div>
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

  const markers = useMemo<ChartMarker[]>(
    () =>
      (shownCount?.labels ?? [])
        .filter((l) => l.label !== '0')
        .map((l) => ({
          date: l.bar_date,
          text: l.label,
          position: shownCount?.direction === 'up' ? 'aboveBar' : 'belowBar',
          color,
        })),
    [shownCount, color]
  );

  const overlayLine = useMemo(
    () =>
      (shownCount?.labels ?? []).map((l) => ({
        date: l.bar_date,
        price: parseFloat(l.price),
        color,
      })),
    [shownCount, color]
  );

  const priceZone = useMemo(
    () =>
      shownCount?.projection
        ? {
            low: parseFloat(shownCount.projection.low),
            high: parseFloat(shownCount.projection.high),
            title: 'Projected zone',
            color,
          }
        : null,
    [shownCount, color]
  );

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
            priceZone={priceZone}
            footnote={
              shownCount
                ? `${showAlternative ? 'Alternative' : 'Primary'} count over ${analysis?.bars_analyzed ?? 0} bars; ${analysis?.pivots.length ?? 0} confirmed pivots at a ${thresholdPct}% reversal threshold. Dashed bounds mark the projected completion zone.`
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
            {shownCount && <CountSummary count={shownCount} color={color} />}
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
