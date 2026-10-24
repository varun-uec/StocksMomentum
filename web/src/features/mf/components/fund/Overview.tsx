/**
 * Fund overview (ui-ux doc 03 §03): three balanced evidence statements, the score
 * with its three equal parts, key metrics by window, essentials, then the growth
 * journey and the rolling distribution. A high score never hides a recent loss.
 */
import { useState } from 'react';
import type { FundDetail, Metrics } from '../../api';
import { categoryShort, date, formatField, isNum, missingLabel, pct } from '../../format';
import { Link } from 'react-router';
import { useDrawdowns, useFundRegimes, useScore } from '../../queries';
import { fallVerdict, recentVerdict } from '../../verdicts';
import { ScoreRing } from '../ScoreBadge';
import { I } from '../icons';
import { Badge, Card, Delta, DependencyPanel, ErrorState, InfoTip, Meter, Segmented, Skeleton, cx } from '../ui';
import { GrowthChart, MetricTile, RollingDistribution, type FundTabProps } from './shared';

const PART_LABELS: Record<string, string> = {
  consistency_3y: 'Consistency',
  ret_risk_3y: 'Return per volatility',
  mdd_3y: 'Drawdown control',
};

type Window = '1Y' | '3Y' | '5Y' | '10Y';
const TILES: Record<Window, { id: string; median?: string; rank?: string; label?: string }[]> = {
  '1Y': [
    { id: 'ret_1y', median: 'ret_1y_cat_median', label: 'Return 1Y' },
    { id: 'sharpe_1y' },
    { id: 'vol_1y', label: 'Volatility 1Y' },
    { id: 'mdd_1y', label: 'Max drawdown 1Y' },
    { id: 'ret_1y_cat_pct', label: 'Category percentile 1Y', rank: 'ret_1y_cat_rank' },
    { id: 'rolling_1y_positive_share', label: 'Positive 1Y periods' },
  ],
  '3Y': [
    { id: 'cagr_3y', median: 'cagr_3y_cat_median', label: 'CAGR 3Y' },
    { id: 'sharpe_3y', rank: 'sharpe_3y_cat_rank' },
    { id: 'vol_3y', median: 'vol_3y_cat_median', label: 'Volatility 3Y' },
    { id: 'mdd_3y', median: 'mdd_3y_cat_median', label: 'Max drawdown 3Y' },
    { id: 'sortino_3y', rank: 'sortino_3y_cat_rank' },
    { id: 'consistency_3y', median: 'consistency_3y_cat_median' },
  ],
  '5Y': [
    { id: 'cagr_5y', median: 'cagr_5y_cat_median', label: 'CAGR 5Y' },
    { id: 'cagr_5y_cat_pct', label: 'Category percentile 5Y', rank: 'cagr_5y_cat_rank' },
    { id: 'rolling_5y_median', label: 'Median 5Y rolling' },
    { id: 'rolling_5y_min', label: 'Worst 5Y rolling' },
    { id: 'rolling_5y_positive_share', label: 'Positive 5Y periods' },
    { id: 'q1_share_3y', label: 'Top-quartile share' },
  ],
  '10Y': [
    { id: 'cagr_10y', label: 'CAGR 10Y' },
    { id: 'cy_positive_share', label: 'Positive calendar years' },
    { id: 'cy_best', label: 'Best calendar year' },
    { id: 'cy_worst', label: 'Worst calendar year' },
    { id: 'mdd_since', label: 'Deepest fall on record' },
    { id: 'underwater_max_days', label: 'Longest below a peak' },
  ],
};

