/**
 * Investment lab (ui-ux doc 03 §06): SIP, lump sum, SWP and STP over real past
 * NAVs, with XIRR and a tax estimate from the backend calculators. The browser
 * computes nothing: it collects inputs, shows the service's result, and labels an
 * old result "Previous scenario" once the inputs change. A saved scenario reopens
 * with every input, on its saved snapshot or the latest (audit A-05).
 */
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useId, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { pctTick } from '../axis';
import { mfApi, type CalculatorKind, type CalculatorRequest, type Simulation, type TaxClass } from '../api';
import { KIND_DEFAULTS, defaultInputs, inputsFromSearch, revisionFromSearch, toRequest, today, yearsAgo, type Inputs, type ScenarioProvenance } from '../scenario';
import { ChartFrame, Histogram, LegendDot, TimeChart } from '../components/charts';
import { FundSearch } from '../components/FundSearch';
import { I } from '../components/icons';
import { Badge, Button, Card, DependencyPanel, ErrorState, Field, PageHeader, Segmented, Skeleton, SnapshotNote, Stat, cx, inputClass, useTitle } from '../components/ui';
import { categoryShort, date, enumLabel, inr, inrTick, pct, schemeName } from '../format';
import { useMetrics } from '../queries';
import { seriesColor, token } from '../theme/themes';
import { startingFunds, useRecentFunds } from '../context';
import { useDebounced } from '../use-debounced';
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
const TAX_LABEL: Record<string, string> = { equity: 'Equity-oriented', debt: 'Debt-oriented', other: 'Other (overseas, hybrid, FoF, gold…)' };

const PLOTTED = ['value', 'invested', 'source_value', 'target_value'];
const SERIES_COLOR: Record<string, string> = { value: seriesColor(0), target_value: seriesColor(0), source_value: seriesColor(1), invested: token('muted') };

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
          <button type="button" onClick={() => onChange('')} aria-label={`Change ${label.toLowerCase()}`} className="relative grid h-8 w-8 place-items-center rounded-full text-mf-muted before:absolute before:-inset-1.5 before:content-[''] hover:bg-mf-line">
            <I.x className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <FundSearch label={label} placeholder="Search a fund" onPick={(f) => onChange(f.amfi_code)} />
      )}
    </div>
  );
}

const TAX_REASONS: Record<string, string> = {
  tax_class_needed: 'This fund’s category does not settle how it is taxed (for example sectoral and thematic funds, which may invest overseas, index funds, fund of funds, gold and dynamic hybrids). Choose a tax class in the scenario to see an estimate.',
  slab_rate_needed: 'Some gains are taxed at your income-tax slab. Enter your slab rate to see an estimate.',
};

/** What the tax figure covers, which differs by kind (independent audit, Lab section). */
function taxScope(sim: Simulation): string {
  const on = date(String(sim.summary.valued_on));
  if (sim.kind === 'swp') return `Only the units sold for withdrawals. Units still held on ${on} are not taxed here.`;
  if (sim.kind === 'stp') return `Only the source units sold for transfers. Units still held on ${on} are not taxed here.`;
  return `As if you redeemed every unit on ${on}. No tax is due until you sell.`;
}

