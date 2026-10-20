/**
 * The side panel's alerts (FR-22, M15): a form for the open symbol and every
 * alert, fired ones first. Alerts read the chart's own series and are checked
 * after each daily sync; "Check now" runs the same check.
 */

import { Link } from 'react-router';
import { ALERTABLE_KINDS, SLOPED_KINDS } from '@/components/stock/chart-drawings';
import { useEffect, useRef, useState } from 'react';
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
import { alertBasisIsCurrent, alertEditThreshold, type AlertEditorBasis } from '@/components/workspace/alert-editor-basis';
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
export function describeAlert(a: Pick<AlertDTO, 'symbol' | 'source' | 'condition' | 'threshold' | 'interval'> & { drawing?: AlertDTO['drawing'] }): string {
  const condition = a.condition === 'enters_zone' ? 'enters zone' : a.condition === 'leaves_zone' ? 'leaves zone' : label(CONDITIONS, a.condition);
  // A sloped line has no single level: name the line, not its first anchor's price.
  const level = a.drawing && SLOPED_KINDS.has(a.drawing.kind) ? `the ${ALERT_DRAWING_NAMES[a.drawing.kind].toLowerCase()}` : parseFloat(a.threshold);
  return `${a.symbol} ${label(SOURCES, a.source)} ${condition} ${level} · ${label(INTERVALS, a.interval)}`;
}

const field = `rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-1.5 py-1 text-xs ${focusRing}`;

/** The open symbol's daily bars: the price basis alerts are entered in. */
function useAlertPrices(symbol?: string) {
  return useQuery({ queryKey: ['stock-ohlcv', symbol ?? '', '1D'], queryFn: () => getOhlcv(symbol ?? '', undefined, undefined, '1D'), enabled: !!symbol });
}

const ALERT_DRAWING_NAMES: Record<string, string> = { hline: 'Horizontal level', horizontal: 'Horizontal level', rectangle: 'Price zone', trendline: 'Trendline', ray: 'Ray', extended: 'Extended line' };

/** A request from the list to edit an alert; `n` makes a repeated click count. */
type EditRequest = { alert: AlertDTO; n: number };

