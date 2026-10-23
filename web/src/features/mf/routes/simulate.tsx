/**
 * Investment lab (ui-ux doc 03 §06): SIP, lump sum, SWP and STP over real past
 * NAVs, with XIRR and a tax estimate from the backend calculators. The browser
 * computes nothing: it collects inputs, shows the service's result, and labels an
 * old result "Previous scenario" once the inputs change.
 */
import { useMutation, useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { mfApi, type CalculatorKind, type CalculatorRequest, type Simulation, type TaxClass } from '../api';
import { ChartFrame, Histogram, LegendDot, TimeChart } from '../components/charts';
import { FundSearch } from '../components/FundSearch';
import { I } from '../components/icons';
import { Badge, Button, Card, DependencyPanel, ErrorState, Field, PageHeader, Segmented, Skeleton, SnapshotNote, Stat, cx, inputClass, useTitle } from '../components/ui';
import { date, enumLabel, inr, pct, schemeName } from '../format';
import { useMetrics } from '../queries';
import { seriesColor, token } from '../theme/themes';
import { useRecordMutations } from '../workspace';

const KINDS: { value: CalculatorKind; label: string; lead: string }[] = [
  { value: 'sip', label: 'SIP', lead: 'A fixed amount every month, optionally stepped up each year.' },
  { value: 'lumpsum', label: 'Lump sum', lead: 'One investment on the start date, valued on the end date.' },
  { value: 'swp', label: 'SWP', lead: 'Invest once, then withdraw a fixed amount every month.' },
  { value: 'stp', label: 'STP', lead: 'Invest in one fund, then move a fixed amount each month into another.' },
];

const SERIES_LABELS: Record<string, string> = {
  invested: 'Invested so far',
  value: 'Value',
  withdrawn: 'Withdrawn',
  transferred: 'Transferred',
  source_value: 'Source fund value',
  target_value: 'Target fund value',
};
const PLOTTED = ['value', 'invested', 'source_value', 'target_value'];
const SERIES_COLOR: Record<string, string> = { value: seriesColor(0), target_value: seriesColor(0), source_value: seriesColor(1), invested: token('muted') };

const today = new Date().toISOString().slice(0, 10);
const yearsAgo = (n: number) => `${Number(today.slice(0, 4)) - n}${today.slice(4, 8)}01`;

interface Inputs {
  kind: CalculatorKind;
  code: string;
  target: string;
  amount: string;
  instalment: string;
  day: string;
  start: string;
  end: string;
  stepUp: string;
  taxClass: TaxClass;
  slab: string;
}

function FundChoice({ code, onChange, label }: { code: string; onChange: (code: string) => void; label: string }) {
  const m = useMetrics(code || undefined);
  return (
    <div>
      <p className="mb-1 text-[13px] font-medium text-mf-ink-soft">{label}</p>
      {code ? (
        <div className="flex items-center gap-2 rounded-control border border-mf-line-strong bg-mf-sunken px-3 py-2">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{m.data ? schemeName(m.data.name) : `AMFI ${code}`}</p>
            {m.data && <p className="text-xs text-mf-muted">{enumLabel(String(m.data.values.plan))} · {enumLabel(String(m.data.values.option))} · AMFI {code}</p>}
          </div>
          <button type="button" onClick={() => onChange('')} aria-label={`Change ${label.toLowerCase()}`} className="grid h-8 w-8 place-items-center rounded-full text-mf-muted hover:bg-mf-line">
            <I.x className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <FundSearch label={label} placeholder="Search a fund" onPick={(f) => onChange(f.amfi_code)} />
      )}
    </div>
  );
}

/** Inputs → a calculator request, or the first problem to fix. */
function toRequest(i: Inputs): { body?: CalculatorRequest; error?: string } {
  const amount = Number(i.amount);
  if (!i.code) return { error: 'Choose a fund.' };
  if (!(amount > 0)) return { error: 'The amount must be more than zero.' };
  if (!i.start || !i.end || i.start >= i.end) return { error: 'The start date must be before the end date.' };
  if (i.end > today) return { error: 'The end date cannot be in the future: this is a historical simulation.' };
  const day = Number(i.day);
  if (i.kind !== 'lumpsum' && !(day >= 1 && day <= 28)) return { error: 'Pick a day of the month from 1 to 28.' };
  const body: CalculatorRequest = { code: i.code, amount, start: i.start, end: i.end, tax_class: i.taxClass };
  if (i.kind !== 'lumpsum') body.day = day;
  if (i.kind === 'sip' && i.stepUp) {
    const s = Number(i.stepUp);
    if (!(s >= 0 && s <= 100)) return { error: 'The step-up is a yearly percentage from 0 to 100.' };
    body.step_up = s / 100;
  }
  if (i.kind === 'swp' || i.kind === 'stp') {
    const inst = Number(i.instalment);
    if (!(inst > 0)) return { error: `The monthly ${i.kind === 'swp' ? 'withdrawal' : 'transfer'} must be more than zero.` };
    body.instalment = inst;
  }
  if (i.kind === 'stp') {
    if (!i.target) return { error: 'Choose the fund to transfer into.' };
    if (i.target === i.code) return { error: 'The target fund must differ from the source fund.' };
    body.target = i.target;
  }
  if (i.taxClass !== 'equity' && i.slab) {
    const slab = Number(i.slab);
    if (!(slab >= 0 && slab <= 50)) return { error: 'The slab rate is a percentage from 0 to 50.' };
    body.slab_rate = slab / 100;
  }
  return { body };
}

function Result({ sim, stale }: { sim: Simulation; stale: boolean }) {
  const s = sim.summary;
  const keys = Object.keys(sim.timeline[0] ?? {}).filter((k) => k !== 'date');
  const plotted = keys.filter((k) => PLOTTED.includes(k));
  const series = plotted.map((k, i) => ({ id: k, label: SERIES_LABELS[k] ?? k, points: sim.timeline.map((r) => [String(r.date), Number(r[k])] as [string, number]), color: SERIES_COLOR[k] ?? seriesColor(i), dashed: k === 'invested' }));
  const n = (k: string) => (typeof s[k] === 'number' ? (s[k] as number) : null);
  return (
    <div className={cx('space-y-6', stale && 'opacity-60')}>
      {stale && <Badge tone="warning">Previous scenario: the inputs have changed since this ran</Badge>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Invested" value={inr(n('invested'))} sub={n('instalments') ? `${n('instalments')} instalments` : s.bought_on ? `on ${date(String(s.bought_on))}` : undefined} />
        {n('withdrawn') ? <Stat label="Withdrawn" value={inr(n('withdrawn'))} sub={`${n('withdrawals') ?? ''} withdrawals`} /> : null}
        <Stat label={`Value on ${date(String(s.valued_on))}`} value={inr(n('value'))} sub={sim.kind === 'stp' ? `target ${inr(n('target_value'))} · source ${inr(n('source_value'))}` : undefined} />
        <Stat label="Gain" value={inr(n('gain'))} valueClass={cx((n('gain') ?? 0) < 0 && 'text-mf-loss')} sub="value plus withdrawals minus invested" />
        <Stat label="XIRR" value={pct(n('xirr'), 2)} sub="yearly return on dated cash flows" help="XIRR is the yearly rate that makes every dated payment and the final value balance. It accounts for when each instalment went in." />
      </div>
      {sim.kind === 'swp' && n('value') === 0 && (
        <p role="alert" className="rounded-[10px] bg-mf-loss-soft p-3 text-sm text-mf-loss">The withdrawals used up the investment before the end date.</p>
      )}
      {series.length > 0 ? (
        <ChartFrame
          title="How the money moved"
          subtitle="Each point is an instalment date; values use that day's NAV"
          legend={series.map((x) => <LegendDot key={x.id} color={x.color} dashed={x.dashed} label={x.label} />)}
          table={{ columns: ['Date', ...keys.map((k) => SERIES_LABELS[k] ?? k)], rows: sim.timeline.map((r) => [date(String(r.date)), ...keys.map((k) => inr(Number(r[k])))]) }}
        >
          <TimeChart label="Scenario value over time" height={280} series={series} format={(v) => inr(v, true)} />
        </ChartFrame>
      ) : (
        <Card title="One purchase">
          <p className="text-sm text-mf-ink-soft">A lump sum has no instalments, so there is no path to draw: {inr(n('invested'))} bought {n('units')?.toFixed(3)} units on {date(String(s.bought_on))}, worth {inr(n('value'))} on {date(String(s.valued_on))}.</p>
        </Card>
      )}
      {sim.tax && (
        <Card title="Tax estimate" subtitle={`Tax class ${sim.tax.tax_class} · rules ${sim.tax.rules} · on gains from units sold or valued`}>
          {sim.tax.reason ? (
            <p className="text-sm text-mf-warning">{sim.tax.reason}</p>
          ) : (
            <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
              <table className="w-full min-w-[520px] text-sm">
                <thead className="text-xs text-mf-muted">
                  <tr className="border-b border-mf-line">
                    {['Financial year', 'Short-term gain', 'Long-term gain', 'Slab-taxed gain', 'Tax'].map((h, i) => <th key={h} scope="col" className={cx('py-2 font-medium', i ? 'text-right' : 'text-left')}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {sim.tax.years.map((y) => (
                    <tr key={y.year} className="border-b border-mf-line last:border-0">
                      <th scope="row" className="py-2 text-left font-normal">{y.year}</th>
                      <td className="py-2 text-right tabular">{inr(y.short_term)}</td>
                      <td className="py-2 text-right tabular">{inr(y.long_term)}</td>
                      <td className="py-2 text-right tabular">{inr(y.slab)}</td>
                      <td className="py-2 text-right font-medium tabular">{inr(y.tax)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-sm">Estimated total tax <b className="tabular">{inr(sim.tax.total)}</b>{sim.tax.sales_not_modelled ? ` · ${sim.tax.sales_not_modelled} sales not modelled` : ''}</p>
        </Card>
      )}
      <ul className="space-y-1 text-xs text-mf-muted">
        {sim.cautions.map((c) => <li key={c}>· {c}</li>)}
        <li>· The expense ratio is already inside the NAV; it is not deducted again.</li>
      </ul>
    </div>
  );
}

function RollingSip({ code }: { code: string }) {
  const [tenor, setTenor] = useState<'3y' | '5y'>('3y');
  const q = useQuery({ queryKey: ['mf', 'fund', code, 'rolling-sip', tenor], queryFn: ({ signal }) => mfApi.rollingSip(code, { tenor, amount: 10000 }, signal), staleTime: 300_000 });
  const d = q.data;
  const xirrs = useMemo(() => (d?.starts ?? []).map((s) => s.xirr).filter((x): x is number => typeof x === 'number'), [d]);
  return (
    <ChartFrame
      title="Did the start month matter?"
      subtitle={`A ₹10,000 monthly SIP held for ${tenor.toUpperCase()}, started in every past month`}
      controls={<Segmented label="SIP length" value={tenor} onChange={setTenor} options={[{ value: '3y', label: '3Y' }, { value: '5y', label: '5Y' }]} />}
      legend={d && (
        <>
          <span>{d.summary.starts} start months</span>
          <span>Median XIRR <b className="tabular">{pct(d.summary.median_xirr)}</b></span>
          <span>Positive <b className="tabular">{pct(d.summary.positive_share, 0)}</b></span>
          {d.summary.worst && <span>Worst <b className="tabular text-mf-loss">{pct(d.summary.worst.xirr)}</b> from {date(d.summary.worst.start)}</span>}
          {d.summary.best && <span>Best <b className="tabular">{pct(d.summary.best.xirr)}</b> from {date(d.summary.best.start)}</span>}
        </>
      )}
      table={d ? { columns: ['Start', 'End', 'Invested', 'Value', 'XIRR'], rows: d.starts.map((s) => [date(s.start), date(s.end), inr(s.invested), inr(s.value), pct(s.xirr)]) } : undefined}
    >
      {q.isError ? <ErrorState error={q.error} compact /> : q.isLoading ? <Skeleton className="h-[220px]" /> : xirrs.length < 3 ? (
        <p className="py-10 text-center text-sm text-mf-muted">The history is too short for {tenor.toUpperCase()} SIPs from many start months.</p>
      ) : (
        <Histogram label="Distribution of SIP XIRR by start month" values={xirrs} bins={18} format={(x) => pct(x, 0)} markers={d?.summary.median_xirr != null ? [{ value: d.summary.median_xirr, label: 'Median', color: token('brandStrong') }] : []} />
      )}
    </ChartFrame>
  );
}

export default function Simulate() {
  useTitle('Investment lab');
  const [params] = useSearchParams();
  const [inputs, setInputs] = useState<Inputs>({
    kind: (KINDS.some((k) => k.value === params.get('kind')) ? params.get('kind') : 'sip') as CalculatorKind,
    code: /^\d{1,9}$/.test(params.get('code') ?? '') ? params.get('code')! : '',
    target: '',
    amount: '10000',
    instalment: '5000',
    day: '1',
    start: yearsAgo(5),
    end: today,
    stepUp: '0',
    taxClass: 'equity',
    slab: '30',
  });
  const set = (patch: Partial<Inputs>) => setInputs((i) => ({ ...i, ...patch }));
  const run = useMutation({ mutationFn: ({ kind, body }: { kind: CalculatorKind; body: CalculatorRequest }) => mfApi.calculate(kind, body) });
  const { create } = useRecordMutations<{ kind: CalculatorKind; request: CalculatorRequest; summary: Simulation['summary'] }>('scenario');
  const fund = useMetrics(inputs.code || undefined);
  const { body, error } = toRequest(inputs);
  const stale = !!run.variables && JSON.stringify(run.variables) !== JSON.stringify({ kind: inputs.kind, body });
  const kind = KINDS.find((k) => k.value === inputs.kind)!;
  const amountLabel = inputs.kind === 'sip' ? 'Monthly instalment (₹)' : 'Initial investment (₹)';

  return (
    <div className="space-y-6">
      <PageHeader title="Investment lab" lead="Test an investment habit on real past NAVs: what happened, month by month, and the tax it would have created." />
      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card title="Scenario" className="self-start lg:sticky lg:top-24">
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (body) run.mutate({ kind: inputs.kind, body });
            }}
          >
            <Segmented label="Investment kind" size="md" value={inputs.kind} onChange={(k) => set({ kind: k })} options={KINDS.map((k) => ({ value: k.value, label: k.label }))} />
            <p className="text-xs text-mf-muted">{kind.lead}</p>
            <FundChoice code={inputs.code} onChange={(code) => set({ code })} label={inputs.kind === 'stp' ? 'Transfer from' : 'Fund'} />
            {inputs.kind === 'stp' && <FundChoice code={inputs.target} onChange={(target) => set({ target })} label="Transfer into" />}
            <Field label={amountLabel}>
              <input className={inputClass} type="number" inputMode="numeric" min={1} value={inputs.amount} onChange={(e) => set({ amount: e.target.value })} />
            </Field>
            {(inputs.kind === 'swp' || inputs.kind === 'stp') && (
              <Field label={inputs.kind === 'swp' ? 'Monthly withdrawal (₹)' : 'Monthly transfer (₹)'}>
                <input className={inputClass} type="number" inputMode="numeric" min={1} value={inputs.instalment} onChange={(e) => set({ instalment: e.target.value })} />
              </Field>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start">
                <input className={inputClass} type="date" max={today} value={inputs.start} onChange={(e) => set({ start: e.target.value })} />
              </Field>
              <Field label="End">
                <input className={inputClass} type="date" max={today} value={inputs.end} onChange={(e) => set({ end: e.target.value })} />
              </Field>
            </div>
            {inputs.kind !== 'lumpsum' && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Day of month" hint="First NAV on or after it">
                  <input className={inputClass} type="number" min={1} max={28} value={inputs.day} onChange={(e) => set({ day: e.target.value })} />
                </Field>
                {inputs.kind === 'sip' && (
                  <Field label="Yearly step-up (%)">
                    <input className={inputClass} type="number" min={0} max={100} step="any" value={inputs.stepUp} onChange={(e) => set({ stepUp: e.target.value })} />
                  </Field>
                )}
              </div>
            )}
            <Field label="Tax class" hint="Choose how the fund is taxed; Wickstreet does not guess it from the name.">
              <select className={inputClass} value={inputs.taxClass} onChange={(e) => set({ taxClass: e.target.value as TaxClass })}>
                <option value="equity">Equity-oriented</option>
                <option value="debt">Debt-oriented</option>
                <option value="other">Other (hybrid, FoF, gold…)</option>
              </select>
            </Field>
            {inputs.taxClass !== 'equity' && (
              <Field label="Your income-tax slab (%)">
                <input className={inputClass} type="number" min={0} max={50} step="any" value={inputs.slab} onChange={(e) => set({ slab: e.target.value })} />
              </Field>
            )}
            {error && inputs.code && <p role="alert" className="text-sm text-mf-loss">{error}</p>}
            <Button type="submit" variant="primary" className="w-full" disabled={!body || run.isPending}>
              {run.isPending ? 'Running…' : 'Run historical scenario'}
            </Button>
            {run.data && body && (
              <Button
                className="w-full"
                disabled={create.isPending || stale}
                onClick={() => create.mutate({ name: `${kind.label} · ${fund.data ? schemeName(fund.data.name) : inputs.code} · ${inputs.start}`.slice(0, 120), body: { kind: inputs.kind, request: body, summary: run.data.summary } })}
              >
                <I.bookmark className="h-4 w-4" />
                {create.isSuccess ? 'Saved to your workspace' : 'Save scenario'}
              </Button>
            )}
          </form>
        </Card>

        <div className="min-w-0 space-y-6">
          {run.isError && <ErrorState error={run.error} />}
          {run.isPending && !run.data && <Skeleton className="h-64" />}
          {run.data ? (
            <Result sim={run.data} stale={stale} />
          ) : (
            !run.isPending && (
              <div className="rounded-card border border-dashed border-mf-line-strong bg-mf-surface/60 p-8 text-center">
                <I.lab className="mx-auto mb-3 h-8 w-8 text-mf-brand" />
                <p className="font-display text-xl">Set up a scenario and run it</p>
                <p className="mx-auto mt-1 max-w-md text-sm text-mf-muted">Results use each instalment date’s real NAV, stamp duty and the tax rules in force on each sale date. Nothing here forecasts returns.</p>
              </div>
            )
          )}
          {inputs.kind === 'sip' && inputs.code && <RollingSip code={inputs.code} />}
          <div className="grid gap-4 md:grid-cols-2">
            <DependencyPanel title="Goal planner with assumed returns" needs="S1, an approved forward-scenario method">
              Forward projections need stated assumptions and their own method. Until then the lab shows history only.
            </DependencyPanel>
            <DependencyPanel title="Exit loads in the result" needs="E1, AMC exit-load disclosures">
              Exit loads are not deducted today; the cautions say so.
            </DependencyPanel>
          </div>
          {run.data && <SnapshotNote asOf={run.data.as_of} revision={run.data.data_revision} method={run.data.method_version} extra={` · calculator v${run.data.summary.calculator_version}`} />}
          {!inputs.code && (
            <p className="text-sm text-mf-muted">
              No fund in mind? <Link className="text-mf-brand hover:underline" to="/mf/screen">Find one in the screener</Link>.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