function Evidence({ metrics, fields }: Pick<FundTabProps, 'metrics' | 'fields'>) {
  const v = metrics.values;
  const n = (k: string) => (isNum(v[k]) ? (v[k] as number) : null);
  const cagr = n('cagr_3y');
  const median = n('cagr_3y_cat_median');
  const ddNow = n('dd_now');
  const ret1y = n('ret_1y');
  const pct1y = n('ret_1y_cat_pct');
  const items = [
    {
      icon: I.trend,
      title: 'Three-year growth',
      text:
        cagr === null
          ? `No 3Y CAGR: ${missingLabel(metrics.states.cagr_3y).toLowerCase()}.`
          : `${pct(cagr)} a year over 3 years${median === null ? '.' : `, ${cagr >= median ? 'above' : 'below'} the category median of ${pct(median)}.`}`,
      tone: cagr !== null && median !== null && cagr < median ? 'loss' : 'gain',
    },
    {
      icon: I.shield,
      title: 'Downside today',
      text:
        ddNow === null
          ? 'No current drawdown figure.'
          : ddNow < 0
            ? `${pct(ddNow)} below its last peak, for ${formatField(fields.get('dd_now_days'), v.dd_now_days)}. Worst 3Y fall ${pct(v.mdd_3y)}.`
            : `At its peak NAV. Worst 3Y fall ${pct(v.mdd_3y)}.`,
      tone: ddNow !== null && ddNow < -0.05 ? 'loss' : 'gain',
    },
    {
      icon: I.calendar,
      title: 'The last year',
      text:
        ret1y === null
          ? 'No 1Y return.'
          : `${pct(ret1y, 1, true)} over 1 year${pct1y === null ? '.' : `; ${pct1y.toFixed(0)}th percentile of its category.`}`,
      tone: ret1y !== null && ret1y < 0 ? 'loss' : 'gain',
    },
  ];
  return (
    <ul className="grid gap-3 md:grid-cols-3" aria-label="Key evidence">
      {items.map((item) => (
        <li key={item.title} className="flex gap-3 rounded-card border border-mf-line bg-mf-surface p-4 shadow-card">
          <span className={cx('grid h-9 w-9 shrink-0 place-items-center rounded-[10px]', item.tone === 'loss' ? 'bg-mf-loss-soft text-mf-loss' : 'bg-mf-brand-soft text-mf-brand')}>
            <item.icon />
          </span>
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.06em] text-mf-muted">{item.title}</p>
            <p className="mt-1 text-sm leading-relaxed text-mf-ink">{item.text}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** The verdict line and the three numbers a first-time investor asks for (audit U-02, U-13). */
export function FundHeadline({ code, metrics }: { code: string; metrics: Metrics }) {
  const score = useScore(code);
  const regimes = useFundRegimes(code);
  const drawdowns = useDrawdowns(code);
  const verdict = regimes.data && drawdowns.data ? fallVerdict(regimes.data.windows, drawdowns.data.drawdowns) : null;
  const recent = recentVerdict(metrics.values);
  const v = metrics.values;
  const category = categoryShort(String(v.category));
  const s = score.data;
  return (
    <div className="mt-2 grid gap-2 border-t border-mf-line pt-2 sm:mt-5 sm:gap-4 sm:pt-4 md:grid-cols-[auto_minmax(0,1fr)] lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:items-center">
      <div className="flex items-center gap-2 sm:gap-3">
        <span className="sm:hidden"><ScoreRing score={s?.score} size={44} /></span>
        <span className="hidden sm:inline-flex"><ScoreRing score={s?.score} /></span>
        <div className="text-sm">
          <p className="font-medium text-mf-ink">Wickstreet score</p>
          <p className="hidden text-mf-muted sm:block">{s?.rank ? `Rank ${s.rank} of ${s.peers_ranked} scored ${category} funds` : s ? missingLabel(s.state) : 'Loading…'}</p>
          <p className="text-mf-muted sm:hidden">{s?.rank ? `Rank ${s.rank} / ${s.peers_ranked} · ${category}` : s ? missingLabel(s.state) : 'Loading…'}</p>
          <Link to="?tab=peers" className="text-xs font-medium text-mf-brand hover:underline">How it ranks</Link>
        </div>
      </div>
      <div className="hidden space-y-2 text-[14px] leading-relaxed text-mf-ink-soft sm:text-[15px] md:order-none md:block" data-testid="fund-verdict">
        {recent && (
          <p>
            <span className="mr-1.5 inline-block rounded-full bg-mf-sunken px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-mf-muted">Recent</span>
            {recent}
          </p>
        )}
        {verdict ? (
          <p>
            <span className="mr-1.5 inline-block rounded-full bg-mf-loss-soft px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-mf-loss">Worst fall</span>
            {verdict.text}{' '}
            <Link to="?tab=risk#regimes" className="whitespace-nowrap text-sm font-medium text-mf-brand hover:underline">
              See every fall
            </Link>
          </p>
        ) : regimes.isLoading || drawdowns.isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <p>This fund has no NAV in a market-proxy fall window yet, so there is no fall to read.</p>
        )}
      </div>
      {/* On phones the three numbers come before the narrative, so they stay on the first screen. */}
      <p className="order-1 text-xs font-medium tabular text-mf-ink-soft sm:hidden">
        1Y {isNum(v.ret_1y) ? <Delta value={v.ret_1y} /> : '—'}
        <span className="mx-1 text-mf-muted">·</span>3Y {isNum(v.cagr_3y) ? <Delta value={v.cagr_3y} /> : '—'}
        <span className="mx-1 text-mf-muted">·</span>Worst 3Y {isNum(v.mdd_3y) ? <Delta value={v.mdd_3y} /> : '—'}
      </p>
      <dl className="hidden grid-cols-3 gap-2 text-center sm:order-none sm:grid md:col-span-2 lg:col-span-1 lg:w-[300px]">
        {[
          ['1Y return', v.ret_1y, 'ret_1y'],
          ['3Y CAGR', v.cagr_3y, 'cagr_3y'],
          ['Worst 3Y fall', v.mdd_3y, 'mdd_3y'],
        ].map(([label, value, id]) => (
          <div key={String(id)} className="rounded-[12px] bg-mf-surface/80 px-2 py-2 ring-1 ring-mf-line">
            <dt className="text-[11px] text-mf-muted">{String(label)}</dt>
            <dd className="mt-0.5 text-base font-semibold">{isNum(value) ? <Delta value={value} /> : <span className="text-mf-muted" title={missingLabel(metrics.states[String(id)])}>—</span>}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function ScoreCard({ code, metrics }: { code: string; metrics: Metrics }) {
  const score = useScore(code);
  const s = score.data;
  const category = categoryShort(String(metrics.values.category));
  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1">
          Wickstreet score
          <InfoTip label="the Wickstreet score">
            {s?.formula ?? 'Equal-weight mean of category percentiles.'} The parts are 3Y consistency, return per volatility and drawdown, each ranked against active peers in the same category, plan and option. Cost is not a part. A score is a historical ranking, not advice.
          </InfoTip>
        </span>
      }
    >
      {score.isError ? (
        <ErrorState error={score.error} compact />
      ) : !s ? (
        <Skeleton className="h-48" />
      ) : (
        <>
          <p className="flex items-baseline gap-1">
            <span className="text-[44px] font-semibold leading-none tabular">{isNum(s.score) ? Math.round(s.score) : '—'}</span>
            <span className="text-base text-mf-muted">/100</span>
          </p>
          <p className="mt-1 text-sm text-mf-ink-soft">
            {s.rank ? `Rank ${s.rank} of ${s.peers_ranked} scored funds in ${category}` : missingLabel(s.state)}
          </p>
          <div className="mt-3">
            <Meter value={s.score} label="Wickstreet score" />
          </div>
          <p className="mt-1 text-xs text-mf-muted">
            A fund is scored only when it has all three parts, so this count can be smaller than the category or a single measure’s peer count.
          </p>
          <ul className="mt-5 space-y-3">
            {s.parts.map((part) => (
              <li key={part.field}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="text-mf-ink-soft">{PART_LABELS[part.field] ?? part.field}</span>
                  <span className="tabular font-medium">{isNum(part.category_percentile) ? part.category_percentile.toFixed(0) : '—'}</span>
                </div>
                <Meter value={part.category_percentile} label={`${PART_LABELS[part.field]} percentile`} />
                <p className="mt-0.5 text-[11px] text-mf-muted">
                  {part.field === 'ret_risk_3y' ? part.value?.toFixed(2) : pct(part.value)} · of {part.peers_ranked ?? '—'} peers
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

function KeyMetrics({ metrics, fields }: Pick<FundTabProps, 'metrics' | 'fields'>) {
  const [window, setWindow] = useState<Window>('3Y');
  return (
    <Card title="Key metrics" action={<Segmented label="Window" value={window} onChange={setWindow} options={['1Y', '3Y', '5Y', '10Y'] as const} />}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {TILES[window].map((t) => (
          <MetricTile key={t.id} metrics={metrics} fields={fields} id={t.id} label={t.label} median={t.median} rank={t.rank} />
        ))}
      </div>
    </Card>
  );
}

export function Essentials({ detail, metrics }: { detail: FundDetail; metrics: Metrics }) {
  const f = detail.fund;
  const v = metrics.values;
  const rows: [string, string][] = [
    ['Fund house', f.amc],
    ['Category', f.category],
    ['Plan · option', `${f.plan} · ${f.option}`],
    ['Launch date', date(f.launch_date)],
    ['First stored NAV', date(detail.classification.since_start)],
    ['ISIN', f.isin_growth ?? f.isin_reinvest ?? '—'],
    ['AMFI code', f.amfi_code],
    ['Last NAV', `${date(detail.classification.last_nav_date)}`],
  ];
  return (
    <Card title="Fund essentials">
      <dl className="space-y-2.5 text-sm">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs text-mf-muted">{k}</dt>
            <dd className="break-words text-mf-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <dl className="mt-4 space-y-2.5 border-t border-mf-line pt-4 text-sm">
        {[
          ['Expense ratio', isNum(v.ter) ? `${pct(v.ter, 2)} a year${isNum(v.ter_cat_pct) ? ` · cheaper than ${Math.round(v.ter_cat_pct)}% of peers` : ''}` : missingLabel(metrics.states.ter)],
          ['AUM', isNum(v.aum_cr) ? `₹${Math.round(v.aum_cr).toLocaleString('en-IN')} Cr` : missingLabel(metrics.states.aum_cr)],
          ['Benchmark', typeof v.benchmark === 'string' ? v.benchmark : missingLabel(metrics.states.benchmark)],
          ['Riskometer', typeof v.riskometer === 'string' ? v.riskometer : missingLabel(metrics.states.riskometer)],
        ].map(([k, value]) => (
          <div key={k}>
            <dt className="text-xs text-mf-muted">{k}</dt>
            <dd className="break-words text-mf-ink">{value}</dd>
          </div>
        ))}
      </dl>
      <Link to="?tab=facts" className="mt-3 inline-flex text-xs font-medium text-mf-brand-strong hover:underline">
        Costs, managers and exit load
      </Link>
      {metrics.values.status !== 'active' && (
        <div className="mt-4">
          <DependencyPanel title="Historical plan" needs="a current NAV">
            This plan has no recent NAV, so returns end at its last NAV date.
          </DependencyPanel>
        </div>
      )}
    </Card>
  );
}

export function Overview({ code, metrics, fields, detail }: FundTabProps & { detail: FundDetail }) {
  return (
    <div className="flex flex-col gap-4 sm:gap-6">
      <div className="order-2 lg:order-1"><Evidence metrics={metrics} fields={fields} /></div>
      <div className="order-3 grid items-start gap-6 lg:order-2 lg:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1fr)]">
        <ScoreCard code={code} metrics={metrics} />
        <div className="lg:col-span-2 xl:col-span-1">
          <KeyMetrics metrics={metrics} fields={fields} />
        </div>
        <Essentials detail={detail} metrics={metrics} />
      </div>
      <div className="order-1 grid items-start gap-6 lg:order-3 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <GrowthChart code={code} metrics={metrics} />
        <RollingDistribution code={code} metrics={metrics} fields={fields} />
      </div>
    </div>
  );
}