function TaxCard({ sim, chosen, slab }: { sim: Simulation; chosen: boolean; slab: string }) {
  const tax = sim.tax!;
  const cls = tax.tax_class ? TAX_LABEL[tax.tax_class] : null;
  const source = chosen ? 'your choice' : 'from the fund’s category';
  return (
    <Card title="Tax estimate" subtitle={taxScope(sim)}>
      <div className="space-y-3">
        <p className="flex flex-wrap items-center gap-2 text-sm">
          {cls ? <Badge tone="neutral">{cls} · {source}</Badge> : <Badge tone="warning">Tax class needed</Badge>}
          {tax.tax_class && tax.tax_class !== 'equity' && <Badge tone="neutral">Slab {slab || '—'}%</Badge>}
          <span className="text-xs text-mf-muted">Rules in force on each sale date ({tax.rules})</span>
        </p>
        {tax.reason ? (
          <p role="status" className="rounded-[10px] bg-mf-warning-soft p-3 text-sm text-mf-warning">{TAX_REASONS[tax.reason] ?? tax.reason}</p>
        ) : (
          <>
            <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Tax by financial year; scroll sideways for more columns">
              <table className="w-full min-w-[520px] text-sm">
                <thead className="text-xs text-mf-muted">
                  <tr className="border-b border-mf-line">
                    {['Financial year', 'Short-term gain', 'Long-term gain', 'Slab-taxed gain', 'Tax'].map((h, i) => <th key={h} scope="col" className={cx('py-2 font-medium', i ? 'text-right' : 'text-left')}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {tax.years.map((y) => (
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
            <p className="text-sm">Estimated total tax <b className="tabular">{inr(tax.total)}</b>{tax.sales_not_modelled ? ` · ${tax.sales_not_modelled} sales before April 2018 not modelled` : ''}</p>
          </>
        )}
        <p className="text-xs text-mf-muted">Holding periods count calendar months: a unit sold on its 12-month anniversary is still short term. Includes 4% cess. Not included: exit loads, surcharge and securities transaction tax.</p>
      </div>
    </Card>
  );
}

function Result({ sim, stale, chosen, slab }: { sim: Simulation; stale: boolean; chosen: boolean; slab: string }) {
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
          <TimeChart label="Scenario value over time" height={280} series={series} format={(v) => inr(v)} tick={inrTick} />
        </ChartFrame>
      ) : (
        <Card title="One purchase">
          <p className="text-sm text-mf-ink-soft">A lump sum has no instalments, so there is no path to draw: {inr(n('invested'))} bought {n('units')?.toFixed(3)} units on {date(String(s.bought_on))}, worth {inr(n('value'))} on {date(String(s.valued_on))}.</p>
        </Card>
      )}
      {sim.tax && <TaxCard sim={sim} chosen={chosen} slab={slab} />}
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
        <Histogram label="Distribution of SIP XIRR by start month" values={xirrs} format={pctTick} markers={d?.summary.median_xirr != null ? [{ value: d.summary.median_xirr, label: 'Median', color: token('brandStrong') }] : []} />
      )}
    </ChartFrame>
  );
}

const RANGES: Record<'monthly' | 'corpus', [number, number, number]> = { monthly: [500, 100_000, 500], corpus: [10_000, 5_000_000, 10_000] };

/** A rupee amount as a slider and a number box; the box takes any value, the slider a common range. */
function MoneyField({ label, value, onChange, range }: { label: string; value: string; onChange: (v: string) => void; range: 'monthly' | 'corpus' }) {
  const [min, max, step] = RANGES[range];
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1 flex items-baseline justify-between text-[13px] font-medium text-mf-ink-soft">
        {label}
        <span className="text-xs font-normal text-mf-muted">{Number(value) > 0 ? inr(Number(value), true) : ''}</span>
      </label>
      <input id={id} className={inputClass} type="number" inputMode="numeric" min={1} value={value} onChange={(e) => onChange(e.target.value)} />
      <input type="range" className="mt-2 h-6 w-full" min={min} max={max} step={step} value={Math.min(max, Math.max(min, Number(value) || min))} onChange={(e) => onChange(e.target.value)} aria-label={`${label}, slider`} />
    </div>
  );
}

