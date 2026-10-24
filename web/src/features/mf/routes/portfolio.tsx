/**
 * Portfolio (ui-ux doc 03 §07, Slice 6): import a CAS on this machine, preview it,
 * confirm, undo; then value, XIRR, costs, allocation, look-through holdings, overlap,
 * better-ranked alternatives and a rebalancing plan. The file and its password are
 * sent only to this machine's Wickstreet server and are never stored.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import { mfApi, type CasPreview, type PortfolioView } from '../api';
import { ShareBar, Weights } from '../components/fund/Holdings';
import { ScoreBadge } from '../components/ScoreBadge';
import { I } from '../components/icons';
import { Badge, Button, Card, Delta, EmptyState, ErrorState, Field, PageHeader, Skeleton, Stat, inputClass, useTitle } from '../components/ui';
import { startingFunds, useRecentFunds } from '../context';
import { categoryShort, date, inr, isNum, pct, schemeName } from '../format';

async function asBase64(file: File): Promise<string> {
  const buffer = new Uint8Array(await file.arrayBuffer());
  let text = '';
  for (let i = 0; i < buffer.length; i += 0x8000) text += String.fromCharCode(...buffer.subarray(i, i + 0x8000));
  return btoa(text);
}

function ImportCard({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [preview, setPreview] = useState<CasPreview | null>(null);
  const body = async () => ({ pdf_base64: await asBase64(file!), password });
  const check = useMutation({ mutationFn: async () => mfApi.previewCas(await body()), onSuccess: setPreview });
  const save = useMutation({
    mutationFn: async () => mfApi.importCas(await body()),
    onSuccess: () => {
      setPreview(null);
      setPassword('');
      onDone();
    },
  });
  const ready = !!file && password.length > 0;
  return (
    <Card title="Import a consolidated account statement" subtitle="A CAMS or KFintech CAS PDF. It is read on this machine; the file and password are never stored, only a hash of the file.">
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,14rem)_auto] sm:items-end">
        <Field label="CAS file (PDF)">
          <input className={`${inputClass} h-auto py-1.5 file:mr-3 file:rounded-control file:border-0 file:bg-mf-brand-soft file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-mf-brand-strong hover:file:bg-mf-brand hover:file:text-mf-on-brand`} type="file" accept="application/pdf,.pdf" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); }} />
        </Field>
        <Field label="Password" hint="Usually your PAN, as the statement email says.">
          <input className={inputClass} type="password" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Button disabled={!ready || check.isPending} onClick={() => check.mutate()}>
          {check.isPending ? 'Reading…' : 'Preview'}
        </Button>
      </div>
      {(check.error || save.error) && <div className="mt-3"><ErrorState error={check.error ?? save.error} compact /></div>}
      {preview && (
        <div className="mt-4 rounded-[12px] border border-mf-line p-4">
          <p className="text-sm text-mf-ink">
            {preview.cas_type.toLowerCase()} statement, {date(preview.period_from)} to {date(preview.period_to)}: {preview.transactions.toLocaleString('en-IN')} transactions in {preview.schemes.length} schemes.
            {preview.already_imported && <Badge tone="warning" className="ml-2">Already imported</Badge>}
          </p>
          <ul className="mt-3 max-h-60 space-y-1 overflow-y-auto text-sm">
            {preview.schemes.map((s) => (
              <li key={s.folio + s.scheme} className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="min-w-0 text-mf-ink-soft">{s.scheme}</span>
                <span className="text-xs text-mf-muted">
                  folio {s.folio} · {Number(s.closing_units).toLocaleString('en-IN')} units {s.known ? '' : '· not in Wickstreet data'}
                </span>
              </li>
            ))}
          </ul>
          {preview.warnings.length > 0 && <p className="mt-2 text-xs text-mf-warning">{preview.warnings.join(' ')}</p>}
          <div className="mt-3 flex gap-2">
            <Button variant="primary" disabled={save.isPending || preview.already_imported} onClick={() => save.mutate()}>
              {save.isPending ? 'Importing…' : 'Import these transactions'}
            </Button>
            <Button onClick={() => setPreview(null)}>Cancel</Button>
          </div>
        </div>
      )}
    </Card>
  );
}

/** Before a statement: what the page will show, how to get a CAS, and what works now. */
function PortfolioStart() {
  const recent = useRecentFunds();
  const start = startingFunds(recent, 5);
  const compare = `/mf/compare?${start.codes.map((c) => `code=${c}`).join('&')}`;
  return (
    <section aria-label="Get started" className="grid gap-4 lg:grid-cols-3">
      <Card title="What you will see" subtitle="Computed on this machine from your statement">
        <ul className="space-y-2 text-sm text-mf-ink-soft">
          {['Your XIRR on your own cash flows', 'Value, gain and what your expense ratios cost a year', 'Asset and category mix', 'Look-through holdings and overlap', 'Higher-ranked funds in the same categories', 'A plan to rebalance to your target mix'].map((t) => (
            <li key={t} className="flex gap-2">
              <I.check className="mt-0.5 h-4 w-4 shrink-0 text-mf-brand" />
              {t}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-mf-muted">The statement reader is tested on sample statements. Check the preview against your statement before you import.</p>
      </Card>
      <Card title="Get a detailed CAS" subtitle="Free, by email, in a few minutes">
        <ol className="space-y-2.5 text-sm text-mf-ink-soft">
          <li><b className="text-mf-ink">1.</b> Request a consolidated account statement from <a className="font-medium text-mf-brand underline-offset-2 hover:underline" href="https://www.camsonline.com" target="_blank" rel="noreferrer">CAMS</a>, <a className="font-medium text-mf-brand underline-offset-2 hover:underline" href="https://mfs.kfintech.com" target="_blank" rel="noreferrer">KFintech</a> or <a className="font-medium text-mf-brand underline-offset-2 hover:underline" href="https://www.mfcentral.com" target="_blank" rel="noreferrer">MF Central</a>.</li>
          <li><b className="text-mf-ink">2.</b> Choose the detailed statement with every transaction, for all folios, from the start.</li>
          <li><b className="text-mf-ink">3.</b> Import the PDF above with the password the statement email names.</li>
        </ol>
      </Card>
      <Card title="Start now, without a statement">
        <div className="space-y-2.5">
          <Link to={compare} className="mf-lift flex items-start gap-3 rounded-[12px] border border-mf-line p-3 hover:border-mf-brand/40">
            <I.compare className="mt-0.5 h-5 w-5 shrink-0 text-mf-brand" />
            <span>
              <span className="block text-sm font-medium text-mf-ink">Do my funds overlap?</span>
              <span className="block text-xs text-mf-muted">Compare up to five funds: returns, falls, costs and shared holdings.{start.example ? ' Starts with example funds.' : ' Starts with the funds you opened last.'}</span>
            </span>
          </Link>
          <Link to="/mf/simulate" className="mf-lift flex items-start gap-3 rounded-[12px] border border-mf-line p-3 hover:border-mf-brand/40">
            <I.lab className="mt-0.5 h-5 w-5 shrink-0 text-mf-brand" />
            <span>
              <span className="block text-sm font-medium text-mf-ink">What would my SIP have made?</span>
              <span className="block text-xs text-mf-muted">Replay a SIP, lump sum or withdrawal plan on real NAVs, with tax.</span>
            </span>
          </Link>
        </div>
      </Card>
    </section>
  );
}

function Imports({ view, onDone }: { view: PortfolioView; onDone: () => void }) {
  const undo = useMutation({ mutationFn: (id: string) => mfApi.undoImport(id), onSuccess: onDone });
  return (
    <Card title="Imports" subtitle="Each import is one batch. A line already held from an earlier statement is not added twice.">
      <ul className="divide-y divide-mf-line text-sm">
        {view.imports.map((i) => (
          <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span>
              {date(i.period_from)} – {date(i.period_to)} <span className="text-xs text-mf-muted">· {i.added} added, {i.duplicates} already held · {date(i.created_at.slice(0, 10))}</span>
            </span>
            <Button size="sm" disabled={undo.isPending} onClick={() => undo.mutate(i.id)}>Undo import</Button>
          </li>
        ))}
      </ul>
      {undo.error && <ErrorState error={undo.error} compact />}
    </Card>
  );
}

function Rebalance() {
  const [equity, setEquity] = useState(60);
  const [debt, setDebt] = useState(30);
  const other = 100 - equity - debt;
  const target = other >= 0 ? `Equity:${equity},Debt:${debt},Other:${other}` : undefined;
  const plan = useQuery({ queryKey: ['mf', 'portfolio', target], queryFn: ({ signal }) => mfApi.portfolio(target, signal), enabled: !!target });
  const rows = plan.data?.rebalance ?? [];
  return (
    <Card title="Rebalance to a target mix" subtitle="By asset class of each fund's SEBI category. Amounts are what to buy (+) or sell (−); tax and exit loads are not included.">
      <div className="grid grid-cols-3 gap-3">
        <Field label="Equity %"><input className={inputClass} type="number" min={0} max={100} value={equity} onChange={(e) => setEquity(Number(e.target.value))} /></Field>
        <Field label="Debt %"><input className={inputClass} type="number" min={0} max={100} value={debt} onChange={(e) => setDebt(Number(e.target.value))} /></Field>
        <Field label="Other %"><input className={inputClass} readOnly value={other} /></Field>
      </div>
      {other < 0 && <p className="mt-2 text-xs text-mf-loss">Equity and debt add up to more than 100%.</p>}
      {rows.length > 0 && (
        <table className="mt-4 w-full text-sm">
          <caption className="sr-only">Current and target share by asset class, and the trade</caption>
          <thead>
            <tr className="text-left text-xs text-mf-muted">
              <th scope="col" className="py-1.5 font-medium">Asset class</th>
              <th scope="col" className="py-1.5 text-right font-medium">Now</th>
              <th scope="col" className="py-1.5 text-right font-medium">Target</th>
              <th scope="col" className="py-1.5 text-right font-medium">Trade</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.asset_class} className="border-t border-mf-line/60">
                <th scope="row" className="py-1.5 text-left font-normal">{r.asset_class}</th>
                <td className="py-1.5 text-right tabular">{pct(r.current)}</td>
                <td className="py-1.5 text-right tabular">{pct(r.target)}</td>
                <td className="py-1.5 text-right tabular">{r.trade >= 0 ? '+' : '−'}{inr(Math.abs(r.trade))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function Analysis({ view }: { view: PortfolioView }) {
  const s = view.summary;
  const name = (code: string) => schemeName(view.positions.find((p) => p.code === code)?.scheme ?? code);
  const gaps = s.reconciliation.gaps;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Value" value={inr(s.value, true)} sub={`NAVs of ${date(s.as_of)}`} />
        <Stat label="Invested" value={inr(s.invested, true)} sub={`withdrawn ${inr(s.withdrawn, true)}`} />
        <Stat label="Gain" value={<Delta value={s.invested ? s.gain / s.invested : null} />} sub={inr(s.gain, true)} />
        <Stat label="XIRR" value={isNum(s.xirr) ? pct(s.xirr) : '—'} sub="your dated cash flows" help="The annual rate that makes every purchase, redemption and payout, plus today's value, net to zero." />
        <Stat label="Weighted TER" value={isNum(s.costs.weighted_ter) ? pct(s.costs.weighted_ter, 2) : '—'} sub={`${inr(s.costs.annual_cost, true)} a year`} />
        <Stat label="Saving in direct plans" value={inr(s.costs.direct_switch_saving, true)} sub={`a year · regular plans ${pct(s.costs.regular_plan_share)}`} help="What the TER gap between your regular plans and the same schemes' direct plans costs a year, at today's value. Exit loads and tax on switching are not included." />
      </div>
      {gaps.length > 0 ? (
        <p className="rounded-[12px] border border-mf-warning/40 bg-mf-warning-soft/40 p-3 text-sm">
          {gaps.length} of {s.reconciliation.checked} holdings do not match the statement&rsquo;s closing units: {gaps.map((g) => `${schemeName(g.scheme)} (ledger ${g.ledger}, statement ${g.statement})`).join('; ')}. A statement that starts after your first purchase leaves units out.
        </p>
      ) : (
        s.reconciliation.checked > 0 && <p className="text-xs text-mf-muted">All {s.reconciliation.checked} holdings match the statement&rsquo;s closing units.</p>
      )}
      <Card title="Holdings" subtitle="Valued at the latest stored NAV; XIRR on each holding's own cash flows">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <caption className="sr-only">Each holding with its value and return</caption>
            <thead>
              <tr className="border-b border-mf-line text-left text-xs text-mf-muted">
                <th scope="col" className="py-2 pr-3 font-medium">Fund</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Invested</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Value</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">XIRR</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">TER</th>
                <th scope="col" className="py-2 text-right font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {view.positions.filter((p) => p.value !== 0).map((p) => (
                <tr key={p.folio + (p.code ?? p.scheme)} className="border-b border-mf-line/60 last:border-0">
                  <td className="py-2 pr-3">
                    {p.code && p.fund ? <Link className="text-mf-ink hover:underline" to={`/mf/funds/${p.code}`}>{schemeName(p.scheme)}</Link> : <span>{p.scheme}</span>}
                    <span className="block text-[11px] text-mf-muted">
                      folio {p.folio} · {p.fund ? `${categoryShort(p.fund.category)} · ${p.fund.plan}` : 'not in Wickstreet data'}
                      {p.reconciled === false && ' · units differ from the statement'}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right tabular">{inr(p.invested, true)}</td>
                  <td className="py-2 pr-3 text-right tabular">{isNum(p.value) ? inr(p.value, true) : '—'}</td>
                  <td className="py-2 pr-3 text-right">{isNum(p.xirr) ? <Delta value={p.xirr} /> : '—'}</td>
                  <td className="py-2 pr-3 text-right tabular">{isNum(p.fund?.ter) ? pct(p.fund!.ter, 2) : '—'}</td>
                  <td className="py-2 text-right">{isNum(p.fund?.score) ? <ScoreBadge score={p.fund!.score} size="sm" /> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card title="Allocation" subtitle="Share of value by the funds' SEBI categories">
          <ShareBar label="Asset class" parts={Object.entries(s.allocation.asset_class ?? {})} />
          <div className="mt-5"><Weights rows={Object.entries(s.allocation.category ?? {}).map(([k, v]) => [categoryShort(k), v])} /></div>
        </Card>
        <Card title="What you own underneath" subtitle={`From each fund's latest portfolio; ${pct(view.look_through.coverage)} of your value has one`}>
          {view.look_through.securities.length ? (
            <>
              <ul className="space-y-1.5 text-sm">
                {view.look_through.securities.slice(0, 10).map((x) => (
                  <li key={x.isin ?? x.name} className="flex items-baseline justify-between gap-3">
                    <span className="min-w-0 truncate text-mf-ink-soft">{x.name}</span>
                    <span className="shrink-0 tabular">{pct(x.weight, 2)} <span className="text-xs text-mf-muted">via {x.funds.length} fund{x.funds.length > 1 ? 's' : ''}</span></span>
                  </li>
                ))}
              </ul>
              {Object.keys(view.look_through.market_cap).length > 0 && (
                <div className="mt-5"><ShareBar label="Market cap of the equity you own" parts={Object.entries(view.look_through.market_cap)} /></div>
              )}
            </>
          ) : (
            <p className="text-sm text-mf-muted">None of your funds has a stored portfolio yet. PPFAS and DSP are read directly; import other AMCs&rsquo; monthly files.</p>
          )}
        </Card>
      </div>
      {view.overlaps.length > 0 && (
        <Card title="Funds that own the same securities" subtitle="Weighted overlap of each pair's latest portfolios">
          <ul className="space-y-2 text-sm">
            {view.overlaps.map((o) => (
              <li key={o.a + o.b} className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-mf-ink-soft">{name(o.a)} and {name(o.b)}</span>
                <span className="tabular"><b>{pct(o.weighted_overlap)}</b> <span className="text-xs text-mf-muted">· {o.common_count} shared{o.same_month ? '' : ' · different months'}</span></span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Card title="Higher-ranked funds in the same categories" subtitle="Direct growth plans with a higher Wickstreet score. A historical ranking for your research, not a recommendation; check costs, exit loads and tax before you switch.">
        <div className="grid gap-5 md:grid-cols-2">
          {Object.entries(view.alternatives).map(([code, alts]) => (
            <div key={code}>
              <p className="text-sm font-medium text-mf-ink">{name(code)}</p>
              {alts.length ? (
                <ul className="mt-1.5 space-y-1 text-sm">
                  {alts.map((x) => (
                    <li key={x.code} className="flex items-baseline justify-between gap-2">
                      <Link className="min-w-0 truncate text-mf-ink-soft hover:underline" to={`/mf/funds/${x.code}`}>{schemeName(x.name)}</Link>
                      <span className="shrink-0 text-xs tabular text-mf-muted">score {isNum(x.score) ? Math.round(x.score) : '—'} · TER {isNum(x.ter) ? pct(x.ter, 2) : '—'}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-xs text-mf-muted">None scores higher in its category.</p>
              )}
            </div>
          ))}
        </div>
      </Card>
      <Rebalance />
    </div>
  );
}

export default function Portfolio() {
  useTitle('Portfolio');
  const client = useQueryClient();
  const view = useQuery({ queryKey: ['mf', 'portfolio', undefined], queryFn: ({ signal }) => mfApi.portfolio(undefined, signal) });
  const refresh = () => client.invalidateQueries({ queryKey: ['mf', 'portfolio'] });
  return (
    <div className="space-y-6">
      <PageHeader title="Your portfolio" lead="What you own, what it returned on your own cash flows, what it costs and what sits underneath. Statements are read on this machine only." />
      <ImportCard onDone={refresh} />
      {view.isError ? (
        <ErrorState error={view.error} onRetry={() => view.refetch()} />
      ) : !view.data ? (
        <Skeleton className="h-64" />
      ) : view.data.imports.length === 0 ? (
        <PortfolioStart />
      ) : (
        <>
          <Analysis view={view.data} />
          <Imports view={view.data} onDone={refresh} />
        </>
      )}
    </div>
  );
}
