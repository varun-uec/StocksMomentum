/** Fund performance: trailing returns against the category, annual and monthly returns, rolling returns over time. */
import { useMemo, useState } from 'react';
import { pctTick } from '../../axis';
import { date, isNum, missingLabel, pct } from '../../format';
import { useAnnual, useRolling } from '../../queries';
import { seriesColor } from '../../theme/themes';
import { ChartFrame, MonthHeatmap, PeriodBars, TimeChart, thin } from '../charts';
import { Card, Delta, ErrorState, Segmented, Skeleton } from '../ui';
import { GrowthChart, RollingDistribution, type FundTabProps } from './shared';

const TRAILING: { label: string; id: string; median?: string; pct?: string; annualised?: boolean }[] = [
  { label: '1 month', id: 'ret_1m' },
  { label: '3 months', id: 'ret_3m' },
  { label: '6 months', id: 'ret_6m' },
  { label: 'Year to date', id: 'ret_ytd' },
  { label: '1 year', id: 'ret_1y', median: 'ret_1y_cat_median', pct: 'ret_1y_cat_pct' },
  { label: '3 years', id: 'cagr_3y', median: 'cagr_3y_cat_median', pct: 'cagr_3y_cat_pct', annualised: true },
  { label: '5 years', id: 'cagr_5y', median: 'cagr_5y_cat_median', pct: 'cagr_5y_cat_pct', annualised: true },
  { label: '10 years', id: 'cagr_10y', annualised: true },
  { label: 'Since first NAV', id: 'cagr_since', annualised: true },
];

const NO_PEER_FIGURE = 'Category figures cover 1, 3 and 5 years only';

/** A dash with its reason, for screen readers and on hover (audit F-11). */
function Reason({ text }: { text: string }) {
  return (
    <span className="text-mf-muted" title={text}>
      —<span className="sr-only"> {text}</span>
    </span>
  );
}

function Trailing({ metrics }: Pick<FundTabProps, 'metrics'>) {
  const v = metrics.values;
  return (
    <Card title="Trailing returns" subtitle="Up to 1 year: total change. 3 years and longer: CAGR, the yearly growth rate. Category figures use active peers with the same plan and option.">
      <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="text-xs text-mf-muted">
            <tr className="border-b border-mf-line">
              <th scope="col" className="py-2 text-left font-medium">Period</th>
              <th scope="col" className="py-2 text-right font-medium">Fund</th>
              <th scope="col" className="py-2 text-right font-medium">Category median</th>
              <th scope="col" className="py-2 text-right font-medium">Percentile</th>
              <th scope="col" className="py-2 text-right font-medium">From</th>
            </tr>
          </thead>
          <tbody>
            {TRAILING.map((t) => (
              <tr key={t.id} className="border-b border-mf-line last:border-0">
                <th scope="row" className="py-2.5 text-left font-normal text-mf-ink-soft">
                  {t.label}
                  {t.annualised && <span className="ml-1 text-xs text-mf-muted">a year</span>}
                </th>
                <td className="py-2.5 text-right font-medium">
                  {isNum(v[t.id]) ? <Delta value={v[t.id]} /> : <Reason text={missingLabel(metrics.states[t.id])} />}
                </td>
                <td className="py-2.5 text-right tabular text-mf-ink-soft">{t.median ? (isNum(v[t.median]) ? pct(v[t.median]) : <Reason text={missingLabel(metrics.states[t.median])} />) : <Reason text={NO_PEER_FIGURE} />}</td>
                <td className="py-2.5 text-right tabular text-mf-ink-soft">{t.pct ? (isNum(v[t.pct]) ? (v[t.pct] as number).toFixed(0) : <Reason text={missingLabel(metrics.states[t.pct])} />) : <Reason text={NO_PEER_FIGURE} />}</td>
                <td className="py-2.5 text-right text-xs text-mf-muted">{t.id === 'cagr_since' ? date(v.since_start) : date(metrics.anchors[t.id])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-mf-muted">— {NO_PEER_FIGURE.toLowerCase()}; hover a dash for its reason.</p>
    </Card>
  );
}

function Annual({ code }: { code: string }) {
  const annual = useAnnual(code);
  const [basis, setBasis] = useState<'calendar' | 'financial'>('calendar');
  const rows = (annual.data?.[basis] ?? []).map((r) => ({ period: basis === 'financial' ? r.period.replace('FY', 'FY ') : r.period, value: r.return, partial: r.partial }));
  return (
    <ChartFrame
      title="Year by year"
      subtitle="Hatched bars are part years: the first and last years of the stored history"
      controls={<Segmented label="Year basis" value={basis} onChange={setBasis} options={[{ value: 'calendar', label: 'Calendar' }, { value: 'financial', label: 'Financial (Apr–Mar)' }]} />}
      table={{ columns: ['Year', 'Return', 'Part year'], rows: rows.map((r) => [r.period, pct(r.value), r.partial ? 'Yes' : '']) }}
    >
      {annual.isError ? <ErrorState error={annual.error} compact /> : annual.isLoading ? <Skeleton className="h-[220px]" /> : <PeriodBars label={`${basis} year returns`} rows={rows} format={(x) => pct(x, 1)} tick={pctTick} />}
    </ChartFrame>
  );
}

function Monthly({ code }: { code: string }) {
  const annual = useAnnual(code);
  return (
    <Card title="Monthly returns" subtitle="Each cell is one calendar month's NAV change">
      {annual.isError ? <ErrorState error={annual.error} compact /> : annual.isLoading ? <Skeleton className="h-40" /> : <MonthHeatmap rows={annual.data!.monthly} format={(x) => pct(x, 1)} />}
    </Card>
  );
}

function RollingOverTime({ code }: { code: string }) {
  const [window, setWindow] = useState<'1y' | '3y' | '5y'>('3y');
  const rolling = useRolling(code, window);
  const points = useMemo(() => thin(rolling.data?.points ?? [], 700), [rolling.data]);
  return (
    <ChartFrame
      title={`Rolling ${window.toUpperCase()} return over time`}
      subtitle="Each point is the annualised return of the period that ended that day"
      controls={<Segmented label="Holding period" value={window} onChange={setWindow} options={[{ value: '1y', label: '1Y' }, { value: '3y', label: '3Y' }, { value: '5y', label: '5Y' }]} />}
      table={{ columns: ['Period end', 'Return'], rows: thin(points, 150).map(([d, x]) => [date(d), pct(x)]) }}
    >
      {rolling.isError ? (
        <ErrorState error={rolling.error} compact />
      ) : rolling.isLoading ? (
        <Skeleton className="h-[240px]" />
      ) : points.length < 2 ? (
        <p className="py-12 text-center text-sm text-mf-muted">The history is too short for this holding period.</p>
      ) : (
        <TimeChart label={`Rolling ${window} return`} zero area height={240} series={[{ id: 'r', label: 'Rolling return', points, color: seriesColor(0) }]} format={(x) => pct(x, 1)} tick={pctTick} />
      )}
    </ChartFrame>
  );
}

export function Performance({ code, metrics, fields }: FundTabProps) {
  return (
    <div className="space-y-6">
      <GrowthChart code={code} metrics={metrics} height={320} />
      <div className="grid gap-6 xl:grid-cols-2">
        <Trailing metrics={metrics} />
        <Annual code={code} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <RollingOverTime code={code} />
        <RollingDistribution code={code} metrics={metrics} fields={fields} initial="1y" />
      </div>
      <Monthly code={code} />
    </div>
  );
}
