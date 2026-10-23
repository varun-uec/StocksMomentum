/**
 * Fund risk (journey J2): how far below a peak, for how long, and whether it
 * recovered. An open drawdown says "not recovered"; it never implies a recovery.
 * Regime rows compare the fund with the NAV-built proxy, never an official index.
 */
import { useEffect, useMemo, useRef } from 'react';
import { useLocation } from 'react-router';
import { pctTick } from '../../axis';
import type { Drawdown } from '../../api';
import { date, formatField, pct } from '../../format';
import { useDrawdowns, useFundRegimes, useRiskFree, useUnderwater } from '../../queries';
import { token } from '../../theme/themes';
import { ChartFrame, LegendDot, PairBars, TimeChart, thin } from '../charts';
import { Badge, Card, Delta, ErrorState, Skeleton } from '../ui';
import { MetricTile, type FundTabProps } from './shared';

const RISK_TILES: { id: string; label?: string; median?: string; rank?: string; plain?: string }[] = [
  { id: 'vol_3y', label: 'Volatility 3Y', median: 'vol_3y_cat_median' },
  { id: 'downside_dev_3y', label: 'Downside deviation 3Y' },
  { id: 'sharpe_3y', rank: 'sharpe_3y_cat_rank' },
  { id: 'sortino_3y', rank: 'sortino_3y_cat_rank' },
  { id: 'var95_3y', label: '1-day loss passed on 5% of days (VaR)' },
  { id: 'cvar95_3y', label: 'Average loss on the worst 5% of days' },
  // Rolling windows, not calendar periods (audit F-07). The 1-year figure is the
  // same rolling 1Y minimum the Performance tab charts.
  { id: 'worst_1m', label: 'Worst 1-month window', plain: 'any 1-month span, not a calendar month' },
  { id: 'rolling_1y_min', label: 'Worst 1-year window', plain: 'same figure as the rolling 1Y charts' },
];

function UnderwaterChart({ code }: { code: string }) {
  const uw = useUnderwater(code);
  const dd = useDrawdowns(code);
  const d = uw.data;
  const points = d?.series ?? [];
  // The service's deepest episode marks its own trough date, so a reader sees the true low at every zoom.
  const deepest = dd.data?.drawdowns.reduce<Drawdown | undefined>((m, e) => (!m || e.depth < m.depth ? e : m), undefined);
  return (
    <ChartFrame
      title="How far below its peak"
      subtitle="Underwater chart: the fall from the highest NAV so far, every trading day. Drag the handles to zoom in."
      legend={
        d && (
          <>
            {deepest && (
              <span>
                Deepest <b className="tabular text-mf-loss">{pct(deepest.depth)}</b> on {date(deepest.trough)}
              </span>
            )}
            <span>
              Now <b className="tabular text-mf-loss">{pct(d.dd_now)}</b> for {d.dd_now_days ?? '—'} days
            </span>
            <span>
              Longest time below a peak <b className="tabular">{d.underwater_max_days ?? '—'} days</b>
            </span>
          </>
        )
      }
      footnote="The table keeps every fall’s lowest day; it shows about 150 of the daily rows."
      table={{ columns: ['Date', 'Below peak'], rows: thin(points, 150).map(([day, v]) => [date(day), pct(v)]) }}
    >
      {uw.isError ? (
        <ErrorState error={uw.error} compact />
      ) : uw.isLoading ? (
        <Skeleton className="h-[240px]" />
      ) : (
        <TimeChart
          label="Drawdown from peak over time"
          area
          zoom
          height={240}
          yDomain={['dataMin', 0]}
          series={[{ id: 'uw', label: 'Below peak', points, color: token('loss') }]}
          dots={deepest ? [{ date: deepest.trough, value: deepest.depth, label: `Deepest ${pct(deepest.depth, 1)} · ${date(deepest.trough)}`, color: token('loss') }] : undefined}
          format={(v) => pct(v, 2)}
          tick={pctTick}
        />
      )}
    </ChartFrame>
  );
}

