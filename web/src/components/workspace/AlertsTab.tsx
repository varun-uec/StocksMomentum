/**
 * The side panel's alerts (FR-22, M15): a form for the open symbol and every
 * alert, fired ones first. Alerts read the chart's own series and are checked
 * after each daily sync; "Check now" runs the same check.
 */

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAlert,
  editAlert,
  deleteAlert,
  evaluateAlerts,
  getAlerts,
  getOhlcv,
  markAlertsSeen,
  rearmAlert,
  type AlertDTO,
  type CreateAlertRequest,
} from '@/lib/api-client';
import { factorAt } from '@/lib/traded-prices';
import { useSymbolDrawings } from '@/lib/workspace';
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
  return `${a.symbol} ${label(SOURCES, a.source)} ${(a.condition === 'enters_zone' ? 'enters zone' : a.condition === 'leaves_zone' ? 'leaves zone' : label(CONDITIONS, a.condition))} ${parseFloat(a.threshold)} · ${label(INTERVALS, a.interval)}`;
}

const field = `rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-1.5 py-1 text-xs ${focusRing}`;

export function AlertsTab({ symbol, price }: { symbol: string; price?: number }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useAlerts();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['alerts'] });
  const [editing, setEditing] = useState<AlertDTO | null>(null);
  const [drawingId, setDrawingId] = useState('');
  const [notice, setNotice] = useState('');
  const drawingDocument = useSymbolDrawings(editing?.symbol ?? symbol);
  const drawings = drawingDocument.drawings.filter((d) => ['hline', 'horizontal', 'rectangle'].includes(d.kind));
  const prices = useQuery({ queryKey: ['stock-ohlcv', editing?.symbol ?? symbol, '1D'], queryFn: () => getOhlcv(editing?.symbol ?? symbol, undefined, undefined, '1D') });
  const linked = drawings.find((d) => d.id === drawingId);
  const rectangle = linked?.kind === 'rectangle';
  const [source, setSource] = useState<CreateAlertRequest['source']>('close');
  const [condition, setCondition] = useState<CreateAlertRequest['condition']>('crosses_above');
  const [interval, setBarInterval] = useState<NonNullable<CreateAlertRequest['interval']>>('1D');
  const [threshold, setThreshold] = useState(price !== undefined ? price.toFixed(2) : '');

  useEffect(() => { setEditing(null); setDrawingId(''); setCondition('crosses_above'); setNotice(''); }, [symbol]);

  // A price picked on the chart fills a close alert.
  useEffect(() => {
    if (price === undefined) return;
    setEditing(null);
    setDrawingId('');
    setCondition('crosses_above');
    setSource('close');
    setThreshold(price.toFixed(2));
  }, [price]);

  const create = useMutation({ mutationFn: createAlert, onError: () => { queryClient.invalidateQueries({ queryKey: ['stock-ohlcv'] }); }, onSuccess: () => { refresh(); setNotice('Alert armed. It will check future completed bars.'); } });
  const edit = useMutation({ onError: () => { refresh(); }, mutationFn: ({ alert, body }: { alert: AlertDTO; body: CreateAlertRequest }) => editAlert(alert.id, { ...body, expected_revision: alert.revision }), onSuccess: () => { refresh(); setEditing(null); setDrawingId(''); setCondition('crosses_above'); setNotice('Alert updated and re-armed from the latest stored session.'); } });
  const remove = useMutation({ mutationFn: deleteAlert, onSuccess: refresh });
  const rearm = useMutation({ mutationFn: rearmAlert, onSuccess: refresh });
  const check = useMutation({ mutationFn: evaluateAlerts, onSuccess: refresh });
  const seen = useMutation({ mutationFn: markAlertsSeen, onSuccess: refresh });

  // Opening the list is seeing it.
  const unseen = data?.unseen ?? 0;
  useEffect(() => {
    if (unseen > 0 && !seen.isPending) seen.mutate();
  }, [unseen]); // eslint-disable-line react-hooks/exhaustive-deps

  const drawingSaved = drawingDocument.status === 'saved' && drawingDocument.revision !== null;
  const valid = (!!linked && drawingSaved) || (!drawingId && threshold.trim() !== '' && Number.isFinite(Number(threshold)));
  const conditions = rectangle ? [{ id: 'enters_zone' as const, label: 'enters zone' }, { id: 'leaves_zone' as const, label: 'leaves zone' }] : linked ? CONDITIONS.filter((c) => c.id.startsWith('crosses')) : CONDITIONS;

  return (
    <div className="text-xs">
      <form
        aria-label={editing ? 'Edit alert' : 'New alert'}
        className="px-3 py-2 space-y-1.5 border-b border-slate-100 dark:border-slate-800"
        onSubmit={(e) => {
          e.preventDefault();
          if (!valid) return;
          const body = { symbol: editing?.symbol ?? symbol, source: linked ? 'close' as const : source, condition, interval: linked ? '1D' as const : interval, threshold: linked ? '0' : threshold, drawing_id: drawingId || null, expected_drawing_revision: linked ? drawingDocument.revision : undefined, expected_data_version: prices.data?.data_version };
          if (editing) edit.mutate({ alert: editing, body }); else create.mutate(body);
        }}
      >
        <div className="font-medium text-slate-600 dark:text-slate-300">{editing ? 'Edit armed alert on' : 'New alert on'} {editing?.symbol ?? symbol}</div>
        <label className="flex items-center gap-2 text-slate-500">Watch
          <select aria-label="Alert drawing" value={drawingId} className={`min-w-0 flex-1 ${field}`} onChange={(e) => { const next = drawings.find((d) => d.id === e.target.value); setDrawingId(e.target.value); setCondition(next?.kind === 'rectangle' ? 'leaves_zone' : 'crosses_above'); }}>
            <option value="">Price or backend indicator</option>
            {drawings.map((d, i) => <option key={d.id} value={d.id}>{d.kind === 'rectangle' ? 'Price zone' : 'Horizontal level'} {i + 1} · {d.points.map((p) => p.price.toFixed(2)).join(' – ')}</option>)}
          </select>
        </label>
        {linked && !drawingSaved && <p role="status" className="text-amber-700 dark:text-amber-400">Waiting for the drawing to save before capturing its level. {drawingDocument.status === 'error' && <button type="button" onClick={drawingDocument.retry} className="underline">Retry drawing save</button>}</p>}
        {drawingId && !linked && <p role="status" className="text-amber-700 dark:text-amber-400">Original drawing unavailable. Choose a saved drawing to refresh, or a price condition.</p>}
        {linked && <p className="text-[10px] text-slate-500">Daily close {rectangle ? 'enters or leaves the inclusive price band; gaps across it count as leaving only when the previous close was inside' : 'crosses the horizontal level'}. Captures the saved drawing now. Later drawing edits do not change this rule; edit the alert to refresh its snapshot. The rectangle’s date span does not limit the future price-band condition.</p>}
        <div className="flex flex-wrap gap-1">
          <select aria-label="Value" disabled={!!linked} value={linked ? 'close' : source} onChange={(e) => setSource(e.target.value as typeof source)} className={field}>
            {SOURCES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
          <select aria-label="Condition" value={condition} onChange={(e) => setCondition(e.target.value as typeof condition)} className={field}>
            {conditions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <input
            aria-label="Threshold"
            disabled={!!linked}
            inputMode="decimal"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            className={`w-20 tabular-nums ${field}`}
          />
          <select aria-label="Interval" disabled={!!linked} value={linked ? '1D' : interval} onChange={(e) => setBarInterval(e.target.value as typeof interval)} className={field}>
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
            disabled={!valid || create.isPending || edit.isPending}
            className={`px-2 py-0.5 rounded-md bg-indigo-600 text-white font-medium disabled:opacity-40 ${focusRing}`}
          >
            {editing ? 'Save alert' : 'Add alert'}
          </button>
          {editing && <button type="button" className="workstation-button" onClick={() => { setEditing(null); setDrawingId(''); setCondition('crosses_above'); }}>Cancel edit</button>}
          <button
            type="button"
            onClick={() => { setNotice(''); check.mutate(); }}
            disabled={check.isPending}
            title="The app also checks after each daily sync"
            className={`px-2 py-0.5 rounded-md border border-slate-200 dark:border-slate-700 text-slate-500 disabled:opacity-40 ${focusRing}`}
          >
            Check now
          </button>
          {check.data && (
            <span role="status" aria-label="Alert evaluation" className="text-slate-500">
              {check.data.fired} of {check.data.evaluated} fired
            </span>
          )}
        </div>
        {notice && <p role="status" className="text-indigo-700 dark:text-indigo-300">{notice}</p>}
        {edit.isError && <p role="alert" className="text-rose-600">Could not save this alert. {edit.error.message} Reopen it to load the latest version.</p>}
        {(remove.isError || rearm.isError || check.isError) && <p role="alert" className="text-rose-600">The action failed. Try again. {String((remove.error ?? rearm.error ?? check.error)?.message ?? '')}</p>}
        {create.isError && <p className="text-rose-600">Could not add the alert. {String(create.error.message)}</p>}
        <p className="text-[10px] text-slate-500">EOD only · last stored session {prices.data?.bars.at(-1)?.date ?? 'loading…'}. Checked on complete bars after the last stored session, on the values the chart draws. A price level follows later splits and bonuses.</p>
      </form>
      {isLoading && <p className="px-3 py-2 text-slate-500">Loading alerts…</p>}
      {data && data.alerts.length === 0 && <p className="px-3 py-2 text-slate-500">No alerts yet.</p>}
      <div className="px-3 pt-3 pb-1 flex justify-between text-[10px] uppercase tracking-wider text-slate-500"><span>Armed · {data?.alerts.filter((a) => a.status === 'active').length ?? 0}</span><span>History · {data?.alerts.filter((a) => a.status === 'triggered').length ?? 0}</span></div>
      <ul aria-label="Alerts">
        {data?.alerts.map((a) => (
          <li key={a.id} className="px-3 py-1.5 border-b border-slate-100 dark:border-slate-800">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">{a.status === 'active' ? 'Armed · EOD' : 'Triggered · inactive history'}</div>
            {a.drawing && <p className="text-[10px] text-slate-500">Drawing snapshot · revision {a.drawing.revision} · {a.drawing.points.map((p) => p.price).join(' – ')}</p>}
            {!a.drawing && <span className="text-[10px] text-slate-500">Threshold in the price basis of {a.armed_after}; follows later splits and bonuses.</span>}
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
              {a.status === 'active' && <button disabled={!prices.data || a.symbol !== symbol} title={a.symbol !== symbol ? 'Open this symbol to edit its alert in the correct price basis' : 'Edit armed condition'} type="button" className={`text-indigo-700 dark:text-indigo-300 ${focusRing}`} onClick={() => { setEditing(a); setSource(a.source); setCondition(a.condition); setBarInterval(a.interval); setThreshold((Number(a.threshold) * (['rsi14', 'adx14'].includes(a.source) ? 1 : factorAt(prices.data?.adjustments ?? [], a.armed_after))).toString()); setDrawingId(a.drawing?.id ?? ''); setNotice(''); }}>Edit</button>}
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
