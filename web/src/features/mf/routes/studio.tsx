/**
 * Analytics studio (ui-ux doc 03 §04): question-led modes over the research API.
 * Every figure is a service result; the studio arranges and labels it. Mode, funds
 * and peer group live in the URL, so a view survives reload and can be saved.
 * Distinct from Momentum25's Strategy Studio at /studio.
 */
import { useQueries, useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { pctTick } from '../axis';
import { mfApi, type Backtest, type BacktestPeriod, type PeerGroup } from '../api';
import { ChartFrame, LegendDot, PairBars, PeerScatter, TimeChart, thin } from '../components/charts';
import { FundSearch } from '../components/FundSearch';
import { I } from '../components/icons';
import { Badge, Button, Card, Chip, EmptyState, ErrorState, Field, PageHeader, Segmented, Skeleton, SnapshotNote, TabLinks, cx, inputClass, useTitle } from '../components/ui';
import { categoryShort, date, enumLabel, month, pct, schemeName } from '../format';
import { useFields, useFrontier, useFundRegimes, useMetrics, useRankHistory, useRegimes, useTransitions } from '../queries';
import { startingFunds, useRecentFunds } from '../context';
import { growthByMonth, monthEnd } from '../series';
import { backtestVerdict } from '../verdicts';
import { heat, seriesColor, token } from '../theme/themes';

const MODES = [
  { id: 'rolling', label: 'Rolling returns' },
  { id: 'drawdown', label: 'Drawdowns' },
  { id: 'ranks', label: 'Peer rankings' },
  { id: 'frontier', label: 'Risk–return' },
  { id: 'transitions', label: 'Rank persistence' },
  { id: 'regimes', label: 'Market regimes' },
  { id: 'backtest', label: 'Selection backtest' },
] as const;
type Mode = (typeof MODES)[number]['id'];
const MAX_FUNDS = 3;
const DEFAULT_GROUP: PeerGroup = { category: 'Equity Scheme - Flexi Cap Fund', plan: 'direct', option: 'growth' };
const REGIME_TONE: Record<string, 'loss' | 'warning' | 'brand'> = { crash: 'loss', correction: 'warning', recovery: 'brand' };

function useStudioParams() {
  const [params, setParams] = useSearchParams();
  const recent = useRecentFunds();
  const mode = (MODES.some((m) => m.id === params.get('mode')) ? params.get('mode') : 'rolling') as Mode;
  const chosen = (params.get('code') ?? '').split(',').filter((c) => /^\d{1,9}$/.test(c)).slice(0, MAX_FUNDS);
  // No fund in the link: start from the funds opened last, or the examples (audit U-01).
  const start = startingFunds(recent, 2);
  const codes = params.has('code') ? chosen : start.codes;
  const example = !params.has('code') && start.example;
  const set = (patch: Record<string, string | null>, push = false) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v === null ? next.delete(k) : next.set(k, v));
    setParams(next, { replace: !push });
  };
  const group: PeerGroup | null = params.get('category') ? { category: params.get('category')!, plan: params.get('plan') ?? 'direct', option: params.get('option') ?? 'growth' } : null;
  return { mode, codes, group, set, params, example };
}

function FundPicker({ codes, onChange }: { codes: string[]; onChange: (codes: string[]) => void }) {
  const names = useQueries({ queries: codes.map((code) => ({ queryKey: ['mf', 'fund', code, 'metrics'], queryFn: ({ signal }: { signal: AbortSignal }) => mfApi.metrics(code, signal), staleTime: 300_000 })) });
  return (
    <div className="flex flex-wrap items-center gap-2">
      {codes.map((code, i) => (
        <Chip key={code} onRemove={() => onChange(codes.filter((c) => c !== code))}>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: seriesColor(i) }} aria-hidden="true" />
            {names[i].data ? schemeName(names[i].data.name) : code}
          </span>
        </Chip>
      ))}
      {codes.length < MAX_FUNDS && (
        <FundSearch className="w-full sm:w-80" label="Add a fund to the studio" placeholder={codes.length ? 'Add a fund to compare' : 'Choose a fund'} onPick={(f) => onChange([...codes, f.amfi_code].filter((c, i, a) => a.indexOf(c) === i))} />
      )}
    </div>
  );
}

