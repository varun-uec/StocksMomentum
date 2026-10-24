/**
 * Facts & costs and Benchmark (doc 21 C12, C14, C15): AMFI's own figures, each with
 * its date, and statistics against a labelled index-fund proxy. A value AMFI did not
 * file shows its reason, never an estimate.
 */
import { useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router';
import type { BenchmarkRow, Dated, FundBenchmark, FundProfile, Missing } from '../../api';
import { pctTick } from '../../axis';
import { date, formatField, isNum, missingLabel, num, pct } from '../../format';
import { useBenchmark, useProfile } from '../../queries';
import { seriesColor, token } from '../../theme/themes';
import { ChartFrame, LegendDot, TimeChart, thin, type Series } from '../charts';
import { Badge, Card, Delta, EmptyState, ErrorState, Segmented, Skeleton, Stat } from '../ui';
import { MetricTile, type FundTabProps } from './shared';

const DAY = 86_400_000;

/** Change points as a step line: each value holds until the day before the next. */
function steps(points: Dated[], until?: string): [string, number][] {
  const out: [string, number][] = [];
  points.forEach(([d, v], i) => {
    if (i > 0) out.push([new Date(Date.parse(d) - DAY).toISOString().slice(0, 10), points[i - 1][1]]);
    out.push([d, v]);
  });
  const last = points[points.length - 1];
  if (last && until && until > last[0]) out.push([until, last[1]]);
  return out;
}

function Dl({ rows }: { rows: [string, string | undefined | null][] }) {
  const shown = rows.filter(([, v]) => v);
  if (!shown.length) return <p className="text-sm text-mf-muted">Not filed in the scheme summary document.</p>;
  return (
    <dl className="space-y-3 text-sm">
      {shown.map(([k, v]) => (
        <div key={k}>
          <dt className="text-xs text-mf-muted">{k}</dt>
          <dd className="whitespace-pre-line break-words text-mf-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function NoScheme({ reason }: { reason?: string }) {
  return (
    <EmptyState title="AMFI has no scheme record for this plan">
      {missingLabel({ state: 'NA', reason: reason ?? 'no_scheme_join' })}. Facts join a plan through the ISINs in its scheme summary document; a closed or merged plan often has none.
    </EmptyState>
  );
}

function TerChart({ profile, asOf }: { profile: FundProfile; asOf: string }) {
  const series: Series[] = (['direct', 'regular'] as const)
    .map((p, i) => ({ id: p, label: p === 'direct' ? 'Direct plan' : 'Regular plan', points: steps(profile.ter?.[p] ?? [], asOf), color: seriesColor(i) }))
    .filter((s) => s.points.length > 0);
  const latest = (p: 'direct' | 'regular') => profile.ter?.[p]?.at(-1)?.[1];
  return (
    <ChartFrame
      title="Expense ratio over time"
      subtitle="Total TER, % a year of daily net assets, as each AMC filed it with AMFI"
      legend={series.map((s) => (
        <LegendDot key={s.id} color={s.color!} label={<>{s.label} <b className="tabular">{isNum(latest(s.id as 'direct')) ? `${latest(s.id as 'direct')!.toFixed(2)}%` : '—'}</b></>} />
      ))}
      footnote={profile.notes?.join(' ')}
      table={{ columns: ['From', 'Direct %', 'Regular %'], rows: mergeDates(profile.ter?.direct ?? [], profile.ter?.regular ?? []) }}
    >
      {series.length ? (
        <TimeChart label="Expense ratio over time" height={220} series={series} format={(v) => `${v.toFixed(2)}%`} tick={(v) => `${v.toFixed(2)}%`} />
      ) : (
        <p className="py-10 text-center text-sm text-mf-muted">AMFI has no TER rows for this scheme yet.</p>
      )}
    </ChartFrame>
  );
}

function mergeDates(a: Dated[], b: Dated[]): (string | number)[][] {
  const days = [...new Set([...a, ...b].map(([d]) => d))].sort();
  const at = (s: Dated[], d: string) => [...s].reverse().find(([x]) => x <= d)?.[1];
  return days.map((d) => [d, at(a, d) ?? '—', at(b, d) ?? '—']);
}

function AumChart({ profile }: { profile: FundProfile }) {
  const points = profile.aum_cr ?? [];
  if (points.length < 2) return null;
  return (
    <ChartFrame
      title="Assets under management"
      subtitle="₹ crore, all plans of the scheme, from AMFI's fund performance reports"
      table={{ columns: ['Date', 'AUM ₹ Cr'], rows: thin(points, 120).map(([d, v]) => [d, Math.round(v)]) }}
    >
      <TimeChart label="Assets under management" height={200} area series={[{ id: 'aum', label: 'AUM', points, color: token('chart2') }]} format={(v) => `₹${Math.round(v).toLocaleString('en-IN')} Cr`} tick={(v) => `₹${Math.round(v).toLocaleString('en-IN')}`} />
    </ChartFrame>
  );
}

function Idcw({ profile, tile }: { profile: FundProfile; tile: (id: string, label?: string, plain?: string) => ReactNode }) {
  const payouts = profile.idcw ?? [];
  const recent = [...payouts].reverse().slice(0, 12);
  return (
    <Card title="IDCW payouts" subtitle="Record dates and ₹ per unit as AMFI lists them; returns reinvest each payout at its record-date NAV">
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {tile('idcw_1y', 'Paid in a year', payouts.length ? `${payouts.length} payouts listed` : undefined)}
        {tile('idcw_yield_1y', 'IDCW yield 1Y')}
        {tile('ret_1y_with_idcw', 'Return 1Y with IDCW')}
        {tile('cagr_3y_with_idcw', 'CAGR 3Y with IDCW')}
      </div>
      {recent.length ? (
        <table className="w-full text-sm tabular">
          <thead>
            <tr className="text-left text-xs text-mf-muted">
              <th className="py-1 font-normal">Record date</th>
              <th className="py-1 text-right font-normal">₹ per unit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-mf-line">
            {recent.map(([d, v]) => (
              <tr key={d}>
                <td className="py-1.5">{date(d)}</td>
                <td className="py-1.5 text-right">{v.toLocaleString('en-IN', { maximumFractionDigits: 4 })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-sm text-mf-muted">AMFI lists no payouts for this option.</p>
      )}
    </Card>
  );
}

export function FactsAndCosts({ code, metrics, fields }: FundTabProps) {
  const profile = useProfile(code);
  const p = profile.data;
  if (profile.isError) return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />;
  if (!p) return <Skeleton className="h-96" />;
  if (!p.scheme) return <NoScheme reason={p.reason} />;
  const doc = (k: string) => p.document?.[k]?.text;
  const v = metrics.values;
  const other = p.plan === 'direct' ? 'regular' : 'direct';
  const otherTer = p.ter?.[other]?.at(-1)?.[1];
  const tile = (id: string, label?: string, plain?: string) => <MetricTile metrics={metrics} fields={fields} id={id} label={label} plain={plain} />;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat
          label="Expense ratio"
          value={isNum(v.ter) ? pct(v.ter, 2) : '—'}
          sub={isNum(v.ter) ? `${p.plan} plan · base ${pct(v.ter_base, 2)}${isNum(otherTer) ? ` · ${other} ${otherTer.toFixed(2)}%` : ''} · AMFI as of ${date(p.summary?.ter_as_of)}` : missingLabel(metrics.states.ter)}
          help={fields.get('ter')?.description}
        />
        {tile('ter_cat_pct', 'Cheaper than peers', isNum(v.ter_cat_median) ? `category median ${pct(v.ter_cat_median, 2)}` : undefined)}
        {tile('aum_cr', 'AUM', isNum(v.aum_change_1y) ? `${pct(v.aum_change_1y, 1, true)} in a year · ${date(v.aum_as_of)}` : `as of ${date(v.aum_as_of)}`)}
        <Stat label="Riskometer" value={typeof v.riskometer === 'string' ? v.riskometer : '—'} sub={`${isNum(v.riskometer_level) ? `level ${v.riskometer_level} of 6` : missingLabel(metrics.states.riskometer)}${p.riskometer_as_of ? ` · AMFI as of ${date(p.riskometer_as_of)}` : ''}`} />
        {tile('manager_tenure_y', 'Longest manager tenure', isNum(v.manager_count) ? `${v.manager_count} managers in the SSD` : undefined)}
        {tile('min_sip', 'Minimum SIP', isNum(v.min_lumpsum) ? `lump sum ₹${v.min_lumpsum.toLocaleString('en-IN')}` : undefined)}
      </div>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <TerChart profile={p} asOf={metrics.as_of} />
          <AumChart profile={p} />
        </div>
        <div className="space-y-6">
          <Card title="Exit load and minimums" subtitle={`As filed in the scheme summary document · ${date(p.document?.exit_load?.as_of)}`}>
            <Dl
              rows={[
                ['Exit load', doc('exit_load')],
                ['Minimum lump sum (₹)', doc('min_lumpsum')],
                ['Minimum additional (₹)', doc('min_additional')],
                ['SIP, SWP and STP minimums', doc('sip_minimum')],
                ['Maximum expense ratio stated', doc('expense_stated_max')],
              ]}
            />
          </Card>
          <Card title="Fund managers" subtitle="Start dates as filed; tenure to the data date">
            {p.managers?.length ? (
              <ul className="divide-y divide-mf-line text-sm">
                {p.managers.map((m) => (
                  <li key={m.name + m.since} className="flex items-baseline justify-between gap-3 py-2">
                    <span className="min-w-0 text-mf-ink">{m.name}</span>
                    <span className="shrink-0 text-xs text-mf-muted tabular">
                      since {date(m.since)} · {m.years.toFixed(1)} yrs
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <Dl rows={[['Managers', doc('managers')]]} />
            )}
            {doc('manager_roles') && <p className="mt-3 text-xs text-mf-muted">{doc('manager_roles')}</p>}
          </Card>
        </div>
      </div>
      {metrics.states.idcw_1y?.reason !== 'not_idcw_option' && <Idcw profile={p} tile={tile} />}
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card title="Mandate" subtitle="The scheme's own description">
          <Dl
            rows={[
              ['Investment objective', doc('objective')],
              ['Type of scheme', doc('fund_type')],
              ['Stated asset allocation', doc('asset_allocation')],
              ['Benchmark (Tier 1)', doc('benchmark_tier_1')],
              ['Benchmark (Tier 2)', doc('benchmark_tier_2')],
            ]}
          />
        </Card>
        <Card title="Scheme record" subtitle={`AMFI scheme ${p.scheme.sd_id}`}>
          <Dl
            rows={[
              ['Allotment date', doc('allotment_date')],
              ['Plans and options', doc('plans')],
              ['Riskometer at launch', doc('riskometer_at_launch')],
              ['Potential risk class', doc('potential_risk_class')],
              ['SEBI scheme code', doc('sebi_code')],
              ['Listing', doc('listing')],
              ['Custodian', doc('custodian')],
              ['Registrar', doc('registrar')],
              ['Auditor', doc('auditor')],
            ]}
          />
          <p className="mt-4 text-xs text-mf-muted">Source: {p.source}.</p>
        </Card>
      </div>
    </div>
  );
}

const HORIZONS = ['1y', '3y', '5y', '10y'] as const;

function cell(value: unknown, state?: Missing) {
  if (isNum(value)) return pct(value, 2);
  return <span className="text-mf-muted">{state ? missingLabel(state) : '—'}</span>;
}

function OfficialTable({ rows, states }: { rows: BenchmarkRow[]; states: FundBenchmark['states'] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-sm">
        <caption className="sr-only">Fund and benchmark returns by period, as AMFI reports them</caption>
        <thead>
          <tr className="border-b border-mf-line text-left text-xs text-mf-muted">
            <th scope="col" className="py-2 pr-3 font-medium">Period</th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">This plan</th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">Benchmark TRI</th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">Difference</th>
            <th scope="col" className="py-2 text-right font-medium">Information ratio</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.horizon} className="border-b border-mf-line/60 last:border-0">
              <th scope="row" className="py-2 pr-3 text-left font-medium">{r.horizon.toUpperCase()}</th>
              <td className="py-2 pr-3 text-right tabular">{cell(r.fund)}</td>
              <td className="py-2 pr-3 text-right tabular">{cell(r.benchmark)}</td>
              <td className="py-2 pr-3 text-right">{isNum(r.excess) ? <Delta value={r.excess} digits={2} /> : cell(null, states?.[`excess_${r.horizon}`])}</td>
              <td className="py-2 text-right tabular">{isNum(r.information_ratio) ? num(r.information_ratio, 2) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HistoryChart({ data }: { data: FundBenchmark }) {
  const [h, setH] = useState<(typeof HORIZONS)[number]>('3y');
  const history = useMemo(() => data.official?.history ?? [], [data.official]);
  const series = useMemo<Series[]>(() => {
    const pick = (key: string) => history.filter((r) => isNum(r[key])).map((r) => [String(r.date), (r[key] as number) / 100] as [string, number]);
    return [
      { id: 'fund', label: 'This plan', points: pick(`fund_${h}`), color: seriesColor(0) },
      { id: 'benchmark', label: data.benchmark ?? 'Benchmark', points: pick(`benchmark_${h}`), color: token('chart2'), dashed: true },
    ].filter((s) => s.points.length > 1);
  }, [history, h, data.benchmark]);
  if (history.length < 3) return null;
  return (
    <ChartFrame
      title={`Trailing ${h.toUpperCase()} return at each month-end`}
      subtitle="AMFI's figure for the plan and its Tier 1 benchmark TRI on each report date"
      controls={<Segmented label="Period" value={h} onChange={setH} options={HORIZONS.map((x) => ({ value: x, label: x.toUpperCase() }))} />}
      legend={series.map((s) => <LegendDot key={s.id} color={s.color!} dashed={s.dashed} label={s.label} />)}
      footnote="Where the plan line sits above the benchmark line, the plan beat its benchmark over the period ending that day."
      table={{ columns: ['Date', 'This plan', 'Benchmark'], rows: history.map((r) => [String(r.date), isNum(r[`fund_${h}`]) ? (r[`fund_${h}`] as number).toFixed(2) : '—', isNum(r[`benchmark_${h}`]) ? (r[`benchmark_${h}`] as number).toFixed(2) : '—']) }}
    >
      {series.length ? <TimeChart label={`Trailing ${h} return history`} height={240} series={series} zero format={(v) => pct(v, 1)} tick={pctTick} /> : <p className="py-10 text-center text-sm text-mf-muted">No history for this period yet.</p>}
    </ChartFrame>
  );
}

const PROXY_TILES = ['beta_3y', 'alpha_3y', 'te_3y', 'ir_3y_proxy', 'up_capture_3y', 'down_capture_3y', 'r2_3y'];

export function Benchmark({ code, metrics, fields }: FundTabProps) {
  const bench = useBenchmark(code);
  const b = bench.data;
  if (bench.isError) return <ErrorState error={bench.error} onRetry={() => bench.refetch()} />;
  if (!b) return <Skeleton className="h-96" />;
  if (!b.scheme) return <NoScheme reason={b.reason} />;
  const index = metrics.values.fund_type === 'index' || metrics.values.fund_type === 'etf';
  return (
    <div className="space-y-6">
      <Card
        title={b.benchmark ? `Against ${b.benchmark}` : 'Benchmark'}
        subtitle={`Tier 1 benchmark as AMFI shows it · AMFI report of ${date(b.official?.as_of)}${b.riskometer_benchmark ? ` · benchmark riskometer ${b.riskometer_benchmark}` : ''}`}
      >
        {b.official?.rows.length ? <OfficialTable rows={b.official.rows} states={b.states} /> : <p className="text-sm text-mf-muted">AMFI has not published returns for this scheme.</p>}
        <p className="mt-3 text-xs text-mf-muted">
          Returns over one year are a year. AMFI publishes these for the growth option of each plan, computed from the benchmark&rsquo;s total return index. {b.official?.source}.
        </p>
      </Card>
      <HistoryChart data={b} />
      <Card
        title={
          <span className="inline-flex flex-wrap items-center gap-2">
            Risk against the benchmark, 3 years <Badge tone="warning">Proxy</Badge>
          </span>
        }
        subtitle={
          b.proxy ? (
            <>
              Stand-in for {b.proxy.benchmark}:{' '}
              <Link className="text-mf-brand-strong underline underline-offset-2" to={`/mf/funds/${b.proxy.code}`}>
                {b.proxy.name}
              </Link>
              {isNum(b.proxy.tracking_error) ? `, filed tracking error ${b.proxy.tracking_error.toFixed(2)}%` : ''}
              {isNum(b.proxy.gap_3y) ? `, ${pct(b.proxy.gap_3y, 2, true)} a year against the index over 3Y` : ''}
            </>
          ) : (
            missingLabel(b.states?.beta_3y)
          )
        }
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
          {PROXY_TILES.map((id) => (
            <MetricTile key={id} metrics={metrics} fields={fields} id={id} />
          ))}
          {index && <MetricTile metrics={metrics} fields={fields} id="tracking_error" label="Tracking error filed with AMFI" />}
        </div>
        <p className="mt-3 text-xs text-mf-muted">{b.method} The licensed TRI series would replace the proxy; it is not stored because index terms bar it.</p>
      </Card>
      <p className="text-xs text-mf-muted">
        {formatField(fields.get('perf_as_of'), metrics.values.perf_as_of)} is the AMFI report behind the figures above. Past performance does not predict future returns.
      </p>
    </div>
  );
}
