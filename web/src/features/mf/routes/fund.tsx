/**
 * Fund intelligence (ui-ux doc 03 §03): one plan-option, an honest picture.
 * `?tab=` deep-links a section; each tab mounts only when opened, so a fund page
 * fetches the reads it shows and no more.
 */
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { CompareButton, WatchButton } from '../components/CompareTray';
import { FundMark } from '../components/FundMark';
import { Benchmark, FactsAndCosts } from '../components/fund/Facts';
import { Holdings } from '../components/fund/Holdings';
import { Profile } from '../components/fund/Profile';
import { FundHeadline, KeyFactsStrip, Overview } from '../components/fund/Overview';
import { Peers } from '../components/fund/Peers';
import { Performance } from '../components/fund/Performance';
import { Risk } from '../components/fund/Risk';
import { I } from '../components/icons';
import { Badge, Button, Delta, EmptyState, ErrorState, Field, Loading, Sheet, SnapshotNote, TabLinks, buttonClass, cx, inputClass, useTitle } from '../components/ui';
import { ScoreBadge } from '../components/ScoreBadge';
import { MfApiError, type Metrics } from '../api';
import { rememberFund } from '../context';
import { categoryShort, date, enumLabel, isNum, schemeName } from '../format';
import { useFields, useFund, useMetrics, useNavs, usePeers } from '../queries';
import { token } from '../theme/themes';
import { useRecordMutations, useRecords, type NoteBody } from '../workspace';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'performance', label: 'Performance' },
  { id: 'risk', label: 'Risk' },
  { id: 'peers', label: 'Peers & rankings' },
  { id: 'facts', label: 'Facts & costs' },
  { id: 'benchmark', label: 'Benchmark' },
  { id: 'holdings', label: 'Holdings' },
  { id: 'profile', label: 'Data sources' },
] as const;
type Tab = (typeof TABS)[number]['id'];

function Identity({ category, plan, option, amc, status }: { category: string; plan: string; option: string; amc: string; status: string }) {
  return (
    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-mf-muted">
      <span className="font-medium text-mf-ink-soft">{categoryShort(category)}</span>
      <span aria-hidden="true">·</span>
      <span>
        {enumLabel(plan)} · {enumLabel(option)}
      </span>
      <span aria-hidden="true" className="hidden sm:inline">·</span>
      <span className="hidden sm:inline">{amc}</span>
      <Badge tone={status === 'active' ? 'brand' : 'warning'}>{enumLabel(status)}</Badge>
    </p>
  );
}

