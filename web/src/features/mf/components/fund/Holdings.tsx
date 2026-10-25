/**
 * Holdings (doc 21 C16): the AMC's monthly portfolio disclosure as filed, its asset
 * mix, concentration, sectors and market cap, what changed since the month before,
 * and how the mix moved over time. A month whose weights do not add up says so.
 */
import { useMemo, useState } from 'react';
import type { FundHoldings, HoldingLine, WeightMove } from '../../api';
import { pctTick } from '../../axis';
import { date, num, pct } from '../../format';
import { useHoldings } from '../../queries';
import { seriesColor, token } from '../../theme/themes';
import { ChartFrame, LegendDot, TimeChart, type Series } from '../charts';
import { Badge, Button, Card, DependencyPanel, EmptyState, ErrorState, Field, Segmented, Skeleton, Stat, inputClass } from '../ui';
import type { FundTabProps } from './shared';

const ASSET_LABELS: Record<string, string> = { equity: 'Equity', debt: 'Debt', cash: 'Cash and TREPS', derivative: 'Derivatives', other: 'Funds, REITs, gold' };

/** Shares as one stacked bar with a labelled legend; colour never carries the meaning alone. */
export function ShareBar({ label, parts }: { label: string; parts: [string, number][] }) {
  const shown = parts.filter(([, v]) => v > 0.0005);
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-mf-sunken" role="img" aria-label={`${label}: ${shown.map(([k, v]) => `${k} ${pct(v)}`).join(', ')}`}>
        {shown.map(([k, v], i) => (
          <span key={k} style={{ width: `${Math.max(v, 0) * 100}%`, background: seriesColor(i) }} />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-mf-ink-soft">
        {shown.map(([k, v], i) => (
          <li key={k} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: seriesColor(i) }} aria-hidden="true" />
            {k} <b className="tabular">{pct(v)}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Weights({ rows, total }: { rows: [string, number][]; total?: number }) {
  const max = Math.max(...rows.map(([, v]) => v), 0.0001);
  return (
    <ul className="space-y-2 text-sm">
      {rows.map(([k, v]) => (
        <li key={k}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate text-mf-ink-soft" title={k}>{k}</span>
            <span className="shrink-0 tabular">{pct(v)}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-mf-sunken">
            <div className="h-1.5 rounded-full bg-mf-brand" style={{ width: `${(v / max) * 100}%` }} />
          </div>
        </li>
      ))}
      {total !== undefined && rows.length === 0 && <li className="text-mf-muted">None filed.</li>}
    </ul>
  );
}

function Lines({ lines }: { lines: HoldingLine[] }) {
  const [asset, setAsset] = useState<string>('all');
  const [all, setAll] = useState(false);
  const [q, setQ] = useState('');
  const kinds = useMemo(() => ['all', ...new Set(lines.map((l) => l.asset))], [lines]);
  const shown = lines.filter((l) => (asset === 'all' || l.asset === asset) && (!q || l.name.toLowerCase().includes(q.toLowerCase())));
  const visible = all ? shown : shown.slice(0, 25);
  return (
    <Card title="Every line as filed" subtitle={`${lines.length} lines, largest first`} action={<Segmented label="Asset" value={asset} onChange={setAsset} options={kinds.map((k) => ({ value: k, label: k === 'all' ? 'All' : ASSET_LABELS[k] ?? k }))} />}>
      <Field label="Find a holding" className="mb-3 max-w-xs">
        <input className={inputClass} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name" />
      </Field>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <caption className="sr-only">Portfolio lines with weight, sector or rating, and market cap</caption>
          <thead>
            <tr className="border-b border-mf-line text-left text-xs text-mf-muted">
              <th scope="col" className="py-2 pr-3 font-medium">Holding</th>
              <th scope="col" className="py-2 pr-3 font-medium">Industry or rating</th>
              <th scope="col" className="py-2 pr-3 font-medium">Market cap</th>
              <th scope="col" className="py-2 text-right font-medium">Weight</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((l, i) => (
              <tr key={`${l.isin ?? l.name}-${i}`} className="border-b border-mf-line/60 last:border-0">
                <td className="py-2 pr-3">
                  <span className="text-mf-ink">{l.name}</span>
                  <span className="block text-[11px] text-mf-muted">{l.isin ?? l.section}</span>
                </td>
                <td className="py-2 pr-3 text-mf-ink-soft">{l.industry ?? '—'}</td>
                <td className="py-2 pr-3 text-mf-ink-soft">{l.cap ?? ASSET_LABELS[l.asset]}</td>
                <td className="py-2 text-right tabular">{pct(l.weight, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {shown.length > 25 && (
        <div className="mt-3">
          <Button size="sm" onClick={() => setAll(!all)}>{all ? 'Show the largest 25' : `Show all ${shown.length}`}</Button>
        </div>
      )}
    </Card>
  );
}

function Moves({ title, rows }: { title: string; rows: WeightMove[] }) {
  return (
    <div className="min-w-0">
      <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-mf-brand">{title}</h3>
      {rows.length ? (
        <ul className="mt-2 space-y-1.5 text-sm">
          {rows.slice(0, 8).map((m) => (
            <li key={(m.isin ?? m.name) + title} className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-mf-ink-soft" title={m.name}>{m.name}</span>
              <span className="shrink-0 text-xs tabular text-mf-muted">
                {pct(m.before, 2)} → <b className="text-mf-ink">{pct(m.after, 2)}</b>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-mf-muted">None.</p>
      )}
    </div>
  );
}

function Trend({ data }: { data: FundHoldings }) {
  const trend = data.trend ?? [];
  const pick = (key: string): [string, number][] => trend.filter((r) => typeof r[key] === 'number').map((r) => [String(r.as_of), r[key] as number]);
  const series: Series[] = [
    { id: 'equity', label: 'Equity', points: pick('equity'), color: seriesColor(0) },
    { id: 'debt', label: 'Debt', points: pick('debt'), color: seriesColor(1) },
    { id: 'cash', label: 'Cash and TREPS', points: pick('cash'), color: seriesColor(2) },
    { id: 'top10', label: 'Top 10 holdings', points: pick('top10_weight'), color: token('chart2'), dashed: true },
  ].filter((s) => s.points.length > 1 && s.points.some(([, v]) => v > 0.005));
  if (trend.length < 3) return null;
  return (
    <ChartFrame
      title="Portfolio mix over time"
      subtitle={`${trend.length} monthly disclosures, ${date(trend[0].as_of)} to ${date(trend[trend.length - 1].as_of)}`}
      legend={series.map((s) => <LegendDot key={s.id} color={s.color!} dashed={s.dashed} label={s.label} />)}
      table={{ columns: ['Month', 'Equity', 'Debt', 'Cash', 'Top 10', 'Large', 'Mid', 'Small'], rows: trend.map((r) => [String(r.as_of), ...['equity', 'debt', 'cash', 'top10_weight', 'Large Cap', 'Mid Cap', 'Small Cap'].map((k) => (typeof r[k] === 'number' ? pct(r[k], 1) : '—'))]) }}
    >
      <TimeChart label="Portfolio mix over time" height={220} series={series} format={(v) => pct(v, 1)} tick={pctTick} />
    </ChartFrame>
  );
}

export function Holdings({ code }: Pick<FundTabProps, 'code'>) {
  const [asOf, setAsOf] = useState<string | undefined>();
  const holdings = useHoldings(code, asOf);
  const h = holdings.data;
  if (holdings.isError) return <ErrorState error={holdings.error} onRetry={() => holdings.refetch()} />;
  if (!h) return <Skeleton className="h-96" />;
  if (!h.scheme || !h.summary || !h.lines)
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <EmptyState title="No portfolio disclosure stored for this scheme yet">
          Wickstreet stores the monthly portfolio only where it can read the fund house&rsquo;s file. For any other fund house, download the month&rsquo;s file from it and import it with <code>wickstreet mf import-portfolios</code>.
        </EmptyState>
        <DependencyPanel title="Sector style and valuation" needs="E7, company fundamentals with a licence">
          Weighted P/E, P/B and ROE need a stock data supplier; none with a clear grant was found.
        </DependencyPanel>
      </div>
    );
  const s = h.summary;
  const equity = s.assets.equity > 0;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-mf-ink-soft">
            Portfolio of {date(h.portfolio_as_of)} {s.reconciled ? <Badge tone="brand">Weights add to {pct(s.weight_sum, 1)}</Badge> : <Badge tone="warning">Weights add to {pct(s.weight_sum, 1)}: check the filing</Badge>}
          </p>
          <p className="mt-0.5 text-xs text-mf-muted">As the AMC filed it; {h.dates.length} months stored.</p>
        </div>
        <Field label="Disclosure month" className="w-48">
          <select className={inputClass} value={h.portfolio_as_of} onChange={(e) => setAsOf(e.target.value)}>
            {[...h.dates].reverse().map((d) => (
              <option key={d} value={d}>{date(d)}</option>
            ))}
          </select>
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Holdings" value={s.count.toLocaleString('en-IN')} sub="lines with a weight" />
        <Stat label="Top 10 holdings" value={pct(s.top10_weight)} sub="of net assets" />
        <Stat label="Effective number of stocks" value={s.effective_holdings ? num(s.effective_holdings, 1) : '—'} sub="equal stocks the equity spread equals" help="1 ÷ the sum of squared equity weights. Fewer means more concentrated." />
        <Stat label="Equity" value={pct(s.assets.equity)} sub={`debt ${pct(s.assets.debt)} · cash ${pct(s.assets.cash)}`} />
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card title="Asset mix" subtitle="Share of net assets">
          <ShareBar label="Asset mix" parts={Object.entries(s.assets).map(([k, v]) => [ASSET_LABELS[k] ?? k, v])} />
          {equity && (
            <div className="mt-5">
              <p className="mb-2 text-xs text-mf-muted">Market cap of the equity held, by AMFI&rsquo;s list</p>
              <ShareBar label="Market cap" parts={Object.entries(s.market_cap)} />
            </div>
          )}
        </Card>
        <Card title={equity ? 'Sectors' : 'Ratings'} subtitle={equity ? 'Industry as filed, share of the equity held' : 'Rating as filed, share of net assets'}>
          <Weights rows={Object.entries(equity ? s.sectors : s.ratings).slice(0, 12)} total={0} />
        </Card>
      </div>
      {h.changes && (
        <Card title="What changed" subtitle={`From ${date(h.previous_as_of)} to ${date(h.portfolio_as_of)}`}>
          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
            <Moves title="New" rows={h.changes.added} />
            <Moves title="Sold out" rows={h.changes.removed} />
            <Moves title="Added to" rows={h.changes.increased} />
            <Moves title="Cut" rows={h.changes.decreased} />
          </div>
        </Card>
      )}
      <Trend data={h} />
      <Lines lines={h.lines} />
      <p className="text-xs text-mf-muted">{h.method}</p>
    </div>
  );
}
