/**
 * Workspace (ui-ux doc 03 §08): research that compounds. Records live on this
 * machine's Wickstreet server (W1) and survive a restart. Every save names the
 * version it read; a save that lost a race says so and keeps the draft.
 * Alerts need an evaluator service (W2) and show as planned, never "active".
 */
import { useMutation, useQueries, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { mfApi, type CalculatorKind, type CalculatorRequest } from '../api';
import { WatchButton } from '../components/CompareTray';
import { FundRow } from '../components/FundRow';
import { FundSearch } from '../components/FundSearch';
import { I } from '../components/icons';
import { Badge, Button, Delta, DependencyPanel, EmptyState, ErrorState, Field, Loading, PageHeader, TabLinks, buttonClass, cx, inputClass, useTitle } from '../components/ui';
import { categoryShort, date, inr, pct, schemeName } from '../format';
import { EXAMPLES, useRecentFunds } from '../context';
import { useFields, useMetrics } from '../queries';
import { scenarioHref, type ScenarioProvenance } from '../scenario';
import { describe, encodeView, type ScreenView } from '../view-spec';
import { isConflict, saveToggle, useDraft, useDraftIds, useRecordMutations, useRecords, type NoteBody, type RecordKind, type ResearchRecord, type WatchlistBody } from '../workspace';

const TABS = [
  { id: 'watchlists', label: 'Watchlists', kind: 'watchlist' },
  { id: 'screens', label: 'Saved screens', kind: 'screen' },
  { id: 'notes', label: 'Notes', kind: 'note' },
  { id: 'scenarios', label: 'Scenarios', kind: 'scenario' },
  { id: 'alerts', label: 'Alerts', kind: null },
] as const;
type TabId = (typeof TABS)[number]['id'];

/**
 * A failed save keeps the draft. A conflict shows the other window's version and
 * offers a copy of yours; only an explicit choice replaces your draft (audit A-09).
 */
function SaveError({ error, onReload, draft, theirs, what = 'text', onRetry }: { error: unknown; onReload: () => void; draft?: string; theirs?: string; what?: string; onRetry?: () => void }) {
  const [copied, setCopied] = useState(false);
  if (!error) return null;
  if (isConflict(error))
    return (
      <div role="alert" className="space-y-2 rounded-[10px] bg-mf-warning-soft p-3 text-sm text-mf-warning">
        <p>Another window saved this record first, so your change was not saved. Your {what} is still here.</p>
        {theirs !== undefined && (
          <p className="text-mf-ink-soft">
            Their version: <q className="break-words">{theirs.length > 140 ? `${theirs.slice(0, 140)}…` : theirs}</q>
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {draft !== undefined && (
            <Button
              size="sm"
              onClick={() =>
                navigator.clipboard?.writeText(draft).then(
                  () => setCopied(true),
                  () => setCopied(false),
                )
              }
            >
              {copied ? 'Copied' : `Copy my ${what}`}
            </Button>
          )}
          {onRetry && (
            <Button size="sm" variant="primary" onClick={onRetry}>
              Save mine over theirs
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={onReload}>
            Use their version{draft !== undefined ? ` (discards my ${what})` : ''}
          </Button>
        </div>
      </div>
    );
  return (
    <div className="space-y-2">
      <ErrorState error={error} compact title={`Could not save. Your ${what} is kept.`} onRetry={onRetry} />
    </div>
  );
}

function RecordList<B>({ records, selected, onSelect, empty }: { records: ResearchRecord<B>[]; selected?: string; onSelect: (id: string) => void; empty: string }) {
  const drafted = useDraftIds();
  if (!records.length) return <p className="px-2 py-6 text-sm text-mf-muted">{empty}</p>;
  return (
    <ul className="space-y-1">
      {records.map((r) => (
        <li key={r.id}>
          <button type="button" onClick={() => onSelect(r.id)} aria-current={r.id === selected ? 'true' : undefined} className={cx('w-full rounded-[10px] px-3 py-2.5 text-left', r.id === selected ? 'bg-mf-brand-soft' : 'hover:bg-mf-sunken')}>
            <p className="truncate text-sm font-medium">{r.name}</p>
            <p className="flex items-center gap-1.5 text-xs text-mf-muted">
              Saved {date(r.updated_at)} · v{r.version}
              {drafted.has(r.id) && <Badge tone="warning">Unsaved draft</Badge>}
            </p>
          </button>
        </li>
      ))}
    </ul>
  );
}

function Header<B>({ record, kind, extra, status }: { record: ResearchRecord<B>; kind: RecordKind; extra?: React.ReactNode; status?: React.ReactNode }) {
  const { save } = useRecordMutations<B>(kind);
  // The proposed name lives in the draft store, so a refetch after a conflict cannot replace it.
  const [name, setName, discard] = useDraft(`${record.id}:name`, record.name);
  const dirty = name.trim() !== record.name;
  const rename = () => save.mutate({ record, draft: { name: name.trim(), body: record.body } }, { onSuccess: discard });
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Name" className="min-w-0 flex-1">
          <input className={inputClass} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
        </Field>
        {dirty && (
          <Button variant="primary" disabled={!name.trim() || save.isPending} onClick={rename}>
            Rename
          </Button>
        )}
        {extra}
        <Button variant="danger" disabled={save.isPending} onClick={() => save.mutate({ record, draft: { name: record.name, body: record.body, archived: !record.archived } })}>
          {record.archived ? 'Restore' : 'Archive'}
        </Button>
      </div>
      <p className="text-xs text-mf-muted" aria-live="polite">
        {save.isPending ? 'Saving…' : status ?? (dirty ? `Unsaved name · last saved version ${record.version}` : `Saved · version ${record.version} · ${date(record.updated_at)}`)}
      </p>
      <SaveError
        error={save.error}
        what="name"
        draft={dirty ? name : undefined}
        theirs={isConflict(save.error) ? record.name : undefined}
        onRetry={dirty && name.trim() ? () => { save.reset(); rename(); } : undefined}
        onReload={() => { save.reset(); discard(); }}
      />
    </div>
  );
}

function WatchlistDetail({ record }: { record: ResearchRecord<WatchlistBody> }) {
  const client = useQueryClient();
  const toggle = useMutation({
    mutationFn: ({ code, on }: { code: string; on: boolean }) => saveToggle(record, code, on),
    onSettled: () => client.invalidateQueries({ queryKey: ['mf', 'workspace'] }),
  });
  const codes = record.body.codes ?? [];
  const metrics = useQueries({ queries: codes.map((code) => ({ queryKey: ['mf', 'fund', code, 'metrics'], queryFn: ({ signal }: { signal: AbortSignal }) => mfApi.metrics(code, signal), staleTime: 300_000 })) });
  const failed = toggle.isError ? toggle.variables : undefined;
  const status = failed ? `Not saved: ${failed.on ? 'adding' : 'removing'} AMFI ${failed.code} · last saved version ${record.version}` : undefined;
  return (
    <div className="space-y-5">
      <Header record={record} kind="watchlist" status={status} extra={codes.length >= 2 && codes.length <= 5 && <Link className={buttonClass('secondary')} to={`/mf/compare?${codes.map((c) => `code=${c}`).join('&')}`}>Compare all</Link>} />
      {failed && <ErrorState error={toggle.error} compact title={`Could not ${failed.on ? 'add' : 'remove'} AMFI ${failed.code}. The list below is the last saved version.`} onRetry={() => toggle.mutate(failed)} />}
      <FundSearch label="Add a fund to this watchlist" placeholder="Add a fund" onPick={(f) => toggle.mutate({ code: f.amfi_code, on: true })} />
      {codes.length === 0 ? (
        <p className="text-sm text-mf-muted">No funds yet. Add one above, or star a fund on its page.</p>
      ) : (
        <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="text-xs text-mf-muted">
              <tr className="border-b border-mf-line">
                {['Fund', '1Y', '3Y CAGR', 'Max drawdown 3Y', 'Score', ''].map((h, i) => <th key={i} scope="col" className={cx('py-2 font-medium', i === 0 ? 'text-left' : 'text-right')}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {codes.map((code, i) => {
                const m = metrics[i].data;
                return (
                  <tr key={code} className="border-b border-mf-line last:border-0">
                    <th scope="row" className="py-2.5 text-left font-normal">
                      <Link to={`/mf/funds/${code}`} className="font-medium hover:text-mf-brand-strong">{m ? schemeName(m.name) : `AMFI ${code}`}</Link>
                      {m && <p className="text-xs text-mf-muted">{categoryShort(String(m.values.category))}</p>}
                    </th>
                    <td className="py-2.5 text-right"><Delta value={m?.values.ret_1y} /></td>
                    <td className="py-2.5 text-right tabular">{pct(m?.values.cagr_3y)}</td>
                    <td className="py-2.5 text-right tabular text-mf-loss">{pct(m?.values.mdd_3y)}</td>
                    <td className="py-2.5 text-right tabular">{typeof m?.values.score === 'number' ? Math.round(m.values.score) : '—'}</td>
                    <td className="py-2.5 text-right">
                      <Button size="sm" variant="ghost" aria-label={`Remove ${m?.name ?? code}`} disabled={toggle.isPending} onClick={() => toggle.mutate({ code, on: false })}>
                        <I.x className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ScreenDetail({ record }: { record: ResearchRecord<{ view: ScreenView; preset?: string }> }) {
  const fields = useFields();
  const view = record.body.view;
  return (
    <div className="space-y-5">
      <Header record={record} kind="screen" extra={<Link className={buttonClass('primary')} to={`/mf/screen?screen=${record.id}&v=${encodeView(view)}`}>Open screen</Link>} />
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-mf-muted">Match {view.mode === 'all' ? 'all' : 'any'} of</p>
        <ul className="flex flex-wrap gap-2">
          {view.conditions.map((c, i) => <li key={i}><Badge tone="neutral" className="text-[12px]">{describe(c, fields.byId, categoryShort)}</Badge></li>)}
        </ul>
      </div>
      <p className="text-sm text-mf-muted">
        Sorted by {view.sort.map((s) => `${fields.byId.get(s.field)?.label ?? s.field} (${s.dir === 'desc' ? 'high first' : 'low first'})`).join(', ')}. {view.columns.length} columns
        {Object.keys(view.formulas).length ? `, ${Object.keys(view.formulas).length} formulas` : ''}. It reruns on the latest snapshot.
      </p>
    </div>
  );
}

function NoteDetail({ record }: { record: ResearchRecord<NoteBody> }) {
  const { save } = useRecordMutations<NoteBody>('note');
  // Kept per note: opening another note and coming back finds the draft (audit A-11).
  const [text, setText, discard] = useDraft(`${record.id}:text`, record.body.text);
  const dirty = text !== record.body.text;
  const submit = () => save.mutate({ record, draft: { name: record.name, body: { ...record.body, text } } }, { onSuccess: discard });
  return (
    <div className="space-y-4">
      <Header record={record} kind="note" extra={record.body.code && <Link className={buttonClass('secondary')} to={`/mf/funds/${record.body.code}`}>Open fund</Link>} />
      <Field label="Note">
        <textarea className={`${inputClass} h-56 py-2`} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" disabled={!dirty || save.isPending} onClick={submit}>
          {save.isPending ? 'Saving…' : 'Save note'}
        </Button>
        {dirty && !save.isPending && (
          <Button variant="ghost" onClick={discard}>
            Discard changes
          </Button>
        )}
        <span className="text-xs text-mf-muted" aria-live="polite">{dirty ? 'Unsaved changes. They stay here if you open another note.' : 'Saved'}</span>
      </div>
      <SaveError
        error={save.error}
        draft={text}
        theirs={isConflict(save.error) ? record.body.text : undefined}
        onRetry={dirty ? () => { save.reset(); submit(); } : undefined}
        onReload={() => { save.reset(); discard(); }}
      />
    </div>
  );
}

function ScenarioDetail({ record }: { record: ResearchRecord<{ kind: CalculatorKind; request: CalculatorRequest; summary: Record<string, unknown>; provenance?: ScenarioProvenance }> }) {
  const b = record.body;
  const s = b.summary ?? {};
  const r = b.request;
  const saved = b.provenance;
  return (
    <div className="space-y-4">
      <Header record={record} kind="scenario" extra={<Link className={buttonClass('primary')} to={scenarioHref(b.kind, r)}>Rerun on the latest snapshot</Link>} />
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {[
          ['Kind', String(b.kind).toUpperCase()],
          ['Dates', `${date(r?.start)} – ${date(r?.end)}`],
          [b.kind === 'sip' ? 'Monthly' : 'Amount', inr(r?.amount)],
          ...(r?.day != null ? [['Day of month', String(r.day)]] : []),
          ...(r?.step_up ? [['Yearly step-up', pct(r.step_up, 0)]] : []),
          ...(r?.instalment != null ? [[b.kind === 'swp' ? 'Monthly withdrawal' : 'Monthly transfer', inr(r.instalment)]] : []),
          ['Tax class', saved?.tax_class ? `${saved.tax_class}${saved.tax_class_source === 'category' ? ' (from category)' : ''}` : r?.tax_class ?? 'from category'],
          ...(r?.slab_rate != null ? [['Slab', pct(r.slab_rate, 0)]] : []),
          ['Invested', inr(s.invested)],
          ['Value then', inr(s.value)],
          ['Gain', inr(s.gain)],
          ['XIRR', pct(s.xirr, 2)],
        ].map(([k, v]) => (
          <div key={k} className="rounded-[10px] border border-mf-line p-3">
            <dt className="text-xs text-mf-muted">{k}</dt>
            <dd className="mt-0.5 font-medium tabular">{v}</dd>
          </div>
        ))}
      </dl>
      {saved ? (
        <div className="flex flex-wrap items-center gap-3 text-xs text-mf-muted">
          <span>Ran on snapshot {saved.data_revision} · NAVs to {date(saved.as_of)} · method v{saved.method_version} · calculator v{saved.calculator_version}.</span>
          <Link className="font-medium text-mf-brand-strong hover:underline" to={scenarioHref(b.kind, r, saved.data_revision)}>Replay on that snapshot</Link>
        </div>
      ) : (
        <p className="text-xs text-mf-muted">Saved before snapshot details were kept, so it can only rerun on the latest snapshot.</p>
      )}
    </div>
  );
}

function NewRecord({ kind, label }: { kind: 'watchlist' | 'note'; label: string }) {
  const { create } = useRecordMutations<WatchlistBody | NoteBody>(kind);
  const [name, setName] = useState('');
  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) create.mutate({ name: name.trim(), body: kind === 'watchlist' ? { codes: [] } : { text: '' } }, { onSuccess: () => setName('') });
      }}
    >
      <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder={label} aria-label={label} maxLength={120} />
      <Button type="submit" variant="primary" disabled={!name.trim() || create.isPending} aria-label="Create">
        <I.plus className="h-4 w-4" />
      </Button>
    </form>
  );
}

/** An empty section starts with something useful: funds to watch, or the tool that makes this kind of record. */
function StartHere({ kind }: { kind: RecordKind | null | undefined }) {
  const recent = useRecentFunds();
  if (kind === 'watchlist') {
    const codes = recent.length ? recent.slice(0, 5) : EXAMPLES.map((e) => e.code);
    return (
      <div>
        <h2 className="font-display text-xl text-mf-ink">Start a watchlist</h2>
        <p className="mt-1 text-sm text-mf-muted">Press the star on any fund. {recent.length ? 'Funds you opened recently:' : 'Some well-known funds to start with:'}</p>
        <div className="mt-2 divide-y divide-mf-line">
          {codes.map((code) => (
            <FundRow key={code} code={code} action={<FundRowStar code={code} />} />
          ))}
        </div>
      </div>
    );
  }
  const where =
    kind === 'screen'
      ? { title: 'No saved screens yet', text: 'Open the screener, set it up, then press Save screen.', to: '/mf/screen', label: 'Open the screener' }
      : kind === 'scenario'
        ? { title: 'No saved scenarios yet', text: 'Replay a SIP, lump sum or withdrawal in the investment lab, then save it.', to: '/mf/simulate', label: 'Open the investment lab' }
        : { title: 'No notes yet', text: 'Name a new note, or press Notes on any fund page.', to: '/mf/screen', label: 'Find a fund' };
  return (
    <EmptyState title={where.title} action={<Link to={where.to} className={buttonClass('primary')}>{where.label}</Link>}>
      {where.text}
    </EmptyState>
  );
}

function FundRowStar({ code }: { code: string }) {
  const metrics = useMetrics(code);
  return metrics.data ? <WatchButton code={code} name={metrics.data.name} /> : null;
}

export default function Workspace() {
  useTitle('Your workspace');
  const [params, setParams] = useSearchParams();
  const tab = (TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'watchlists') as TabId;
  const def = TABS.find((t) => t.id === tab)!;
  const archived = params.get('archived') === '1';
  const records = useRecords(def.kind ?? undefined, archived);
  const list = def.kind ? records.data ?? [] : [];
  const selectedId = params.get('id') ?? list[0]?.id;
  const selected = list.find((r) => r.id === selectedId);
  const select = (id: string) => setParams((p) => { p.set('id', id); return p; }, { replace: true });
  // Drafts survive moving around the app, not a reload: warn before the page goes.
  const drafted = useDraftIds().size > 0;
  useEffect(() => {
    if (!drafted) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [drafted]);

  return (
    <div className="space-y-6">
      <PageHeader title="Your workspace" lead="Watchlists, saved screens, notes and scenarios. Saved on this machine's Wickstreet server, so they come back after a restart." />
      <TabLinks label="Workspace sections" active={tab} tabs={TABS.map((t) => ({ id: t.id, label: t.label, to: `?tab=${t.id}` }))} />
      {tab === 'alerts' ? (
        <div className="grid gap-4 md:grid-cols-2">
          <DependencyPanel title="Metric alerts" needs="W2, a rule evaluator that runs after each snapshot, with an event log">
            An alert such as “tell me when this fund’s 3Y drawdown is deeper than −20%” needs a service that checks each new snapshot once and records the event. Until it exists, no alert is shown as active.
          </DependencyPanel>
          <DependencyPanel title="Screen-entry and disclosure alerts" needs="W2 plus E4 holdings disclosures">
            New funds entering a saved screen, and changes in disclosed holdings, are separate rule types.
          </DependencyPanel>
        </div>
      ) : records.isError ? (
        <ErrorState error={records.error} onRetry={() => records.refetch()} />
      ) : records.isLoading ? (
        <Loading label="Loading your records" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="space-y-3">
            {(def.kind === 'watchlist' || def.kind === 'note') && !archived && <NewRecord kind={def.kind} label={def.kind === 'watchlist' ? 'New watchlist name' : 'New note title'} />}
            <RecordList records={list} selected={selected?.id} onSelect={select} empty={archived ? 'Nothing archived.' : def.kind === 'screen' ? 'Save a screen from the screener to see it here.' : def.kind === 'scenario' ? 'Save a scenario from the investment lab.' : 'Nothing here yet.'} />
            <button type="button" className="px-2 text-xs text-mf-muted underline-offset-2 hover:underline" onClick={() => setParams({ tab, ...(archived ? {} : { archived: '1' }) })}>
              {archived ? 'Show current records' : 'Show archived records'}
            </button>
          </aside>
          <section aria-label="Selected record" className="min-w-0 rounded-card border border-mf-line bg-mf-surface p-5 shadow-card">
            {!selected ? (
              list.length === 0 && !archived ? <StartHere kind={def.kind} /> : <EmptyState title="Nothing selected">Choose a record on the left, or create one.</EmptyState>
            ) : (
              <div key={selected.id}>
                {def.kind === 'watchlist' && <WatchlistDetail record={selected as unknown as ResearchRecord<WatchlistBody>} />}
                {def.kind === 'screen' && <ScreenDetail record={selected as unknown as ResearchRecord<{ view: ScreenView }>} />}
                {def.kind === 'note' && <NoteDetail record={selected as unknown as ResearchRecord<NoteBody>} />}
                {def.kind === 'scenario' && <ScenarioDetail record={selected as never} />}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