function LastNav({ code, compact }: { code: string; compact?: boolean }) {
  const navs = useNavs(code);
  const rows = navs.data?.navs.filter((r) => !r.anomaly) ?? [];
  const last = rows[rows.length - 1];
  const prev = rows[rows.length - 2];
  if (!last) return null;
  const change = prev ? Number(last.nav) / Number(prev.nav) - 1 : null;
  return (
    <div className="text-left sm:text-right">
      <p className={cx('font-semibold leading-none tabular', compact ? 'text-lg' : 'text-[26px] sm:text-[30px]')}>₹{Number(last.nav).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</p>
      <p className={cx('mt-1', compact ? 'text-xs' : 'text-sm')}>
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

/** One click from a fund to Compare with its two largest same-category peers (assessment 25 Oct, rank 2). */
function ComparePeers({ code, metrics }: { code: string; metrics: Metrics }) {
  const { peers } = usePeers(code, metrics.values, 2);
  const label = (
    <>
      <I.layers className="h-4 w-4" />
      Compare peers
    </>
  );
  // Until the peers load, a disabled twin holds the place, so the row does not shift.
  if (!peers?.length) return <span className={cx(buttonClass('secondary', 'sm'), 'pointer-events-none opacity-50')} aria-hidden="true">{label}</span>;
  return (
    <Link
      to={`/mf/compare?${[code, ...peers.map((p) => p.amfi_code)].map((c) => `code=${c}`).join('&')}`}
      className={buttonClass('secondary', 'sm')}
      title={`With ${peers.map((p) => schemeName(p.name)).join(' and ')}, the largest ${categoryShort(String(metrics.values.category))} peers by AUM`}
    >
      {label}
    </Link>
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
  const known = !!metrics.data;
  useEffect(() => {
    if (known) rememberFund(code);
  }, [code, known]);

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

  const actions = (
    <>
      <WatchButton code={code} name={m.name} label />
      <ComparePeers code={code} metrics={m} />
      <CompareButton code={code} name={m.name} label />
      <Link to={`/mf/simulate?code=${code}`} className={buttonClass('secondary', 'sm')}>
        <I.lab className="h-4 w-4" />
        Test an investment
      </Link>
      <Button size="sm" onClick={() => setNotes(true)}>
        <I.note className="h-4 w-4" />
        Notes
      </Button>
    </>
  );

  return (
    <div className="flex flex-col gap-2.5 sm:gap-6">
      <div className="order-0 flex items-center justify-between gap-2">
        <button type="button" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/mf/screen'))} className="inline-flex min-h-10 shrink-0 items-center gap-1.5 text-sm text-mf-muted hover:text-mf-ink sm:min-h-0">
          <I.arrowLeft className="h-4 w-4" />
          Back
        </button>
        {/* One actions row at every width; on phones it scrolls sideways, so no bar covers the page. */}
        <div tabIndex={0} className="mf-scroll -mr-1 flex min-w-0 gap-2 overflow-x-auto py-1 pr-6 [mask-image:linear-gradient(to_right,black_calc(100%-1.5rem),transparent)] sm:flex-wrap sm:justify-end sm:overflow-visible sm:pr-1 sm:[mask-image:none]" role="group" aria-label="Fund actions; scroll sideways for more actions">
          {actions}
        </div>
      </div>

      {tab === 'overview' ? (
        <header className="order-1 relative overflow-hidden rounded-[20px] border border-mf-line p-3 shadow-card sm:p-6" style={{ background: `radial-gradient(420px 220px at 100% 0%, ${token('accent', 0.14)}, transparent 70%), linear-gradient(135deg, ${token('heroFrom')}, ${token('surface')} 62%)` }}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
            <div className="flex min-w-0 items-start gap-3 sm:gap-4">
              <FundMark amc={f.amc} size="lg" className="hidden sm:inline-grid" />
              <div className="min-w-0">
                <h1 className="font-display text-[24px] leading-tight sm:text-[34px]">{schemeName(m.name)}</h1>
                <Identity category={f.category} plan={String(m.values.plan)} option={String(m.values.option)} amc={f.amc} status={status} />
              </div>
            </div>
            <LastNav code={code} />
          </div>
          <FundHeadline code={code} metrics={m} />
          <div className="sm:hidden">
            <KeyFactsStrip code={code} metrics={m} />
          </div>
        </header>
      ) : (
        // Other tabs keep the identity and NAV in one strip, so their first chart sits high (audit 5.3).
        <header className="order-1 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[16px] border border-mf-line bg-mf-surface px-4 py-3 shadow-card">
          <FundMark amc={f.amc} size="md" className="hidden sm:inline-grid" />
          {/* On phones the name takes the whole first line; score and NAV wrap below it. */}
          <div className="min-w-0 flex-1 max-sm:basis-full">
            <h1 className="truncate font-display text-[20px] leading-tight sm:text-[24px]">{schemeName(m.name)}</h1>
            <Identity category={f.category} plan={String(m.values.plan)} option={String(m.values.option)} amc={f.amc} status={status} />
          </div>
          {isNum(m.values.score) && (
            <Link to="?tab=peers" className="flex items-center gap-2 text-xs text-mf-muted hover:text-mf-ink">
              <ScoreBadge score={m.values.score} />
              <span className="sr-only sm:not-sr-only">Wickstreet score</span>
            </Link>
          )}
          <LastNav code={code} compact />
        </header>
      )}

      <div className="order-2">
        <TabLinks label="Fund sections" active={tab} tabs={TABS.map((t) => ({ id: t.id, label: t.label, to: `?tab=${t.id}` }))} />
      </div>

      <div key={tab} className="order-3 mf-rise">
        {tab === 'overview' && <Overview {...props} detail={fund.data} />}
        {tab === 'performance' && <Performance {...props} />}
        {tab === 'risk' && <Risk {...props} />}
        {tab === 'peers' && <Peers {...props} />}
        {tab === 'facts' && <FactsAndCosts {...props} />}
        {tab === 'benchmark' && <Benchmark {...props} />}
        {tab === 'holdings' && <Holdings code={code} />}
        {tab === 'profile' && <Profile code={code} detail={fund.data} />}
      </div>

      <div className="order-4"><SnapshotNote asOf={m.as_of} revision={m.data_revision} method={m.method_version} extra={` · ${m.since_label}. Past performance does not predict future returns.`} /></div>
      <NoteSheet open={notes} onClose={() => setNotes(false)} code={code} name={m.name} />
    </div>
  );
}