function Episodes({ code }: { code: string }) {
  const dd = useDrawdowns(code);
  return (
    <Card title="Deepest falls on record" subtitle="Whole stored history; peak to trough, then the days to regain the peak">
      {dd.isError ? (
        <ErrorState error={dd.error} compact />
      ) : !dd.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
          <table className="w-full min-w-[520px] text-sm">
            <thead className="text-xs text-mf-muted">
              <tr className="border-b border-mf-line">
                <th scope="col" className="py-2 text-left font-medium">Fall</th>
                <th scope="col" className="py-2 text-left font-medium">Peak</th>
                <th scope="col" className="py-2 text-left font-medium">Trough</th>
                <th scope="col" className="py-2 text-right font-medium">Fall days</th>
                <th scope="col" className="py-2 text-right font-medium">Recovered</th>
              </tr>
            </thead>
            <tbody>
              {dd.data.drawdowns.map((e) => (
                <tr key={e.peak} className="border-b border-mf-line last:border-0">
                  <td className="py-2.5 font-medium tabular text-mf-loss">{pct(e.depth)}</td>
                  <td className="py-2.5 text-mf-ink-soft">{date(e.peak)}</td>
                  <td className="py-2.5 text-mf-ink-soft">{date(e.trough)}</td>
                  <td className="py-2.5 text-right tabular">{e.fall_days}</td>
                  <td className="py-2.5 text-right">
                    {e.recovery ? (
                      <span className="tabular">
                        {date(e.recovery)} <span className="text-xs text-mf-muted">({e.recovery_days} d)</span>
                      </span>
                    ) : (
                      <Badge tone="warning">Not recovered</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Recovery({ code }: { code: string }) {
  const uw = useUnderwater(code);
  return (
    <Card title="Time to recover" subtitle="For every fall at least this deep: how many recovered, and how long it took">
      {!uw.data ? (
        <Skeleton className="h-32" />
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-mf-muted">
            <tr className="border-b border-mf-line">
              <th scope="col" className="py-2 text-left font-medium">Fall of</th>
              <th scope="col" className="py-2 text-right font-medium">Recovered</th>
              <th scope="col" className="py-2 text-right font-medium">Median days</th>
              <th scope="col" className="py-2 text-right font-medium">Slowest</th>
            </tr>
          </thead>
          <tbody>
            {uw.data.recovery.map((r) => (
              <tr key={r.depth} className="border-b border-mf-line last:border-0">
                <td className="py-2.5 tabular">{pct(r.depth, 0)} or more</td>
                <td className="py-2.5 text-right tabular">
                  {r.recovered} of {r.recovered + r.not_recovered}
                </td>
                <td className="py-2.5 text-right tabular">{r.median_days ?? '—'}</td>
                <td className="py-2.5 text-right tabular">{r.max_days ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function Regimes({ code }: { code: string }) {
  const regimes = useFundRegimes(code);
  const { hash } = useLocation();
  const ref = useRef<HTMLDivElement>(null);
  const ready = !!regimes.data;
  useEffect(() => {
    if (hash === '#regimes' && ready) ref.current?.scrollIntoView({ block: 'start' });
  }, [hash, ready]);
  const bars = (regimes.data?.windows ?? []).filter((w) => w.fund_return !== null).map((w) => ({ label: `${w.kind === 'recovery' ? '↑' : '↓'} ${w.start.slice(2, 7).replace('-', '/')}`, a: w.fund_return, b: w.proxy_return }));
  return (
    <div ref={ref} id="regimes" className="scroll-mt-24">
    <Card title="Through market falls and recoveries" subtitle={regimes.data?.proxy_label ?? 'NAV-built large-cap proxy, not an official index'}>
      {regimes.isError ? (
        <ErrorState error={regimes.error} compact />
      ) : !regimes.data ? (
        <Skeleton className="h-40" />
      ) : (
        <>
        {bars.length > 0 && (
          <div className="mb-4">
            <div className="mb-2 flex flex-wrap gap-4 text-xs text-mf-ink-soft">
              <LegendDot color={token('brand')} label="This fund" />
              <LegendDot color={token('muted', 0.6)} label="Market proxy" />
              <span className="text-mf-muted">↓ fall window · ↑ recovery window, by start month</span>
            </div>
            <PairBars label="Fund return against the proxy in each market window" rows={bars} names={['This fund', 'Market proxy']} format={(v) => pct(v, 1, true)} tick={pctTick} height={220} />
          </div>
        )}
        <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Table; scroll sideways for more columns">
          <table className="w-full min-w-[600px] text-sm">
            <thead className="text-xs text-mf-muted">
              <tr className="border-b border-mf-line">
                <th scope="col" className="py-2 text-left font-medium">Window</th>
                <th scope="col" className="py-2 text-left font-medium">Kind</th>
                <th scope="col" className="py-2 text-right font-medium">Proxy</th>
                <th scope="col" className="py-2 text-right font-medium">Fund</th>
                <th scope="col" className="py-2 text-right font-medium">Capture</th>
              </tr>
            </thead>
            <tbody>
              {[...regimes.data.windows].reverse().map((w) => (
                <tr key={w.start} className="border-b border-mf-line last:border-0">
                  <td className="py-2.5 text-mf-ink-soft">
                    {date(w.start)} – {date(w.end)}
                  </td>
                  <td className="py-2.5 capitalize">{w.kind}</td>
                  <td className="py-2.5 text-right">
                    <Delta value={w.proxy_return} />
                  </td>
                  <td className="py-2.5 text-right">{w.fund_return === null ? <span className="text-mf-muted">No NAV</span> : <Delta value={w.fund_return} />}</td>
                  <td className="py-2.5 text-right tabular">{w.capture === null ? '—' : `${(w.capture * 100).toFixed(0)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-mf-muted">Capture is the fund’s return as a share of the proxy’s in that window. Below 100% in a fall means the fund fell less.</p>
        </div>
        </>
      )}
    </Card>
    </div>
  );
}

export function Risk({ code, metrics, fields }: FundTabProps) {
  const riskFree = useRiskFree();
  return (
    <div className="space-y-6">
      {/* The fall itself first, then the measures that summarise it (audit 5.3). */}
      <UnderwaterChart code={code} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {RISK_TILES.map((t) => (
          <MetricTile key={t.id} metrics={metrics} fields={fields} {...t} />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Episodes code={code} />
        <Recovery code={code} />
      </div>
      <Regimes code={code} />
      <p className="text-xs text-mf-muted">
        Sharpe uses the RBI 91-day T-bill as the risk-free rate (3Y average {formatField(fields.get('rf_3y'), metrics.values.rf_3y)}). {riskFree.data?.acknowledgement}
      </p>
    </div>
  );
}
