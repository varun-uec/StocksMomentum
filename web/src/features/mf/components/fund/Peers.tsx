/**
 * Fund peers: did the relative standing persist? Rank history uses AMFI's current
 * category labels for past months, and the page says so. The direct–regular gap
 * is an observed NAV gap, not the expense ratio; near-duplicates are NAV
 * correlations, not holdings overlap.
 */
import { useMemo } from 'react';
import { Link } from 'react-router';
import { categoryShort, enumLabel, formatField, inr, isNum, month, pct, schemeName } from '../../format';
import { useDirectRegular, useNearDuplicates, usePeers, useRankHistory } from '../../queries';
import { COMPARE_LIMIT } from '../../workspace';
import { seriesColor } from '../../theme/themes';
import { ChartFrame, LegendDot, TimeChart } from '../charts';
import { Card, Delta, ErrorState, Meter, Skeleton, buttonClass, cx } from '../ui';
import type { FundTabProps } from './shared';

const RANKED: { base: string; label: string; better: 'higher' | 'lower' }[] = [
  { base: 'score', label: 'Wickstreet score', better: 'higher' },
  { base: 'ret_1y', label: 'Return 1Y', better: 'higher' },
  { base: 'cagr_3y', label: 'CAGR 3Y', better: 'higher' },
  { base: 'cagr_5y', label: 'CAGR 5Y', better: 'higher' },
  { base: 'consistency_3y', label: 'Consistency 3Y', better: 'higher' },
  { base: 'sharpe_3y', label: 'Sharpe 3Y', better: 'higher' },
  { base: 'sortino_3y', label: 'Sortino 3Y', better: 'higher' },
  { base: 'vol_3y', label: 'Volatility 3Y', better: 'lower' },
  { base: 'mdd_3y', label: 'Max drawdown 3Y', better: 'higher' },
];

function RankHistory({ code }: { code: string }) {
  const ranks = useRankHistory(code);
  const series = useMemo(() => {
    const h = ranks.data?.history ?? [];
    const pts = (k: 'ret_1y' | 'cagr_3y') => h.filter((r) => r[k]).map((r) => [`${r.month}-28`, r[k]!.pct] as [string, number]);
    return [
      { id: 'ret_1y', label: 'Return 1Y percentile', points: pts('ret_1y'), color: seriesColor(0) },
      { id: 'cagr_3y', label: 'CAGR 3Y percentile', points: pts('cagr_3y'), color: seriesColor(1), dashed: true },
    ];
  }, [ranks.data]);
  const g = ranks.data?.group;
  return (
    <ChartFrame
      title="Standing in its category, month by month"
      subtitle={g ? `${categoryShort(g.category)} · ${enumLabel(g.plan)} ${enumLabel(g.option)} · 100 is the best of the peers alive that month` : undefined}
      legend={series.map((s) => <LegendDot key={s.id} color={s.color} dashed={s.dashed} label={s.label} />)}
      footnote="Past months use today's AMFI category labels; a fund that changed category may be ranked against a group it did not belong to then."
      table={{
        columns: ['Month', 'Return 1Y rank', 'CAGR 3Y rank'],
        rows: (ranks.data?.history ?? []).map((r) => [month(r.month), r.ret_1y ? `${r.ret_1y.rank}/${r.ret_1y.count}` : '—', r.cagr_3y ? `${r.cagr_3y.rank}/${r.cagr_3y.count}` : '—']),
      }}
    >
      {ranks.isError ? <ErrorState error={ranks.error} compact /> : ranks.isLoading ? <Skeleton className="h-[240px]" /> : <TimeChart label="Category percentile over time" height={240} series={series} yDomain={[0, 100]} format={(v) => v.toFixed(0)} />}
    </ChartFrame>
  );
}