export default function Simulate() {
  useTitle('Investment lab');
  const [params] = useSearchParams();
  const recent = useRecentFunds();
  const linked = /^\d{1,9}$/.test(params.get('code') ?? '') ? params.get('code')! : '';
  const [inputs, setInputs] = useState<Inputs>(() => {
    const first = linked || startingFunds(recent, 1).codes[0];
    const target = startingFunds(recent, 2).codes.find((c) => c !== first) ?? '';
    return inputsFromSearch(params, defaultInputs('sip', first, target));
  });
  // A saved scenario can replay on the snapshot it ran on; any edit or "latest" unpins it.
  const [pinned, setPinned] = useState(() => revisionFromSearch(params));
  const now = today();
  const example = !linked && !recent.includes(inputs.code);
  const set = (patch: Partial<Inputs>) => setInputs((i) => ({ ...i, ...patch }));
  const { create } = useRecordMutations<{ kind: CalculatorKind; request: CalculatorRequest; summary: Simulation['summary']; provenance: ScenarioProvenance }>('scenario');
  const fund = useMetrics(inputs.code || undefined);
  const { body: request, error } = toRequest(inputs, now);
  const body = request && pinned != null ? { ...request, data_revision: pinned } : request;
  // Results follow the inputs: the request runs 400 ms after the last change.
  const key = useDebounced(body ? JSON.stringify({ kind: inputs.kind, body }) : '', 400);
  const run = useQuery({
    queryKey: ['mf', 'calculate', key],
    queryFn: ({ signal }) => {
      const r = JSON.parse(key) as { kind: CalculatorKind; body: CalculatorRequest };
      return mfApi.calculate(r.kind, r.body, signal);
    },
    enabled: !!key,
    staleTime: 300_000,
    placeholderData: keepPreviousData,
  });
  const stale = run.isPlaceholderData || (!!body && key !== JSON.stringify({ kind: inputs.kind, body }));
  const kind = KINDS.find((k) => k.value === inputs.kind)!;
  const amountLabel = inputs.kind === 'sip' ? 'Monthly instalment (₹)' : 'Initial investment (₹)';
  const category = fund.data ? String(fund.data.values.category) : '';
  const save = () =>
    run.data &&
    request &&
    create.mutate({
      name: `${kind.label} · ${fund.data ? schemeName(fund.data.name) : inputs.code} · ${inputs.start}`.slice(0, 120),
      body: {
        kind: inputs.kind,
        request,
        summary: run.data.summary,
        provenance: {
          data_revision: run.data.data_revision,
          method_version: run.data.method_version,
          as_of: run.data.as_of,
          calculator_version: Number(run.data.summary.calculator_version),
          tax_class: run.data.tax?.tax_class ?? null,
          tax_class_source: inputs.taxClass ? 'chosen' : 'category',
        },
      },
    });

  return (
    <div className="space-y-6">
      <PageHeader title="Investment lab" lead="Test an investment habit on real past NAVs: what happened, month by month, and the tax it would have created." />
      {example && (
        <p className="rounded-[12px] border border-mf-info/30 bg-mf-info-soft/60 px-4 py-2.5 text-sm text-mf-ink-soft">
          Showing an example fund so you can see a result at once. Change the fund below, or open any fund and choose “Test an investment”.
        </p>
      )}
      {pinned != null && (
        <div role="status" className="flex flex-wrap items-center gap-3 rounded-[12px] border border-mf-line-strong bg-mf-sunken px-4 py-2.5 text-sm">
          <span>Replaying a saved scenario on snapshot <b className="tabular">{pinned}</b>, the data it ran on.</span>
          <Button size="sm" variant="secondary" onClick={() => setPinned(undefined)}>Rerun on the latest snapshot</Button>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card title="Scenario" subtitle="Results update as you change an input" className="order-2 self-start lg:order-1 lg:sticky lg:top-24" id="scenario-inputs">
          <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
            <Segmented label="Investment kind" size="md" value={inputs.kind} onChange={(k) => set({ kind: k, ...KIND_DEFAULTS[k] })} options={KINDS.map((k) => ({ value: k.value, label: k.label }))} />
            <p className="text-xs text-mf-muted">{kind.lead}</p>
            {/* A new fund needs its own tax decision: a class chosen for the old one does not carry over. */}
            <FundChoice code={inputs.code} onChange={(code) => set({ code, taxClass: '' })} label={inputs.kind === 'stp' ? 'Transfer from' : 'Fund'} />
            {inputs.kind === 'stp' && <FundChoice code={inputs.target} onChange={(target) => set({ target })} label="Transfer into" />}
            <MoneyField label={amountLabel} value={inputs.amount} onChange={(amount) => set({ amount })} range={inputs.kind === 'sip' ? 'monthly' : 'corpus'} />
            {(inputs.kind === 'swp' || inputs.kind === 'stp') && (
              <MoneyField label={inputs.kind === 'swp' ? 'Monthly withdrawal (₹)' : 'Monthly transfer (₹)'} value={inputs.instalment} onChange={(instalment) => set({ instalment })} range="monthly" />
            )}
            <Segmented
              label="Start"
              value={[1, 3, 5, 10].map((n) => yearsAgo(n, now)).includes(inputs.start) && inputs.end === now ? inputs.start : ''}
              onChange={(start) => set({ start, end: now })}
              options={[1, 3, 5, 10].map((n) => ({ value: yearsAgo(n, now), label: `${n}Y ago` }))}
            />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start">
                <input className={inputClass} type="date" max={now} value={inputs.start} onChange={(e) => set({ start: e.target.value })} />
              </Field>
              <Field label="End">
                <input className={inputClass} type="date" max={now} value={inputs.end} onChange={(e) => set({ end: e.target.value })} />
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
            <Field
              label="Tax class"
              hint={
                inputs.taxClass
                  ? 'Your choice. It resets when you change the fund.'
                  : run.data?.tax?.reason === 'tax_class_needed'
                    ? `The category${category ? `, ${categoryShort(category)},` : ''} does not settle the class. Choose one.`
                    : category
                      ? `Taken from the category, ${categoryShort(category)}, where it settles the class.`
                      : 'Taken from the fund’s category where it settles the class.'
              }
            >
              <select className={inputClass} value={inputs.taxClass} onChange={(e) => set({ taxClass: e.target.value as TaxClass | '' })}>
                <option value="">From the fund’s category</option>
                <option value="equity">{TAX_LABEL.equity}</option>
                <option value="debt">{TAX_LABEL.debt}</option>
                <option value="other">{TAX_LABEL.other}</option>
              </select>
            </Field>
            {inputs.taxClass !== 'equity' && (
              <Field label="Your income-tax slab (%)" hint="Used only for gains taxed at the slab rate">
                <input className={inputClass} type="number" min={0} max={50} step="any" value={inputs.slab} onChange={(e) => set({ slab: e.target.value })} />
              </Field>
            )}
            {error && inputs.code && <p role="alert" className="text-sm text-mf-loss">{error}</p>}
            <p className="text-xs text-mf-muted" aria-live="polite">{run.isFetching ? 'Running the scenario…' : run.data && !stale ? 'Result is up to date.' : ''}</p>
            {run.data && request && (
              <Button className="w-full" disabled={create.isPending || stale} onClick={save}>
                <I.bookmark className="h-4 w-4" />
                {create.isPending ? 'Saving…' : create.isSuccess ? 'Saved to your workspace' : 'Save scenario'}
              </Button>
            )}
            {create.isError && <ErrorState error={create.error} compact title="Could not save the scenario. Your inputs are kept; try again." />}
          </form>
        </Card>

        {/* The result column keeps its height while a run loads, so nothing below it jumps (audit 9, Lab CLS). */}
        <div className="order-1 min-w-0 space-y-6 lg:order-2 lg:min-h-[760px]">
          {run.data && (
            <a href="#scenario-inputs" className="flex items-center justify-between gap-3 rounded-[12px] border border-mf-line bg-mf-surface px-4 py-2.5 text-sm lg:hidden">
              <span className="min-w-0 truncate">
                <b>{kind.label}</b> · {inr(Number(inputs.amount), true)} · {date(inputs.start)} – {date(inputs.end)}
              </span>
              <span className="shrink-0 font-medium text-mf-brand-strong">Edit inputs ↓</span>
            </a>
          )}
          {run.isError && (
            <ErrorState
              error={run.error}
              title={pinned != null ? `Snapshot ${pinned} could not be replayed. It may no longer be stored.` : undefined}
              onRetry={pinned != null ? () => setPinned(undefined) : undefined}
              retryLabel="Rerun on the latest snapshot"
            />
          )}
          {run.isLoading && <Skeleton className="h-[560px]" />}
          {run.data ? (
            <Result sim={run.data} stale={stale} chosen={!!inputs.taxClass} slab={inputs.slab} />
          ) : (
            !run.isLoading && (
              <div className="rounded-card border border-dashed border-mf-line-strong bg-mf-surface/60 p-8 text-center">
                <I.lab className="mx-auto mb-3 h-8 w-8 text-mf-brand" />
                <p className="font-display text-xl">Choose a fund to see a result</p>
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