function GroupPicker({ group, onChange }: { group: PeerGroup; onChange: (g: PeerGroup) => void }) {
  const fields = useFields();
  const categories = fields.byId.get('category')?.values ?? [group.category];
  return (
    <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <Field label="Category">
        <select className={inputClass} value={group.category} onChange={(e) => onChange({ ...group, category: e.target.value })}>
          {categories.filter((c) => c !== 'Unclassified').map((c) => (
            <option key={c} value={c}>
              {c.split(' - ')[0].replace(' Scheme', '')} · {categoryShort(c)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Plan">
        <select className={inputClass} value={group.plan} onChange={(e) => onChange({ ...group, plan: e.target.value })}>
          <option value="direct">Direct</option>
          <option value="regular">Regular</option>
        </select>
      </Field>
      <Field label="Option">
        <select className={inputClass} value={group.option} onChange={(e) => onChange({ ...group, option: e.target.value })}>
          <option value="growth">Growth</option>
          <option value="idcw">IDCW</option>
        </select>
      </Field>
    </div>
  );
}

function NeedFund({ text }: { text: string }) {
  return (
    <EmptyState title="Choose a fund to begin" art={<I.studio className="mb-3 h-8 w-8 text-mf-brand" />}>
      {text}
    </EmptyState>
  );
}

// ── Modes ───────────────────────────────────────────────────────────────

function Rolling({ codes }: { codes: string[] }) {
  const [window, setWindow] = useState<'1y' | '3y' | '5y'>('3y');
  const results = useQueries({ queries: codes.map((code) => ({ queryKey: ['mf', 'fund', code, `rolling-${window}`], queryFn: ({ signal }: { signal: AbortSignal }) => mfApi.rolling(code, window, signal), staleTime: 300_000 })) });
  const metrics = useQueries({ queries: codes.map((code) => ({ queryKey: ['mf', 'fund', code, 'metrics'], queryFn: ({ signal }: { signal: AbortSignal }) => mfApi.metrics(code, signal), staleTime: 300_000 })) });
  if (!codes.length) return <NeedFund text="Rolling returns show how much the entry date mattered. Add up to three funds to compare their ranges." />;
  const series = codes.map((code, i) => ({ id: code, label: metrics[i].data ? schemeName(metrics[i].data.name) : code, points: results[i].data?.points ?? [], color: seriesColor(i) }));
  const key = window;
  return (
    <div className="space-y-6">
      <ChartFrame
        title={`Rolling ${key.toUpperCase()} return`}
        subtitle="Annualised return of the holding period that ended on each day"
        controls={<Segmented label="Holding period" value={window} onChange={setWindow} options={[{ value: '1y', label: '1Y' }, { value: '3y', label: '3Y' }, { value: '5y', label: '5Y' }]} />}
        legend={series.map((s) => <LegendDot key={s.id} color={s.color} label={s.label} />)}
        footnote="Overlapping periods share most of their days; read the range, not a count of wins."
      >
        {results.some((r) => r.isLoading) ? <Skeleton className="h-[320px]" /> : <TimeChart label="Rolling returns over time" zero height={320} zoom series={series} format={(v) => pct(v, 1)} tick={pctTick} />}
      </ChartFrame>
      <Card title="Selected statistics" subtitle={`${key.toUpperCase()} rolling, from each fund's metrics`}>
        <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-xs text-mf-muted">
              <tr className="border-b border-mf-line">
                <th scope="col" className="py-2 text-left font-medium">Fund</th>
                {['Median', '10th pct', '90th pct', 'Positive', 'Best', 'Worst'].map((h) => (
                  <th key={h} scope="col" className="py-2 text-right font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {codes.map((code, i) => {
                const v = metrics[i].data?.values ?? {};
                const g = (k: string) => v[`rolling_${key}_${k}`];
                return (
                  <tr key={code} className="border-b border-mf-line last:border-0">
                    <th scope="row" className="py-2.5 text-left font-normal">
                      <Link to={`/mf/funds/${code}`} className="hover:text-mf-brand-strong">{series[i].label}</Link>
                    </th>
                    {[pct(g('median')), pct(g('p10')), pct(g('p90')), pct(g('positive_share'), 0), pct(g('max')), pct(g('min'))].map((t, j) => (
                      <td key={j} className={cx('py-2.5 text-right tabular', j === 5 && 'text-mf-loss')}>{t}</td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Drawdown({ codes }: { codes: string[] }) {
  const results = useQueries({ queries: codes.map((code) => ({ queryKey: ['mf', 'fund', code, 'underwater'], queryFn: ({ signal }: { signal: AbortSignal }) => mfApi.underwater(code, signal), staleTime: 300_000 })) });
  const metrics = useQueries({ queries: codes.map((code) => ({ queryKey: ['mf', 'fund', code, 'metrics'], queryFn: ({ signal }: { signal: AbortSignal }) => mfApi.metrics(code, signal), staleTime: 300_000 })) });
  if (!codes.length) return <NeedFund text="See how far each fund fell below its peak, and for how long." />;
  const series = codes.map((code, i) => ({ id: code, label: metrics[i].data ? schemeName(metrics[i].data.name) : code, points: results[i].data?.series ?? [], color: i === 0 ? token('loss') : seriesColor(i) }));
  return (
    <ChartFrame
      title="Below the previous peak"
      subtitle="Underwater: 0% is a new high; the depth is the fall since the last high"
      legend={series.map((s, i) => (
        <LegendDot key={s.id} color={s.color} label={<>{s.label} · now <b className="tabular">{pct(results[i].data?.dd_now)}</b></>} />
      ))}
    >
      {results.some((r) => r.isLoading) ? <Skeleton className="h-[320px]" /> : <TimeChart label="Underwater chart" height={320} yDomain={['dataMin', 0]} zoom series={series} format={(v) => pct(v, 1)} tick={pctTick} />}
    </ChartFrame>
  );
}

function Ranks({ code }: { code?: string }) {
  const ranks = useRankHistory(code);
  if (!code) return <NeedFund text="Rank history shows whether a fund stayed near the top of its category month after month." />;
  const h = ranks.data?.history ?? [];
  const pts = (k: 'ret_1y' | 'cagr_3y') => h.filter((r) => r[k]).map((r) => [`${r.month}-28`, r[k]!.pct] as [string, number]);
  const q = (k: 'ret_1y' | 'cagr_3y') => [1, 2, 3, 4].map((n) => h.filter((r) => r[k]?.quartile === n).length);
  return (
    <div className="space-y-6">
      <ChartFrame
        title="Category percentile, month by month"
        subtitle={ranks.data ? `${categoryShort(ranks.data.group.category)} · ${ranks.data.group.funds_with_nav} funds with NAVs · 100 is best` : undefined}
        legend={<><LegendDot color={seriesColor(0)} label="Return 1Y" /><LegendDot color={seriesColor(1)} dashed label="CAGR 3Y" /></>}
        footnote="Peer counts change month to month. Past months use today's AMFI category labels."
        table={{ columns: ['Month', 'Return 1Y', 'CAGR 3Y'], rows: h.map((r) => [month(r.month), r.ret_1y ? `${r.ret_1y.rank}/${r.ret_1y.count} (Q${r.ret_1y.quartile})` : '—', r.cagr_3y ? `${r.cagr_3y.rank}/${r.cagr_3y.count} (Q${r.cagr_3y.quartile})` : '—']) }}
      >
        {ranks.isError ? <ErrorState error={ranks.error} compact /> : ranks.isLoading ? <Skeleton className="h-[300px]" /> : (
          <TimeChart label="Category percentile over time" height={300} yDomain={[0, 100]} format={(v) => v.toFixed(0)} series={[{ id: 'ret_1y', label: 'Return 1Y', points: pts('ret_1y'), color: seriesColor(0) }, { id: 'cagr_3y', label: 'CAGR 3Y', points: pts('cagr_3y'), color: seriesColor(1), dashed: true }]} />
        )}
      </ChartFrame>
      <Card title="Months spent in each quartile" subtitle="Quartile 1 is the top quarter of the category">
        <div className="grid gap-4 sm:grid-cols-2">
          {(['ret_1y', 'cagr_3y'] as const).map((k) => {
            const counts = q(k);
            const total = counts.reduce((a, b) => a + b, 0) || 1;
            return (
              <div key={k}>
                <p className="mb-2 text-sm font-medium">{k === 'ret_1y' ? 'Return 1Y' : 'CAGR 3Y'}</p>
                <div className="flex h-8 overflow-hidden rounded-[8px]" role="img" aria-label={counts.map((c, i) => `Q${i + 1}: ${c} months`).join(', ')}>
                  {counts.map((c, i) => (
                    <div key={i} className="grid place-items-center text-[11px] font-medium text-mf-ink" style={{ width: `${(c / total) * 100}%`, background: heat('brand', 1 - i * 0.3) }}>
                      {c > 0 && `Q${i + 1}`}
                    </div>
                  ))}
                </div>
                <p className="mt-1 text-xs text-mf-muted">{counts.map((c, i) => `Q${i + 1} ${c}`).join(' · ')} months</p>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

function Frontier({ group, highlight }: { group: PeerGroup; highlight?: string }) {
  const frontier = useFrontier(group);
  const [selected, setSelected] = useState<string | null>(null);
  const points = useMemo(() => (frontier.data?.points ?? []).map((p) => ({ id: p.amfi_code, name: p.name, x: p.vol_3y, y: p.cagr_3y, frontier: p.frontier, highlight: p.amfi_code === highlight || p.amfi_code === selected })), [frontier.data, highlight, selected]);
  const sorted = [...points].sort((a, b) => b.y - a.y);
  const pick = sorted.find((p) => p.id === selected);
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
      <ChartFrame
        title="Return against volatility, 3 years"
        subtitle={`${categoryShort(group.category)} · ${enumLabel(group.plan)} ${enumLabel(group.option)} · ${points.length} active funds`}
        legend={<><LegendDot color={token('brandAlt')} label="On the historical frontier" /><LegendDot color={token('chart2')} label="Selected" /><LegendDot color={token('muted', 0.6)} label="Other peers" /></>}
        footnote="Frontier funds had no peer with both a higher CAGR and lower volatility over these 3 years. It is history, not an optimal choice for you."
        table={{ columns: ['Fund', 'CAGR 3Y', 'Volatility 3Y', 'Frontier'], rows: sorted.map((p) => [p.name, pct(p.y), pct(p.x), p.frontier ? 'Yes' : '']) }}
      >
        {frontier.isError ? <ErrorState error={frontier.error} compact /> : frontier.isLoading ? <Skeleton className="h-[360px]" /> : points.length === 0 ? (
          <p className="py-16 text-center text-sm text-mf-muted">No fund in this group has 3 years of NAVs.</p>
        ) : (
          <PeerScatter label="Risk-return scatter of peers" points={points} xLabel="Volatility 3Y" yLabel="CAGR 3Y" format={(v) => pct(v, 1)} tick={pctTick} height={380} onSelect={setSelected} />
        )}
      </ChartFrame>
      <Card title="Peers by 3Y CAGR" subtitle="Select a fund to mark it on the map">
        <p className="flex gap-2 px-1 pb-1 text-[11px] text-mf-muted" aria-hidden="true">
          <span className="flex-1">Fund</span>
          <span className="w-14 text-right">CAGR 3Y</span>
          <span className="w-14 text-right">Vol 3Y</span>
        </p>
        <ul className="mf-scroll max-h-[420px] divide-y divide-mf-line overflow-y-auto">
          {sorted.map((p) => (
            <li key={p.id}>
              <button type="button" onClick={() => setSelected(p.id === selected ? null : p.id)} aria-pressed={p.id === selected} className={cx('flex w-full items-center gap-2 px-1 py-2 text-left text-sm', p.id === selected && 'bg-mf-brand-soft')}>
                <span className="min-w-0 flex-1 truncate">{schemeName(p.name)}</span>
                {p.frontier && <Badge tone="brand">Frontier</Badge>}
                <span className="w-14 text-right tabular">{pct(p.y)}</span>
                <span className="w-14 text-right tabular text-mf-muted">{pct(p.x)}</span>
              </button>
            </li>
          ))}
        </ul>
        {pick && (
          <Link to={`/mf/funds/${pick.id}`} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-mf-brand hover:underline">
            Open {schemeName(pick.name)} <I.arrowUpRight className="h-4 w-4" />
          </Link>
        )}
      </Card>
    </div>
  );
}

function Transitions({ group }: { group: PeerGroup }) {
  const t = useTransitions(group);
  const d = t.data;
  return (
    <Card title="Did leaders stay leaders?" subtitle={`1Y-return quartile at a month-end (rows) and 12 month-ends later (columns) · ${categoryShort(group.category)} · ${enumLabel(group.plan)} ${enumLabel(group.option)}`}>
      {t.isError ? <ErrorState error={t.error} compact /> : !d ? <Skeleton className="h-64" /> : (
        <>
          <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
            <table className="w-full min-w-[520px] border-separate border-spacing-1 text-sm">
              <thead>
                <tr>
                  <th scope="col" className="text-left text-xs font-medium text-mf-muted">From \ 12 months later</th>
                  {[1, 2, 3, 4].map((q) => <th key={q} scope="col" className="text-xs font-medium text-mf-muted">Q{q}{q === 1 ? ' (top)' : q === 4 ? ' (bottom)' : ''}</th>)}
                </tr>
              </thead>
              <tbody>
                {d.counts.map((row, i) => {
                  const total = row.reduce((a, b) => a + b, 0);
                  return (
                    <tr key={i}>
                      <th scope="row" className="text-left text-xs font-medium text-mf-ink-soft">Q{i + 1} · {total}</th>
                      {row.map((c, j) => {
                        const share = d.shares[i][j];
                        return (
                          <td key={j} className="h-16 rounded-[8px] text-center tabular" style={{ background: heat(i === j ? 'brand' : 'info', (share ?? 0) * 2) }}>
                            <span className="block text-base font-semibold text-mf-ink">{share === null ? '—' : pct(share, 0)}</span>
                            <span className="text-[11px] text-mf-ink-soft">{c} of {total}</span>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-mf-muted">If ranks were random, each cell would be near 25%. These are counts from the past, not probabilities for the future. {d.funds_with_nav} funds with NAVs; current category labels apply to past months.</p>
        </>
      )}
    </Card>
  );
}

function Regimes({ code }: { code?: string }) {
  const regimes = useRegimes();
  const fundRegimes = useFundRegimes(code);
  const metrics = useMetrics(code);
  const d = regimes.data;
  const bands = (d?.windows ?? []).map((w) => ({ start: w.start, end: w.end, color: token(REGIME_TONE[w.kind] ?? 'info') }));
  const levels = useMemo(() => thin(d?.proxy.levels ?? [], 800), [d]);
  const byStart = new Map((fundRegimes.data?.windows ?? []).map((w) => [w.start, w]));
  return (
    <div className="space-y-6">
      <ChartFrame
        title="Falls and recoveries of the market proxy"
        subtitle={d?.proxy.label}
        legend={<><LegendDot color={token('loss')} label="Crash" /><LegendDot color={token('warning')} label="Correction" /><LegendDot color={token('brand')} label="Recovery" /></>}
        footnote="Windows come from the backend's proxy rules. They are not named after events, and the proxy is not an official index."
      >
        {regimes.isError ? <ErrorState error={regimes.error} compact /> : regimes.isLoading ? <Skeleton className="h-[300px]" /> : (
          <TimeChart label="Proxy level with regime windows" height={300} bands={bands} series={[{ id: 'proxy', label: 'Proxy level', points: levels, color: token('ink') }]} format={(v) => v.toFixed(0)} />
        )}
      </ChartFrame>
      {code && (fundRegimes.data?.windows ?? []).some((w) => w.fund_return !== null) && (
        <ChartFrame
          title={metrics.data ? `${schemeName(metrics.data.name)} against the proxy, window by window` : 'Fund against the proxy, window by window'}
          subtitle="↓ fall window · ↑ recovery window, labelled by start month"
          legend={<><LegendDot color={token('brand')} label="This fund" /><LegendDot color={token('muted', 0.6)} label="Market proxy" /></>}
        >
          <PairBars
            label="Fund return against the proxy in each regime window"
            rows={(fundRegimes.data?.windows ?? []).filter((w) => w.fund_return !== null).map((w) => ({ label: `${w.kind === 'recovery' ? '↑' : '↓'} ${w.start.slice(2, 7).replace('-', '/')}`, a: w.fund_return, b: w.proxy_return }))}
            names={['This fund', 'Market proxy']}
            format={(v) => pct(v, 1, true)}
            tick={pctTick}
          />
        </ChartFrame>
      )}
      <Card title={code && metrics.data ? `${schemeName(metrics.data.name)} in each window` : 'Each window'} subtitle={code ? 'Fund return against the proxy in the same window' : 'Add a fund above to see how it behaved in each window'}>
        <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="text-xs text-mf-muted">
              <tr className="border-b border-mf-line">
                <th scope="col" className="py-2 text-left font-medium">Window</th>
                <th scope="col" className="py-2 text-left font-medium">Kind</th>
                <th scope="col" className="py-2 text-right font-medium">Proxy</th>
                {code && <th scope="col" className="py-2 text-right font-medium">Fund</th>}
                {code && <th scope="col" className="py-2 text-right font-medium">Capture</th>}
              </tr>
            </thead>
            <tbody>
              {[...(d?.windows ?? [])].reverse().map((w) => {
                const f = byStart.get(w.start);
                return (
                  <tr key={w.start} className="border-b border-mf-line last:border-0">
                    <td className="py-2.5 text-mf-ink-soft">{date(w.start)} – {date(w.end)}{(w as { ongoing?: boolean }).ongoing && <Badge className="ml-2">Ongoing</Badge>}</td>
                    <td className="py-2.5"><Badge tone={REGIME_TONE[w.kind] === 'brand' ? 'brand' : REGIME_TONE[w.kind] ?? 'neutral'}>{w.kind}</Badge></td>
                    <td className="py-2.5 text-right tabular">{pct(w.proxy_return, 1, true)}</td>
                    {code && <td className="py-2.5 text-right tabular">{f?.fund_return == null ? '—' : pct(f.fund_return, 1, true)}</td>}
                    {code && <td className="py-2.5 text-right tabular">{f?.capture == null ? '—' : `${(f.capture * 100).toFixed(0)}%`}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function PeriodCard({ title, period, tone }: { title: string; period: BacktestPeriod | null; tone: 'brand' | 'info' }) {
  const ahead = period ? period.strategy_annualised >= period.median_annualised : false;
  return (
    <div className={cx('rounded-card border p-4', tone === 'brand' ? 'border-mf-line bg-mf-surface' : 'border-mf-info/30 bg-mf-info-soft/50')}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.06em] text-mf-muted">{title}</p>
        {period && <Badge tone={ahead ? 'brand' : 'loss'}>{ahead ? 'Ahead of median' : 'Behind median'}</Badge>}
      </div>
      {!period ? (
        <p className="mt-2 text-sm text-mf-muted">Not enough months.</p>
      ) : (
        <>
          <p className="mt-1 text-xs text-mf-muted">{month(period.first_signal)} – {month(period.last_signal)} · {period.months} months</p>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-xs text-mf-muted">Top-N a year</dt><dd className="text-lg font-semibold tabular">{pct(period.strategy_annualised)}</dd></div>
            <div><dt className="text-xs text-mf-muted">Group median a year</dt><dd className="text-lg font-semibold tabular">{pct(period.median_annualised)}</dd></div>
            <div><dt className="text-xs text-mf-muted">Months ahead of median</dt><dd className="tabular">{pct(period.beat_share, 0)}</dd></div>
            <div><dt className="text-xs text-mf-muted">Growth, top-N vs median</dt><dd className="tabular">{pct(period.strategy_growth, 0, true)} / {pct(period.median_growth, 0, true)}</dd></div>
          </dl>
        </>
      )}
    </div>
  );
}

function BacktestMode({ group }: { group: PeerGroup }) {
  const [signal, setSignal] = useState<'ret_1y' | 'cagr_3y'>('cagr_3y');
  const [top, setTop] = useState(5);
  // The default test runs on open, so the mode starts with a result (audit U-01).
  const [submitted, setSubmitted] = useState({ signal, top });
  const body = { ...group, ...submitted };
  const run = useQuery({ queryKey: ['mf', 'backtest', body], queryFn: ({ signal: abort }) => mfApi.backtest(body, abort), staleTime: 300_000 });
  const result: Backtest | undefined = run.data;
  const stale = submitted.signal !== signal || submitted.top !== top;
  const holdout = result ? String(result.strategy.holdout_from) : '';
  const months = useMemo(() => result?.months ?? [], [result]);
  const growth = useMemo(
    () => ({ s: growthByMonth(months, months.map((m) => m.strategy)), m: growthByMonth(months, months.map((m) => m.median)) }),
    [months],
  );
  return (
    <div className="space-y-6">
      <Card title="Each month, buy the top funds by a signal" subtitle="Equal weights, rebalanced monthly, NAV returns net of TER and before tax">
        <form onSubmit={(e) => { e.preventDefault(); setSubmitted({ signal, top }); }} className="flex flex-wrap items-end gap-3">
          <Field label="Signal">
            <select className={inputClass} value={signal} onChange={(e) => setSignal(e.target.value as 'ret_1y' | 'cagr_3y')}>
              <option value="cagr_3y">CAGR 3Y</option>
              <option value="ret_1y">Return 1Y</option>
            </select>
          </Field>
          <Field label="Funds held (1–50)">
            <input className={cx(inputClass, 'w-28')} type="number" min={1} max={50} value={top} onChange={(e) => setTop(Math.max(1, Math.min(50, Number(e.target.value) || 1)))} />
          </Field>
          <Button type="submit" variant="primary" disabled={run.isFetching}>{run.isFetching ? 'Running…' : 'Run backtest'}</Button>
          {stale && <Badge tone="warning">The result below used other inputs</Badge>}
        </form>
      </Card>
      {run.isError && <ErrorState error={run.error} onRetry={() => run.refetch()} />}
      {run.isLoading && <Skeleton className="h-64" />}
      {result && (
        <div className={cx('space-y-6', stale && 'opacity-60')}>
          <p className="rounded-card border border-mf-line bg-mf-surface p-4 text-[15px] leading-relaxed text-mf-ink shadow-card" data-testid="backtest-verdict">
            {backtestVerdict(result)}
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <PeriodCard title="Historical research — in-sample" period={result.summary.in_sample} tone="brand" />
            <PeriodCard title={`Out-of-sample evaluation — from ${month(holdout)}`} period={result.summary.holdout} tone="info" />
          </div>
          <ChartFrame
            title="Growth of 100: top-N against the group median"
            subtitle={`Signal ${result.strategy.signal === 'cagr_3y' ? 'CAGR 3Y' : 'Return 1Y'}, top ${result.strategy.top}, ${result.funds_with_nav} funds with NAVs · monthly returns compounded`}
            legend={<><LegendDot color={seriesColor(0)} label="Top-N" /><LegendDot color={seriesColor(1)} dashed label="Group median" /></>}
            footnote={`Each point is a holding month’s end: funds picked at the end of a signal month earn the next month’s return. The shaded band is the hold-out, returns earned from the end of ${month(holdout)}; the rules were not tuned on it.`}
            table={{ columns: ['Signal month', 'Return earned to', 'Top-N', 'Median', 'Picks'], rows: months.map((m) => [month(m.signal_month), date(monthEnd(m.signal_month, 1)), pct(m.strategy), pct(m.median), m.picks.join(' ')]) }}
          >
            <TimeChart
              label="Cumulative growth of the backtest"
              height={280}
              bands={[{ start: monthEnd(holdout), end: monthEnd(months[months.length - 1]?.signal_month ?? holdout, 1), color: token('info') }]}
              markers={[{ date: monthEnd(holdout), label: 'Hold-out', color: token('info') }]}
              series={[
                { id: 's', label: 'Top-N', points: growth.s, color: seriesColor(0) },
                { id: 'm', label: 'Median', points: growth.m, color: seriesColor(1), dashed: true },
              ]}
              format={(v) => v.toFixed(1)}
            />
          </ChartFrame>
          <Card title="Limits of this test">
            <ul className="list-disc space-y-1 pl-5 text-sm text-mf-ink-soft">
              {result.limits.map((l) => <li key={l}>{l}</li>)}
              <li>A good in-sample result is not a validated strategy; read the hold-out separately.</li>
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}

export default function Studio() {
  useTitle('Analytics studio');
  const { mode, codes, group, set, params, example } = useStudioParams();
  const first = useMetrics(codes[0]);
  const fields = useFields();
  const fundGroup: PeerGroup | null = first.data ? { category: String(first.data.values.category), plan: String(first.data.values.plan), option: String(first.data.values.option) } : null;
  const activeGroup = group ?? fundGroup ?? DEFAULT_GROUP;
  const usesGroup = mode === 'frontier' || mode === 'transitions' || mode === 'backtest';
  const usesFunds = mode === 'rolling' || mode === 'drawdown' || mode === 'ranks' || mode === 'regimes';
  const single = mode === 'ranks' || mode === 'regimes';
  const setGroup = (g: PeerGroup) => set({ category: g.category, plan: g.plan, option: g.option });
  const tabs = MODES.map((m) => {
    const p = new URLSearchParams(params);
    p.set('mode', m.id);
    return { id: m.id, label: m.label, to: `?${p}` };
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics studio" lead="Explore performance, risk and market behaviour in depth. Every chart has its data table and method notes." />
      <TabLinks label="Studio modes" active={mode} tabs={tabs} />
      {usesFunds && <FundPicker codes={single ? codes.slice(0, 1) : codes} onChange={(c) => set({ code: c.length ? c.slice(0, single ? 1 : MAX_FUNDS).join(',') : null })} />}
      {usesGroup && <GroupPicker group={activeGroup} onChange={setGroup} />}
      {example && usesFunds && (
        <p className="text-sm text-mf-muted">
          Showing example funds so the chart starts with a story. Add your own, or open a fund first: the studio starts from the funds you opened last.
        </p>
      )}
      <div key={mode} className="mf-rise">
        {mode === 'rolling' && <Rolling codes={codes} />}
        {mode === 'drawdown' && <Drawdown codes={codes} />}
        {mode === 'ranks' && <Ranks code={codes[0]} />}
        {mode === 'frontier' && <Frontier group={activeGroup} highlight={codes[0]} />}
        {mode === 'transitions' && <Transitions group={activeGroup} />}
        {mode === 'regimes' && <Regimes code={codes[0]} />}
        {mode === 'backtest' && <BacktestMode group={activeGroup} />}
      </div>
      <SnapshotNote asOf={fields.data?.as_of} revision={fields.data?.data_revision} method={fields.data?.method_version} />
    </div>
  );
}