function CurrentRanks({ metrics, fields }: Pick<FundTabProps, 'metrics' | 'fields'>) {
  const v = metrics.values;
  return (
    <Card title="Where it ranks today" subtitle={`Against active ${categoryShort(String(v.category))} peers with the same plan and option`}>
      <ul className="space-y-3.5">
        {RANKED.map((r) => {
          const rank = v[`${r.base}_cat_rank`];
          const count = v[`${r.base}_cat_count`];
          const pctile = v[`${r.base}_cat_pct`] as number | null;
          return (
            <li key={r.base}>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="text-mf-ink-soft">{r.label}</span>
                <span className="tabular">
                  {rank == null ? <span className="text-mf-muted">Not ranked</span> : <><b>{String(rank)}</b> <span className="text-mf-muted">of {String(count)}</span></>}
                </span>
              </div>
              <Meter value={pctile} label={`${r.label} category percentile`} />
              <p className="mt-0.5 text-[11px] text-mf-muted">
                Fund {formatField(fields.get(r.base), v[r.base], fields)}
                {v[`${r.base}_cat_median`] != null && ` · median ${formatField(fields.get(`${r.base}_cat_median`), v[`${r.base}_cat_median`], fields)}`}
                {r.better === 'lower' && ' · lower is better'}
              </p>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function DirectRegular({ code }: { code: string }) {
  const dr = useDirectRegular(code);
  const d = dr.data;
  return (
    <Card title="Direct versus regular" subtitle="The same scheme bought with and without distributor commission">
      {dr.isError ? (
        <ErrorState error={dr.error} compact />
      ) : !d ? (
        <Skeleton className="h-32" />
      ) : !d.pair ? (
        <p className="text-sm text-mf-muted">No matching direct–regular pair is on record for this plan.</p>
      ) : (
        <>
          <table className="w-full text-sm">
            <thead className="text-xs text-mf-muted">
              <tr className="border-b border-mf-line">
                <th scope="col" className="py-2 text-left font-medium">Plan</th>
                <th scope="col" className="py-2 text-right font-medium">1Y</th>
                <th scope="col" className="py-2 text-right font-medium">3Y CAGR</th>
                <th scope="col" className="py-2 text-right font-medium">5Y CAGR</th>
              </tr>
            </thead>
            <tbody>
              {(['direct', 'regular'] as const).map((k) => (
                <tr key={k} className="border-b border-mf-line last:border-0">
                  <th scope="row" className="py-2.5 text-left font-normal">
                    {d.pair![k].amfi_code === code ? <b>{enumLabel(k)}</b> : <Link className="text-mf-brand hover:underline" to={`/mf/funds/${d.pair![k].amfi_code}`}>{enumLabel(k)}</Link>}
                  </th>
                  <td className="py-2.5 text-right"><Delta value={d.pair![k].ret_1y} /></td>
                  <td className="py-2.5 text-right"><Delta value={d.pair![k].cagr_3y} /></td>
                  <td className="py-2.5 text-right"><Delta value={d.pair![k].cagr_5y} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-sm text-mf-ink-soft">
            Gap: <b className="tabular">{pct(d.dr_gap_1y, 2)}</b> over 1Y, <b className="tabular">{pct(d.dr_gap_3y, 2)}</b> a year over 3Y. ₹10 lakh grown for 10 years at each plan’s 3Y CAGR ends <b className="tabular">{inr(d.dr_wealth_10y, true)}</b> apart.
          </p>
          <p className="mt-1 text-xs text-mf-muted">{d.label}</p>
        </>
      )}
    </Card>
  );
}

/** The fund beside its largest peers, the alternatives an investor weighs first (assessment 25 Oct, rank 2). */
function LargestPeers({ code, metrics }: Pick<FundTabProps, 'code' | 'metrics'>) {
  const { peers, isError, error } = usePeers(code, metrics.values, COMPARE_LIMIT - 1);
  const rows = [{ amfi_code: code, name: metrics.name, values: metrics.values }, ...(peers ?? [])];
  const cost = (v: unknown) => (isNum(v) ? pct(v, 2) : '—');
  const size = (v: unknown) => (isNum(v) ? `₹${Math.round(v).toLocaleString('en-IN')} Cr` : '—');
  const ret = (v: unknown) => (isNum(v) ? <Delta value={v} /> : <span className="text-mf-muted">—</span>);
  return (
    <Card
      title={`Largest ${categoryShort(String(metrics.values.category))} peers`}
      subtitle="By assets under management, same plan and option · the latest snapshot"
      action={peers?.length ? <Link to={`/mf/compare?${rows.map((r) => `code=${r.amfi_code}`).join('&')}`} className={buttonClass('primary', 'sm')}>Compare these {rows.length}</Link> : undefined}
    >
      {isError ? (
        <ErrorState error={error} compact />
      ) : !peers ? (
        <Skeleton className="h-40" />
      ) : (
        <>
        {/* Phones: one block per fund, so no number sits past the edge. */}
        <ul className="divide-y divide-mf-line sm:hidden">
          {rows.map((r) => (
            <li key={r.amfi_code} className="py-3">
              {r.amfi_code === code ? (
                <p className="font-semibold text-mf-ink">{schemeName(r.name)} <span className="font-normal text-mf-muted">· this fund</span></p>
              ) : (
                <Link to={`/mf/funds/${r.amfi_code}`} className="font-medium text-mf-ink hover:text-mf-brand-strong">{schemeName(r.name)}</Link>
              )}
              <dl className="mt-1.5 grid grid-cols-3 gap-x-3 gap-y-1.5 text-sm tabular">
                {([['1Y', ret(r.values.ret_1y)], ['3Y CAGR', ret(r.values.cagr_3y)], ['Worst 3Y fall', ret(r.values.mdd_3y)], ['TER', cost(r.values.ter)], ['AUM', size(r.values.aum_cr)]] as const).map(([k, value]) => (
                  <div key={k} className={cx('min-w-0', k === 'AUM' && 'col-span-2')}>
                    <dt className="text-[11px] text-mf-muted">{k}</dt>
                    <dd className="font-medium">{value}</dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ul>
        <div className="mf-scroll -mx-1 hidden overflow-x-auto px-1 sm:block">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="text-xs text-mf-muted">
              <tr className="border-b border-mf-line">
                <th scope="col" className="py-2 text-left font-medium">Fund</th>
                <th scope="col" className="py-2 text-right font-medium">1Y</th>
                <th scope="col" className="py-2 text-right font-medium">3Y CAGR</th>
                <th scope="col" className="py-2 text-right font-medium">Worst 3Y fall</th>
                <th scope="col" className="py-2 text-right font-medium">TER</th>
                <th scope="col" className="py-2 text-right font-medium">AUM</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.amfi_code} className="border-b border-mf-line last:border-0">
                  <th scope="row" className="max-w-[220px] py-2.5 pr-3 text-left font-normal">
                    {r.amfi_code === code ? (
                      <span className="block truncate font-semibold text-mf-ink">{schemeName(r.name)} <span className="font-normal text-mf-muted">· this fund</span></span>
                    ) : (
                      <Link to={`/mf/funds/${r.amfi_code}`} className="block truncate text-mf-ink hover:text-mf-brand-strong">{schemeName(r.name)}</Link>
                    )}
                  </th>
                  <td className="py-2.5 text-right tabular">{ret(r.values.ret_1y)}</td>
                  <td className="py-2.5 text-right tabular">{ret(r.values.cagr_3y)}</td>
                  <td className="py-2.5 text-right tabular">{ret(r.values.mdd_3y)}</td>
                  <td className="py-2.5 text-right tabular">{cost(r.values.ter)}</td>
                  <td className="py-2.5 text-right tabular">{size(r.values.aum_cr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}
    </Card>
  );
}

function NearDuplicates({ code }: { code: string }) {
  const nd = useNearDuplicates(code);
  return (
    <Card title="Funds that move almost the same way" subtitle="Daily-return correlation of 0.95 or more. This is not a holdings overlap.">
      {!nd.data ? (
        <Skeleton className="h-20" />
      ) : nd.data.listed.length === 0 ? (
        <p className="text-sm text-mf-muted">No other fund’s daily returns track this one that closely.</p>
      ) : (
        <ul className="divide-y divide-mf-line">
          {nd.data.listed.map((f) => (
            <li key={f.amfi_code} className="flex items-center gap-3 py-2.5 text-sm">
              <Link to={`/mf/funds/${f.amfi_code}`} className="min-w-0 flex-1 truncate text-mf-ink hover:text-mf-brand-strong">
                {f.name}
              </Link>
              <span className="tabular">{f.correlation.toFixed(3)}</span>
              <span className="text-xs text-mf-muted">{f.common_days} days</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function Peers({ code, metrics, fields }: FundTabProps) {
  const v = metrics.values;
  const studio = `/mf/studio?mode=frontier&category=${encodeURIComponent(String(v.category))}&plan=${v.plan}&option=${v.option}&code=${code}`;
  return (
    <div className="space-y-6">
      <LargestPeers code={code} metrics={metrics} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <RankHistory code={code} />
        <CurrentRanks metrics={metrics} fields={fields} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <DirectRegular code={code} />
        <NearDuplicates code={code} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Link to={studio} className={buttonClass('secondary')}>
          See its peers on the risk–return map
        </Link>
        <Link to={`/mf/studio?mode=ranks&code=${code}`} className={buttonClass('ghost')}>
          Rank persistence in the studio
        </Link>
      </div>
    </div>
  );
}
