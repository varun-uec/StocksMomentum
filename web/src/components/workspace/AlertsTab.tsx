/**
 * The side panel's alerts (FR-22, M15): a form for the open symbol and every
 * alert, fired ones first. Alerts read the chart's own series and are checked
 * after each daily sync; "Check now" runs the same check.
 */

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAlert,
  deleteAlert,
  evaluateAlerts,
  getAlerts,
  markAlertsSeen,
  rearmAlert,
  type AlertDTO,
  type CreateAlertRequest,
} from '@/lib/api-client';
import { focusRing } from '@/lib/theme';

const SOURCES: { id: CreateAlertRequest['source']; label: string }[] = [
  { id: 'close', label: 'Close' },
  { id: 'rsi14', label: 'RSI (14)' },
  { id: 'adx14', label: 'ADX (14)' },
  { id: 'atr14', label: 'ATR (14)' },
  { id: 'macd_line', label: 'MACD line' },
  { id: 'macd_signal', label: 'MACD signal' },
  { id: 'macd_histogram', label: 'MACD histogram' },
];
const CONDITIONS: { id: CreateAlertRequest['condition']; label: string }[] = [
  { id: 'crosses_above', label: 'crosses above' },
  { id: 'crosses_below', label: 'crosses below' },
  { id: 'above', label: 'is above' },
  { id: 'below', label: 'is below' },
];
const INTERVALS: { id: NonNullable<CreateAlertRequest['interval']>; label: string }[] = [
  { id: '1D', label: 'Daily' },
  { id: '1W', label: 'Weekly' },
  { id: '1M', label: 'Monthly' },
];
const label = <T extends string>(list: { id: T; label: string }[], id: T) => list.find((x) => x.id === id)?.label ?? id;

export function useAlerts() {
  return useQuery({ queryKey: ['alerts'], queryFn: getAlerts });
}

/** What an alert watches, in words. */
export function describeAlert(a: Pick<AlertDTO, 'symbol' | 'source' | 'condition' | 'threshold' | 'interval'>): string {
  return `${a.symbol} ${label(SOURCES, a.source)} ${label(CONDITIONS, a.condition)} ${parseFloat(a.threshold)} · ${label(INTERVALS, a.interval)}`;
}

const field = `rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-1.5 py-1 text-xs ${focusRing}`;

export function AlertsTab({ symbol, price }: { symbol: string; price?: number }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useAlerts();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['alerts'] });
  const [source, setSource] = useState<CreateAlertRequest['source']>('close');
  const [condition, setCondition] = useState<CreateAlertRequest['condition']>('crosses_above');
  const [interval, setBarInterval] = useState<NonNullable<CreateAlertRequest['interval']>>('1D');
  const [threshold, setThreshold] = useState(price !== undefined ? price.toFixed(2) : '');

  // A price picked on the chart fills a close alert.
  useEffect(() => {
    if (price === undefined) return;
    setSource('close');
    setThreshold(price.toFixed(2));
  }, [price]);

  const create = useMutation({ mutationFn: createAlert, onSuccess: refresh });
  const remove = useMutation({ mutationFn: deleteAlert, onSuccess: refresh });
  const rearm = useMutation({ mutationFn: rearmAlert, onSuccess: refresh });
  const check = useMutation({ mutationFn: evaluateAlerts, onSuccess: refresh });
  const seen = useMutation({ mutationFn: markAlertsSeen, onSuccess: refresh });

  // Opening the list is seeing it.
  const unseen = data?.unseen ?? 0;
  useEffect(() => {
    if (unseen > 0 && !seen.isPending) seen.mutate();
  }, [unseen]); // eslint-disable-line react-hooks/exhaustive-deps

  const valid = threshold.trim() !== '' && Number.isFinite(Number(threshold));

  return (
    <div className="text-xs">
      <form
        aria-label="New alert"
        className="px-3 py-2 space-y-1.5 border-b border-slate-100 dark:border-slate-800"
        onSubmit={(e) => {
          e.preventDefault();
          if (!valid) return;
          create.mutate({ symbol, source, condition, interval, threshold });
        }}
      >
        <div className="font-medium text-slate-600 dark:text-slate-300">New alert on {symbol}</div>
        <div className="flex flex-wrap gap-1">
          <select aria-label="Value" value={source} onChange={(e) => setSource(e.target.value as typeof source)} className={field}>
            {SOURCES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
          <select aria-label="Condition" value={condition} onChange={(e) => setCondition(e.target.value as typeof condition)} className={field}>
            {CONDITIONS.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <input
            aria-label="Threshold"
            inputMode="decimal"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            className={`w-20 tabular-nums ${field}`}
          />
          <select aria-label="Interval" value={interval} onChange={(e) => setBarInterval(e.target.value as typeof interval)} className={field}>
            {INTERVALS.map((i) => (
              <option key={i.id} value={i.id}>
                {i.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={!valid || create.isPending}
            className={`px-2 py-0.5 rounded-md bg-indigo-600 text-white font-medium disabled:opacity-40 ${focusRing}`}
          >
            Add alert
          </button>
          <button
            type="button"
            onClick={() => check.mutate()}
            disabled={check.isPending}
            title="The app also checks after each daily sync"
            className={`px-2 py-0.5 rounded-md border border-slate-200 dark:border-slate-700 text-slate-500 disabled:opacity-40 ${focusRing}`}
          >
            Check now
          </button>
          {check.data && (
            <span role="status" className="text-slate-500">
              {check.data.fired} of {check.data.evaluated} fired
            </span>
          )}
        </div>
        {create.isError && <p className="text-rose-600">Could not add the alert. {String(create.error.message)}</p>}
        <p className="text-[10px] text-slate-500">Checked on complete bars after the last stored session, on the values the chart draws. A price level follows later splits and bonuses.</p>
      </form>
      {isLoading && <p className="px-3 py-2 text-slate-500">Loading alerts…</p>}
      {data && data.alerts.length === 0 && <p className="px-3 py-2 text-slate-500">No alerts yet.</p>}
      <ul aria-label="Alerts">
        {data?.alerts.map((a) => (
          <li key={a.id} className="px-3 py-1.5 border-b border-slate-100 dark:border-slate-800">
            <div className={a.status === 'triggered' ? 'font-semibold' : ''}>{describeAlert(a)}</div>
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              {a.status === 'triggered' ? (
                <span title={a.data_version ? `Data version ${a.data_version}` : undefined}>
                  Fired on {a.triggered_on} at {a.trigger_value === null ? '—' : parseFloat(a.trigger_value).toFixed(2)}
                </span>
              ) : (
                <span>Watching bars after {a.armed_after}</span>
              )}
              <span className="flex-1" />
              {a.status === 'triggered' && (
                <button type="button" onClick={() => rearm.mutate(a.id)} className={`text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}>
                  Re-arm
                </button>
              )}
              <button
                type="button"
                aria-label={`Delete alert: ${describeAlert(a)}`}
                onClick={() => remove.mutate(a.id)}
                className={`text-rose-600 dark:text-rose-400 hover:underline ${focusRing}`}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
