/**
 * Compare (ui-ux doc 03 §05): 2–5 exact plan-options, one common start, aligned
 * metrics and daily-return correlations. Funds in different categories get no
 * combined score winner, and correlation is never called holdings overlap.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { pctTick } from '../axis';
import { ChartFrame, LegendDot, PeerScatter, TimeChart, mergeSeries, thin } from '../components/charts';
import { startingFunds, useRecentFunds } from '../context';
import { rebase } from '../series';
import { FundSearch } from '../components/FundSearch';
import { I } from '../components/icons';
import { ScoreBadge } from '../components/ScoreBadge';
import { Badge, Button, Card, Chip, EmptyState, ErrorState, Loading, PageHeader, Segmented, SnapshotNote, buttonClass, cx, useTitle } from '../components/ui';
import { categoryShort, date, formatField, inr, inrTick, isNum, missingLabel, pct, schemeName } from '../format';
import { useCompare, useFields } from '../queries';
import { heat, seriesColor, token } from '../theme/themes';
import { COMPARE_LIMIT, setTray, useCompareTray, useRecordMutations, type WatchlistBody } from '../workspace';

type Better = 'higher' | 'lower' | null;
const PERIODS = { '1Y': 1, '3Y': 3, '5Y': 5, All: 0 } as const;
type Period = keyof typeof PERIODS;
const GROUPS: { title: string; rows: { id: string; better: Better; label?: string }[] }[] = [
  {
    title: 'Growth',
    rows: [
      { id: 'ret_1y', better: 'higher' },
      { id: 'cagr_3y', better: 'higher' },
      { id: 'cagr_5y', better: 'higher' },
      { id: 'cagr_10y', better: 'higher' },
      { id: 'ret_ytd', better: 'higher' },
    ],
  },
  {
    title: 'Consistency',
    rows: [
      { id: 'consistency_3y', better: 'higher' },
      { id: 'rolling_3y_positive_share', better: 'higher' },
      { id: 'rolling_3y_median', better: 'higher' },
      { id: 'cy_positive_share', better: 'higher' },
    ],
  },
  {
    title: 'Downside',
    rows: [
      { id: 'mdd_3y', better: 'higher' },
      { id: 'dd_now', better: 'higher' },
      { id: 'worst_1y', better: 'higher' },
      { id: 'vol_3y', better: 'lower' },
      { id: 'cvar95_3y', better: 'higher' },
    ],
  },
  {
    title: 'Return for the risk',
    rows: [
      { id: 'sharpe_3y', better: 'higher' },
      { id: 'sortino_3y', better: 'higher' },
      { id: 'ret_risk_3y', better: 'higher' },
    ],
  },
  {
    title: 'Standing in its own category',
    rows: [
      { id: 'score', better: null },
      { id: 'score_cat_rank', better: null },
      { id: 'cagr_3y_cat_pct', better: null },
    ],
  },
];

export default function Compare() {
  useTitle('Compare funds');
  const [params, setParams] = useSearchParams();
  const tray = useCompareTray();
  const codes = useMemo(() => params.getAll('code').filter((c, i, a) => /^\d{1,9}$/.test(c) && a.indexOf(c) === i).slice(0, COMPARE_LIMIT), [params]);
  const fields = useFields();
  const compare = useCompare(codes);
  const { create } = useRecordMutations<WatchlistBody>('watchlist');

  // Opening /mf/compare with no codes takes the tray's selection, else the funds
  // opened last, else the examples, so the page opens on a chart (audit U-01).
  const recent = useRecentFunds();
  const [example, setExample] = useState(false);
  useEffect(() => {
    if (codes.length) return;
    const start = tray.funds.length ? { codes: tray.funds.map((f) => f.code), example: false } : startingFunds(recent, 3);
    setExample(start.example);
    setParams(new URLSearchParams(start.codes.map((c) => ['code', c])), { replace: true });
  }, [codes.length, tray.funds, recent, setParams]);
  const [period, setPeriod] = useState<Period>('All');

  // Keep the tray in step with the page, so other pages show the same selection.
  const data = compare.data;
  useEffect(() => {
    if (data && !example) setTray(codes.map((code) => ({ code, name: data.funds.find((f) => f.amfi_code === code)?.name ?? code })));
  }, [data, codes, example]);

  const setCodes = (next: string[]) => {
    setExample(false);
    setParams(new URLSearchParams(next.map((c) => ['code', c])));
  };
  const funds = codes.map((code) => data?.funds.find((f) => f.amfi_code === code)).filter((f) => !!f);
  const categories = new Set(funds.map((f) => String(f.values.category)));
  const full = funds.map((f, i) => ({ id: f.amfi_code, label: schemeName(f.name), points: data?.series[f.amfi_code] ?? [], color: seriesColor(i) }));
  // A shorter window rebases the common series at the window's first shared date: a change of units, not a new measure.
  const last = full[0]?.points[full[0].points.length - 1]?.[0];
  const windowStart = last && period !== 'All' ? `${Number(last.slice(0, 4)) - PERIODS[period]}${last.slice(4)}` : null;
  const available = (p: Period) => p === 'All' || (!!last && !!data && `${Number(last.slice(0, 4)) - PERIODS[p]}${last.slice(4)}` >= data.start);
  const series = windowStart && available(period) ? full.map((s) => ({ ...s, points: rebase(s.points, 100, windowStart) })) : full;

  const header = (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {codes.map((code, i) => {
          const f = data?.funds.find((x) => x.amfi_code === code);
          return (
            <Chip key={code} onRemove={() => setCodes(codes.filter((c) => c !== code))}>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: seriesColor(i) }} aria-hidden="true" />
                {f ? schemeName(f.name) : code}
              </span>
            </Chip>
          );
        })}
        {codes.length < COMPARE_LIMIT ? (
          <FundSearch className="w-full sm:w-80" label="Add a fund to compare" placeholder="Add a fund (up to 5)" onPick={(f) => setCodes([...codes.filter((c) => c !== f.amfi_code), f.amfi_code])} />
        ) : (
          <p className="text-sm text-mf-muted">Five funds is the limit. Remove one to add another.</p>
        )}
      </div>
    </div>
  );

  if (codes.length < 2)
    return (
      <div className="space-y-6">
        <PageHeader title="Compare funds" lead="Put two to five funds side by side over the same dates." />
        {header}
        <EmptyState title={codes.length ? 'Add one more fund' : 'Choose funds to compare'} art={<I.compare className="mb-3 h-8 w-8 text-mf-brand" />}>
          Search above, or use the compare button on any fund or screener row. Compare plans with the same option, such as two Direct Growth plans, for a fair view.
        </EmptyState>
      </div>
    );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compare funds"
        lead="The same start date, the same metrics, side by side."
        actions={
          <>
            <Link to={`/mf/simulate?code=${codes[0]}`} className={buttonClass('secondary')}>
              <I.lab className="h-4 w-4" />
              Test an investment
            </Link>
            <Button disabled={!data || create.isPending} onClick={() => create.mutate({ name: `Comparison · ${funds.map((f) => schemeName(f.name).split(' ')[0]).join(', ')}`.slice(0, 120), body: { codes } })}>
              <I.star className="h-4 w-4" />
              {create.isSuccess ? 'Saved as a watchlist' : 'Save as watchlist'}
            </Button>
          </>
        }
      />
      {header}
      {compare.isError ? (
        <ErrorState error={compare.error} onRetry={() => compare.refetch()} />
      ) : !data ? (
        <Loading label="Comparing" />
      ) : (
        <div className={cx('space-y-6', compare.isPlaceholderData && 'opacity-60')}>
          <div className="rounded-[12px] border border-mf-info/30 bg-mf-info-soft/60 px-4 py-3 text-sm text-mf-ink-soft">
            The growth chart starts on <b>{date(data.start)}</b>, the first date every selected fund has a NAV. Metrics below keep their own trailing windows.
            {categories.size > 1 && ' These funds are in different categories, so their scores rank them against different peers; a higher score is not a win across categories.'}
          </div>
          {example && (
            <p className="text-sm text-mf-muted">These are example funds. Remove them and add your own, or use the compare button on any fund.</p>
          )}
          <ChartFrame
            title={period === 'All' ? 'Growth of ₹10,000 from the common start' : `Growth of ₹10,000 over ${period}`}
            subtitle={`From ${date(series[0]?.points[0]?.[0])}; NAV rebased, before tax`}
            controls={<Segmented label="Window" value={period} onChange={setPeriod} options={(Object.keys(PERIODS) as Period[]).map((p) => ({ value: p, label: p, disabled: !available(p) }))} />}
            legend={series.map((s) => (
              <LegendDot key={s.id} color={s.color} label={<>{s.label} <b className="tabular">{inr(((s.points[s.points.length - 1]?.[1] ?? NaN) / 100) * 10_000)}</b></>} />
            ))}
            // Same unit as the plot: rupees from ₹10,000 (audit A-13).
            table={{ columns: ['Date', ...series.map((s) => s.label)], rows: thin(mergeSeries(series), 120).map((r) => [date(String(r.date)), ...series.map((s) => (typeof r[s.id] === 'number' ? inr(((r[s.id] as number) / 100) * 10_000) : '—'))]) }}
          >
            <TimeChart label="Rebased growth of the selected funds" height={320} zoom series={series} format={(v) => inr((v / 100) * 10_000)} tick={(v) => inrTick((v / 100) * 10_000)} />
          </ChartFrame>

          {funds.filter((f) => isNum(f.values.vol_3y) && isNum(f.values.cagr_3y)).length >= 2 && (
            <ChartFrame
              title="The trade-off: return against volatility, 3 years"
              subtitle="Up and to the left is more return for less volatility"
              table={{ columns: ['Fund', 'CAGR 3Y', 'Volatility 3Y'], rows: funds.map((f) => [schemeName(f.name), pct(f.values.cagr_3y), pct(f.values.vol_3y)]) }}
            >
              <PeerScatter
                label="Return against volatility of the selected funds"
                points={funds.map((f, i) => ({ f, color: seriesColor(i) })).filter(({ f }) => isNum(f.values.vol_3y) && isNum(f.values.cagr_3y)).map(({ f, color }) => ({ id: f.amfi_code, name: f.name, x: f.values.vol_3y as number, y: f.values.cagr_3y as number, highlight: true, color }))}
                xLabel="Volatility 3Y"
                yLabel="CAGR 3Y"
                format={(v) => pct(v, 1)}
                tick={pctTick}
                height={300}
              />
            </ChartFrame>
          )}

          <Card title="Side by side" subtitle="A mark shows the strongest value in a row. Category standing compares each fund with its own peers.">
            <div className="mf-scroll overflow-x-auto" role="region" aria-label="Metric comparison" tabIndex={0}>
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-mf-line">
                    <th scope="col" className="sticky left-0 bg-mf-surface py-3 text-left text-xs font-medium text-mf-muted">Metric</th>
                    {funds.map((f, i) => (
                      <th key={f.amfi_code} scope="col" className="min-w-[150px] px-3 py-3 text-right align-bottom font-medium">
                        <Link to={`/mf/funds/${f.amfi_code}`} className="inline-flex items-start gap-1.5 text-right hover:text-mf-brand-strong">
                          <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: seriesColor(i) }} aria-hidden="true" />
                          <span className="line-clamp-2">{schemeName(f.name)}</span>
                        </Link>
                        <p className="text-xs font-normal text-mf-muted">{categoryShort(String(f.values.category))}</p>
                      </th>
                    ))}
                  </tr>
                </thead>
                {GROUPS.map((g) => (
                  <tbody key={g.title}>
                    <tr>
                      <th colSpan={funds.length + 1} scope="colgroup" className="pb-1 pt-4 text-left text-xs font-semibold uppercase tracking-[0.08em] text-mf-brand">
                        {g.title}
                      </th>
                    </tr>
                    {g.rows.map((r) => {
                      const field = fields.byId.get(r.id);
                      const values = funds.map((f) => f.values[r.id]);
                      const nums = values.filter(isNum);
                      const best = r.better && nums.length > 1 ? (r.better === 'higher' ? Math.max(...nums) : Math.min(...nums)) : null;
                      return (
                        <tr key={r.id} className="border-b border-mf-line last:border-0">
                          <th scope="row" className="sticky left-0 bg-mf-surface py-2.5 pr-3 text-left font-normal text-mf-ink-soft" title={field?.description}>
                            {field?.label ?? r.id}
                          </th>
                          {funds.map((f, i) => {
                            const v = values[i];
                            if (r.id === 'score') return <td key={f.amfi_code} className="px-3 py-2 text-right"><ScoreBadge score={v as number | null} size="sm" /></td>;
                            const missing = v === null || v === undefined;
                            const isBest = best !== null && v === best;
                            return (
                              <td key={f.amfi_code} className={cx('px-3 py-2.5 text-right tabular', isBest && 'font-semibold text-mf-brand-strong', isNum(v) && v < 0 && field?.unit === 'fraction' && !isBest && 'text-mf-loss')}>
                                {missing ? (
                                  <span className="text-xs text-mf-muted">{missingLabel(f.states[r.id])}</span>
                                ) : r.id === 'score_cat_rank' ? (
                                  `${v} of ${f.values.score_cat_count ?? '—'}`
                                ) : (
                                  formatField(field, v, fields.byId)
                                )}
                                {isBest && <span className="sr-only"> (strongest)</span>}
                                {isBest && <I.check className="ml-1 inline h-3.5 w-3.5" />}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                ))}
              </table>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {['Expense ratio (E1)', 'Exit load (E1)', 'Holdings overlap (E4)'].map((t) => (
                <Badge key={t} tone="planned">Planned · {t}</Badge>
              ))}
            </div>
          </Card>

          <Card title="Do their daily returns move together?" subtitle="Correlation of daily NAV returns over the dates both funds share. 1 means they move in lockstep. It does not measure shared holdings.">
            <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
              <table className="border-separate border-spacing-1 text-sm">
                <thead>
                  <tr>
                    <td />
                    {funds.map((f, i) => (
                      <th key={f.amfi_code} scope="col" className="w-24 text-center text-xs font-medium text-mf-muted">
                        <span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full" style={{ background: seriesColor(i) }} aria-hidden="true" />
                        {schemeName(f.name).split(' ').slice(0, 2).join(' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {funds.map((a, i) => (
                    <tr key={a.amfi_code}>
                      <th scope="row" className="pr-2 text-left text-xs font-medium text-mf-muted">{schemeName(a.name).split(' ').slice(0, 3).join(' ')}</th>
                      {funds.map((b, j) => {
                        const pair = data.correlations.find((p) => (p.a === a.amfi_code && p.b === b.amfi_code) || (p.a === b.amfi_code && p.b === a.amfi_code));
                        const c = i === j ? 1 : pair?.correlation ?? null;
                        return (
                          <td key={b.amfi_code} className="h-14 w-24 rounded-[8px] text-center tabular" style={{ background: c === null ? token('sunken') : heat('brand', c) }} title={pair ? `${pair.observations} shared days` : undefined}>
                            <span className="block font-semibold">{c === null ? '—' : c.toFixed(2)}</span>
                            {pair && i !== j && <span className="text-[10px] text-mf-ink-soft">{pair.observations.toLocaleString('en-IN')} days</span>}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {isNum(data.average_correlation) && <p className="mt-3 text-sm text-mf-ink-soft">Average pairwise correlation: <b className="tabular">{data.average_correlation.toFixed(2)}</b>. Close to 1 means little diversification between these funds.</p>}
          </Card>
          <SnapshotNote asOf={data.as_of} revision={data.data_revision} method={data.method_version} />
        </div>
      )}
    </div>
  );
}