/** The alert list, and a form for the context symbol. A route without a symbol shows the list only. */
export function AlertsTab({ symbol, price, drawing }: { symbol?: string; price?: number; drawing?: { id: string; n: number } }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useAlerts();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['alerts'] });
  // The form edits only the open symbol's alerts, so it shares this query.
  const prices = useAlertPrices(symbol);
  const [editRequest, setEditRequest] = useState<EditRequest | null>(null);
  const remove = useMutation({ mutationFn: deleteAlert, onSuccess: refresh });
  const rearm = useMutation({ mutationFn: rearmAlert, onSuccess: refresh });
  const seen = useMutation({ mutationFn: markAlertsSeen, onSuccess: refresh });
  // The panel opens on the route's symbol; "All" lists every alert (workflow 6).
  const [scope, setScope] = useState<'symbol' | 'all'>('symbol');
  const scoped = symbol && scope === 'symbol';
  const alerts = (data?.alerts ?? []).filter((a) => !scoped || a.symbol === symbol);

  // Opening the list is seeing it.
  const unseen = data?.unseen ?? 0;
  useEffect(() => {
    if (unseen > 0 && !seen.isPending) seen.mutate();
  }, [unseen]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="text-xs">
      {symbol ? <AlertForm symbol={symbol} price={price} drawing={drawing} editRequest={editRequest} /> : <p className="px-3 py-2 border-b border-slate-100 dark:border-slate-800 text-slate-500">Open a chart or a symbol page to create an alert.</p>}
      {(remove.isError || rearm.isError) && <p role="alert" className="px-3 py-1 text-rose-600">The action failed. Try again. {String((remove.error ?? rearm.error)?.message ?? '')}</p>}
      {isLoading && <p className="px-3 py-2 text-slate-500">Loading alerts…</p>}
      {symbol && (
        <div role="group" aria-label="Alert scope" className="px-3 pt-2 flex gap-1">
          {(['symbol', 'all'] as const).map((s) => (
            <button key={s} type="button" aria-pressed={scope === s} onClick={() => setScope(s)} className={`px-2 py-0.5 rounded-md ${focusRing} ${scope === s ? 'bg-[var(--ws-muted)] font-semibold' : 'text-slate-500 hover:bg-[var(--ws-muted)]'}`}>
              {s === 'symbol' ? 'This symbol' : 'All'}
            </button>
          ))}
        </div>
      )}
      {data && data.alerts.length === 0 && <p className="px-3 py-2 text-slate-500">No alerts yet.</p>}
      {data && data.alerts.length > 0 && alerts.length === 0 && <p className="px-3 py-2 text-slate-500">No alerts for {symbol}. Choose All to see the other {data.alerts.length}.</p>}
      <div className="px-3 pt-3 pb-1 flex justify-between text-[10px] uppercase tracking-wider text-slate-500"><span>Armed · {alerts.filter((a) => a.status === 'active').length}</span><span>History · {alerts.filter((a) => a.status === 'triggered').length}</span></div>
      <ul aria-label="Alerts">
        {alerts.map((a) => (
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
              {a.symbol !== symbol && <Link to={`/chart/${encodeURIComponent(a.symbol)}`} className={`text-indigo-700 dark:text-indigo-300 ${focusRing}`}>Open chart</Link>}
              {a.status === 'active' && <button disabled={!prices.data || a.symbol !== symbol} title={a.symbol !== symbol ? 'Open this symbol to edit its alert in the correct price basis' : 'Edit armed condition'} type="button" className={`text-indigo-700 dark:text-indigo-300 ${focusRing}`} onClick={() => setEditRequest((r) => ({ alert: a, n: (r?.n ?? 0) + 1 }))}>Edit</button>}
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

/** New and edited alerts for one symbol. It owns the symbol's drawings, so it mounts only with a symbol. */
function AlertForm({ symbol, price, drawing, editRequest }: { symbol: string; price?: number; drawing?: { id: string; n: number }; editRequest: EditRequest | null }) {
  const queryClient = useQueryClient();
  const { data } = useAlerts();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['alerts'] });
  const [editing, setEditing] = useState<AlertDTO | null>(null);
  const [drawingId, setDrawingId] = useState('');
  const [notice, setNotice] = useState('');
  const drawingDocument = useSymbolDrawings(symbol);
  const drawings = drawingDocument.drawings.filter((d) => ALERTABLE_KINDS.has(d.kind));
  const prices = useAlertPrices(symbol);
  const currentVersionRef = useRef(prices.data?.data_version);
  currentVersionRef.current = prices.data?.data_version;
  const [basis, setBasis] = useState<AlertEditorBasis | null>(null);
  const linked = drawings.find((d) => d.id === drawingId);
  const rectangle = linked?.kind === 'rectangle';
  const sloped = !!linked && SLOPED_KINDS.has(linked.kind);
  const [source, setSource] = useState<CreateAlertRequest['source']>('close');
  const [condition, setCondition] = useState<CreateAlertRequest['condition']>('crosses_above');
  const [interval, setBarInterval] = useState<NonNullable<CreateAlertRequest['interval']>>('1D');
  const [threshold, setThreshold] = useState(price !== undefined ? price.toFixed(2) : '');

  useEffect(() => { setEditing(null); setDrawingId(''); setCondition('crosses_above'); setNotice(''); setBasis(null); }, [symbol]);

  // A price picked on the chart fills a close alert.
  useEffect(() => {
    if (price === undefined) return;
    setEditing(null);
    setDrawingId('');
    setCondition('crosses_above');
    setSource('close');
    setThreshold(price.toFixed(2));
    setBasis(currentVersionRef.current ? { symbol, version: currentVersionRef.current } : null);
  }, [price, symbol]);

  // "Alert on this line…" from the drawing menu picks the drawing.
  useEffect(() => {
    if (!drawing) return;
    const kind = drawingDocument.drawings.find((d) => d.id === drawing.id)?.kind;
    setEditing(null);
    setDrawingId(drawing.id);
    setCondition(kind === 'rectangle' ? 'leaves_zone' : 'crosses_above');
    setNotice('');
  }, [drawing]); // eslint-disable-line react-hooks/exhaustive-deps

  const startEditing = (alert: AlertDTO) => {
    if (!prices.data || alert.symbol !== symbol) return;
    setEditing(alert);
    setSource(alert.source);
    setCondition(alert.condition);
    setBarInterval(alert.interval);
    setThreshold(alertEditThreshold(alert, prices.data.adjustments));
    setDrawingId(alert.drawing?.id ?? '');
    setBasis({ symbol: alert.symbol, version: prices.data.data_version });
    setNotice('');
  };
  useEffect(() => { if (editRequest) startEditing(editRequest.alert); }, [editRequest]); // eslint-disable-line react-hooks/exhaustive-deps

  const create = useMutation({ mutationFn: createAlert, onError: () => { queryClient.invalidateQueries({ queryKey: ['stock-ohlcv'] }); }, onSuccess: () => { refresh(); setNotice('Alert armed. It will check future completed bars.'); } });
  const edit = useMutation({ onError: () => { refresh(); queryClient.invalidateQueries({ queryKey: ['stock-ohlcv'] }); }, mutationFn: ({ alert, body }: { alert: AlertDTO; body: CreateAlertRequest }) => editAlert(alert.id, { ...body, expected_revision: alert.revision }), onSuccess: () => { refresh(); setEditing(null); setDrawingId(''); setCondition('crosses_above'); setNotice('Alert updated and re-armed from the latest stored session.'); } });
  const check = useMutation({ mutationFn: evaluateAlerts, onSuccess: refresh });

  const drawingSaved = drawingDocument.status === 'saved' && drawingDocument.revision !== null;
  const basisCurrent = alertBasisIsCurrent(basis, editing?.symbol ?? symbol, prices.data?.data_version);
  const scalarEntered = !drawingId && threshold.trim() !== '';
  const valid = (!!linked && drawingSaved) || (scalarEntered && basisCurrent && Number.isFinite(Number(threshold)));
  const conditions = rectangle ? [{ id: 'enters_zone' as const, label: 'enters zone' }, { id: 'leaves_zone' as const, label: 'leaves zone' }] : linked ? CONDITIONS.filter((c) => c.id.startsWith('crosses')) : CONDITIONS;

  return (
    <form
      aria-label={editing ? 'Edit alert' : 'New alert'}
      className="px-3 py-2 space-y-1.5 border-b border-slate-100 dark:border-slate-800"
      onSubmit={(e) => {
        e.preventDefault();
        if (!valid) return;
        const body = { symbol: editing?.symbol ?? symbol, source: linked ? 'close' as const : source, condition, interval: linked ? '1D' as const : interval, threshold: linked ? '0' : threshold, drawing_id: drawingId || null, expected_drawing_revision: linked ? drawingDocument.revision : undefined, expected_data_version: linked ? prices.data?.data_version : basis?.version };
        if (editing) edit.mutate({ alert: editing, body }); else create.mutate(body);
      }}
    >
      <div className="font-medium text-slate-600 dark:text-slate-300">{editing ? 'Edit armed alert on' : 'New alert on'} {editing?.symbol ?? symbol}</div>
      <label className="flex items-center gap-2 text-slate-500">Watch
        <select aria-label="Alert drawing" value={drawingId} className={`min-w-0 flex-1 ${field}`} onChange={(e) => { const next = drawings.find((d) => d.id === e.target.value); setDrawingId(e.target.value); setCondition(next?.kind === 'rectangle' ? 'leaves_zone' : 'crosses_above'); }}>
          <option value="">Price or backend indicator</option>
          {drawings.map((d, i) => <option key={d.id} value={d.id}>{ALERT_DRAWING_NAMES[d.kind]} {i + 1} · {d.points.map((p) => p.price.toFixed(2)).join(' – ')}</option>)}
        </select>
      </label>
      {linked && !drawingSaved && <p role="status" className="text-amber-700 dark:text-amber-400">Waiting for the drawing to save before capturing its level. {drawingDocument.status === 'error' && <button type="button" onClick={drawingDocument.retry} className="underline">Retry drawing save</button>}</p>}
      {drawingId && !linked && <p role="status" className="text-amber-700 dark:text-amber-400">Original drawing unavailable. Choose a saved drawing to refresh, or a price condition.</p>}
      {linked && <p className="text-[10px] text-slate-500">Daily close {rectangle ? 'enters or leaves the inclusive price band; gaps across it count as leaving only when the previous close was inside' : sloped ? `crosses the line, compared with the line's value on each session. ${linked.kind === 'trendline' ? 'A trendline watches only the sessions between its anchors' : linked.kind === 'ray' ? 'A ray watches from its first anchor onward' : 'An extended line watches every session'}` : 'crosses the horizontal level'}. Captures the saved drawing now. Later drawing edits do not change this rule; edit the alert to refresh its snapshot.{rectangle && ' The rectangle’s date span does not limit the future price-band condition.'}</p>}
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
          onChange={(e) => { setThreshold(e.target.value); if (!basis && prices.data) setBasis({ symbol: editing?.symbol ?? symbol, version: prices.data.data_version }); }}
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
      {scalarEntered && !basisCurrent && <p role="alert" className="text-amber-700 dark:text-amber-400">
        Chart data changed or the price basis is not loaded. Your entered value is kept; review the current basis before arming.
        {editing ? <button type="button" disabled={!prices.data} className="block underline" onClick={() => startEditing(data?.alerts.find((a) => a.id === editing.id) ?? editing)}>Reload alert in current price basis</button>
          : <button type="button" disabled={!prices.data} className="block underline" onClick={() => { if (prices.data) setBasis({ symbol, version: prices.data.data_version }); }}>Use entered level in current price basis</button>}
      </p>}
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
      {check.isError && <p role="alert" className="text-rose-600">The check failed. Try again. {check.error.message}</p>}
      {create.isError && <p className="text-rose-600">Could not add the alert. {String(create.error.message)}</p>}
      <p className="text-[10px] text-slate-500">EOD only · last stored session {prices.data?.bars.at(-1)?.date ?? 'loading…'}. Checked on complete bars after the last stored session, on the values the chart draws. A price level follows later splits and bonuses.</p>
    </form>
  );
}
