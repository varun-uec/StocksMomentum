/**
 * Fund intelligence (ui-ux doc 03 §03): one plan-option, an honest picture.
 * `?tab=` deep-links a section; each tab mounts only when opened, so a fund page
 * fetches the reads it shows and no more.
 */
import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { CompareButton, WatchButton } from '../components/CompareTray';
import { Holdings, Profile } from '../components/fund/Profile';
import { Overview } from '../components/fund/Overview';
import { Peers } from '../components/fund/Peers';
import { Performance } from '../components/fund/Performance';
import { Risk } from '../components/fund/Risk';
import { I } from '../components/icons';
import { Badge, Button, Delta, EmptyState, ErrorState, Field, Loading, Sheet, SnapshotNote, TabLinks, buttonClass, inputClass, useTitle } from '../components/ui';
import { MfApiError } from '../api';
import { categoryShort, date, enumLabel, isNum, schemeName } from '../format';
import { useFields, useFund, useMetrics, useNavs } from '../queries';
import { useRecordMutations, useRecords, type NoteBody } from '../workspace';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'performance', label: 'Performance' },
  { id: 'risk', label: 'Risk' },
  { id: 'peers', label: 'Peers & rankings' },
  { id: 'holdings', label: 'Holdings' },
  { id: 'profile', label: 'Data & profile' },
] as const;
type Tab = (typeof TABS)[number]['id'];

function LastNav({ code }: { code: string }) {
  const navs = useNavs(code);
  const rows = navs.data?.navs.filter((r) => !r.anomaly) ?? [];
  const last = rows[rows.length - 1];
  const prev = rows[rows.length - 2];
  if (!last) return null;
  const change = prev ? Number(last.nav) / Number(prev.nav) - 1 : null;
  return (
    <div className="text-left sm:text-right">
      <p className="text-[30px] font-semibold leading-none tabular">₹{Number(last.nav).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</p>
      <p className="mt-1 text-sm">
        {isNum(change) && (
          <>
            <Delta value={change} digits={2} /> <span className="text-mf-muted">1D · </span>
          </>
        )}
        <span className="text-mf-muted">NAV {date(last.date)}</span>
      </p>
    </div>
  );
}

function NoteSheet({ open, onClose, code, name }: { open: boolean; onClose: () => void; code: string; name: string }) {
  const notes = useRecords<NoteBody>('note');
  const { create } = useRecordMutations<NoteBody>('note');
  const [text, setText] = useState('');
  const mine = (notes.data ?? []).filter((n) => n.body.code === code);
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Research notes"
      footer={
        <Button
          variant="primary"
          disabled={!text.trim() || create.isPending}
          onClick={() =>
            create.mutate(
              { name: `${schemeName(name)} · ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`, body: { text: text.trim(), code, fund: name } },
              { onSuccess: () => setText('') },
            )
          }
        >
          {create.isPending ? 'Saving…' : 'Save note'}
        </Button>
      }
    >
      <Field label={`A note on ${schemeName(name)}`} hint="Your thesis, doubts or a date to review. Saved on this machine's Wickstreet server.">
        <textarea className={`${inputClass} h-32 py-2`} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      {create.error && <div className="mt-3"><ErrorState error={create.error} compact /></div>}
      {mine.length > 0 && (
        <ul className="mt-5 space-y-3">
          {mine.map((n) => (
            <li key={n.id} className="rounded-[10px] border border-mf-line p-3">
              <p className="text-xs text-mf-muted">{date(n.updated_at)}</p>
              <p className="mt-1 whitespace-pre-wrap text-sm">{n.body.text}</p>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

export default function Fund() {
  const { code = '' } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const tab = (TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'overview') as Tab;
  const valid = /^\d{1,9}$/.test(code);
  const fund = useFund(valid ? code : undefined);
  const metrics = useMetrics(valid ? code : undefined);
  const fields = useFields();
  const [notes, setNotes] = useState(false);
  useTitle(metrics.data ? schemeName(metrics.data.name) : 'Fund');

  if (!valid || (fund.error instanceof MfApiError && fund.error.status === 404))
    return (
      <EmptyState title="We could not find that fund" action={<Link to="/mf/screen" className={buttonClass('primary')}>Open the screener</Link>}>
        No plan-option has AMFI code “{code}”. Search by name, code or ISIN at the top of the page.
      </EmptyState>
    );
  if (fund.isError || metrics.isError) return <ErrorState error={fund.error ?? metrics.error} onRetry={() => { fund.refetch(); metrics.refetch(); }} />;
  if (!fund.data || !metrics.data || !fields.data) return <Loading label="Loading the fund" />;

  const f = fund.data.fund;
  const m = metrics.data;
  const props = { code, metrics: m, fields: fields.byId };
  const status = String(m.values.status);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button type="button" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/mf/screen'))} className="inline-flex items-center gap-1.5 text-sm text-mf-muted hover:text-mf-ink">
          <I.arrowLeft className="h-4 w-4" />
          Back
        </button>
        <div className="flex flex-wrap gap-2">
          <WatchButton code={code} name={m.name} label />
          <CompareButton code={code} name={m.name} label />
          <Link to={`/mf/simulate?code=${code}`} className={buttonClass('secondary', 'sm')}>
            <I.lab className="h-4 w-4" />
            Test an investment
          </Link>
          <Button size="sm" onClick={() => setNotes(true)}>
            <I.note className="h-4 w-4" />
            Notes
          </Button>
        </div>
      </div>

      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="font-display text-[28px] leading-tight sm:text-[36px]">{schemeName(m.name)}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-mf-muted">
            <span className="font-medium text-mf-ink-soft">{categoryShort(f.category)}</span>
            <span aria-hidden="true">·</span>
            <span>{String(m.values.asset_class)}</span>
            <span aria-hidden="true">·</span>
            <span>
              {enumLabel(String(m.values.plan))} · {enumLabel(String(m.values.option))}
            </span>
            <span aria-hidden="true">·</span>
            <span>{f.amc}</span>
            <Badge tone={status === 'active' ? 'brand' : 'warning'}>{enumLabel(status)}</Badge>
          </p>
        </div>
        <LastNav code={code} />
      </header>

      <TabLinks label="Fund sections" active={tab} tabs={TABS.map((t) => ({ id: t.id, label: t.label, to: `?tab=${t.id}` }))} />

      <div key={tab} className="mf-rise">
        {tab === 'overview' && <Overview {...props} detail={fund.data} />}
        {tab === 'performance' && <Performance {...props} />}
        {tab === 'risk' && <Risk {...props} />}
        {tab === 'peers' && <Peers {...props} />}
        {tab === 'holdings' && <Holdings />}
        {tab === 'profile' && <Profile code={code} detail={fund.data} />}
      </div>

      <SnapshotNote asOf={m.as_of} revision={m.data_revision} method={m.method_version} extra={` · ${m.since_label}. Past performance does not predict future returns.`} />
      <NoteSheet open={notes} onClose={() => setNotes(false)} code={code} name={m.name} />
    </div>
  );
}
