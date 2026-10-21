import { useState } from 'react';
import { Link } from 'react-router';
import { runWalkForwardBacktest } from '@/lib/api-client';
import { Card, MetricCard, LoadingSpinner, ErrorMessage, PageHeader, EmptyState } from '@/components/shared/Card';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useChartColors } from '@/lib/useChartColors';
import type { BacktestResponse } from '@/lib/types';
import { focusRing, chartPalette } from '@/lib/theme';

const inputClass = 'px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm';

function formatPercent(value: string): string {
  return `${(parseFloat(value) * 100).toFixed(2)}%`;
}

/** Fills shown in the table; the full log stays in the API response. */
const TRADE_ROWS_SHOWN = 500;

/**
 * A symbol that opens its chart as it stood on `asOf` (bar replay), or the security id
 * when no symbol is stored. The date is the fill or last-bar date of the row.
 */
function SecurityCell({ id, symbols, asOf }: { id: number; symbols: Record<string, string>; asOf: string }) {
  const symbol = symbols[String(id)];
  if (!symbol) return <span className="tabular-nums">{id}</span>;
  return (
    <Link
      to={`/chart/${encodeURIComponent(symbol)}?replay=${asOf}`}
      title={`Open ${symbol} as it stood on ${asOf}`}
      className={`text-indigo-700 dark:text-indigo-300 hover:underline ${focusRing}`}
    >
      {symbol}
    </Link>
  );
}

export default function BacktestPage() {
  const chartColors = useChartColors();
  const [start, setStart] = useState('2019-01-01');
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const [initialCapital, setInitialCapital] = useState('1000000');
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setIsRunning(true);
    setError(null);
    setResult(null);
    try {
      setResult(await runWalkForwardBacktest({ start, end, initial_capital: initialCapital }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backtest failed');
    } finally {
      setIsRunning(false);
    }
  };

  const equityCurve = (result?.rebalances ?? []).map((r) => ({
    date: r.fill_date,
    nav: parseFloat(r.nav_pre_cost),
  }));

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Walk-Forward Backtest"
        subtitle="3/6/12M blended momentum, monthly rebalance, N=30 with a 45-rank buffer"
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <Card title="Backtest Configuration">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label htmlFor="bt-start" className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Start Date</label>
              <input id="bt-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className={`${inputClass} ${focusRing}`} />
            </div>
            <div>
              <label htmlFor="bt-end" className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">End Date</label>
              <input id="bt-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={`${inputClass} ${focusRing}`} />
            </div>
            <div>
              <label htmlFor="bt-capital" className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Initial Capital (INR)</label>
              <input id="bt-capital" type="number" min="1" step="1" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)} className={`${inputClass} w-40 ${focusRing}`} />
            </div>
            <button
              type="button"
              onClick={handleRun}
              disabled={isRunning}
              className={`px-6 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${focusRing}`}
            >
              {isRunning ? 'Running Backtest…' : 'Run Backtest'}
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-3">A multi-year range reads several years of prices from the database and can take a few seconds.</p>
        </Card>

        {isRunning && <LoadingSpinner />}
        {error && <ErrorMessage message={error} />}

        {result && (
          <>
            <div
              role="note"
              className="rounded-lg border border-amber-300 dark:border-amber-700/60 bg-amber-50 dark:bg-amber-900/20 px-4 py-3"
            >
              <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wider mb-1">
                Known data caveat — read before using these numbers
              </p>
              <p className="text-sm text-amber-800 dark:text-amber-200">{result.simulation_notice}</p>
              <p className="text-sm text-amber-800 dark:text-amber-200 mt-2">{result.survivorship_warning}</p>
            </div>

            <Card title="Result" subtitle={`${result.start} to ${result.end}`}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard label="Final NAV" value={parseFloat(result.final_nav).toLocaleString('en-IN', { maximumFractionDigits: 0 })} />
                <MetricCard
                  label="Total Return"
                  value={formatPercent(result.total_return)}
                  color={parseFloat(result.total_return) >= 0 ? 'text-emerald-400' : 'text-rose-400'}
                />
                {/* The lower bound sits next to the return (execution method v2). */}
                <MetricCard
                  label="Lower bound (non-trading holdings at zero)"
                  value={result.lower_bound_return === null ? 'Not available' : formatPercent(result.lower_bound_return)}
                />
                <MetricCard label="CAGR" value={result.cagr === null ? 'Not available' : formatPercent(result.cagr)} />
                <MetricCard label="Max drawdown" value={formatPercent(result.max_drawdown)} />
                {/* The benchmark number never appears without its label. */}
                <MetricCard
                  label={result.benchmark_return === null ? 'Benchmark' : `Benchmark — ${result.benchmark_label ?? 'UNLABELED BENCHMARK'}`}
                  value={result.benchmark_return === null ? 'Not available' : formatPercent(result.benchmark_return)}
                />
                <MetricCard label="Rebalances" value={String(result.rebalance_count)} />
                <MetricCard label="Fills" value={`${result.trade_count} (${result.partial_fill_count} partial, ${result.deferred_fill_count} deferred)`} />
              </div>
              <p className="text-xs text-slate-500 mt-4" data-testid="backtest-provenance">
                Method v{result.provenance.method_version}. Buy window {String(result.provenance.execution_policy.buy_window_sessions)} sessions; fills capped at {formatPercent(String(result.provenance.execution_policy.participation_cap))} of the session&apos;s traded value. Market data {result.provenance.market_data_version ?? 'unknown'} (revision {result.provenance.data_revision}); build {result.provenance.build_id ?? 'unknown'}.
              </p>
            </Card>

            {result.nontrading_holdings.length > 0 && (
              <Card title="Non-trading holdings at the end" subtitle="No bar for more than 20 sessions. Valued at the last close; zero in the lower bound.">
                <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                        <th scope="col" className="text-left px-3 py-3">Security</th>
                        <th scope="col" className="text-left px-3 py-3">Last bar</th>
                        <th scope="col" className="text-right px-3 py-3">Sessions without a bar</th>
                        <th scope="col" className="text-right px-3 py-3">Weight</th>
                        <th scope="col" className="text-left px-3 py-3">Identity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40">
                      {result.nontrading_holdings.map((h) => (
                        <tr key={h.security_id}>
                          <td className="px-3 py-3"><SecurityCell id={h.security_id} symbols={result.symbols} asOf={h.last_bar_date} /></td>
                          <td className="px-3 py-3">{h.last_bar_date}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{h.sessions_without_bar}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{formatPercent(h.weight)}</td>
                          <td className="px-3 py-3">{h.identity_status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {result.transfers.length > 0 && (
              <Card title="Identity transfers" subtitle="Holdings carried to a successor under a verified rename. No cash or cost moves.">
                <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                        <th scope="col" className="text-left px-3 py-3">Session</th>
                        <th scope="col" className="text-left px-3 py-3">From</th>
                        <th scope="col" className="text-left px-3 py-3">To</th>
                        <th scope="col" className="text-right px-3 py-3">Ratio</th>
                        <th scope="col" className="text-left px-3 py-3">Evidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40">
                      {result.transfers.map((t) => (
                        <tr key={`${t.session}-${t.predecessor_id}`}>
                          <td className="px-3 py-3">{t.session}</td>
                          <td className="px-3 py-3 tabular-nums">{t.predecessor_id}</td>
                          <td className="px-3 py-3 tabular-nums">{t.successor_id}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{t.ratio}</td>
                          <td className="px-3 py-3">{t.evidence_reference}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {equityCurve.length > 0 && (
              <Card title="Equity Curve" subtitle="NAV before trading, at each rebalance">
                <div role="img" aria-label="Equity curve chart" className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={equityCurve}>
                      <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: chartColors.tick }} minTickGap={24} />
                      <YAxis tick={{ fontSize: 10, fill: chartColors.tick }} domain={['auto', 'auto']} width={80} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: chartColors.tooltipBg,
                          border: `1px solid ${chartColors.tooltipBorder}`,
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <Line type="monotone" dataKey="nav" name="NAV" stroke={chartPalette.info} dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            {result.trades.length === 0 && (
              <div role="status" className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                No fills in this range. Read the Eligible column in the rebalance log: a name needs a stored listing date at least 252 days before the decision, and bars to score on.
              </div>
            )}

            {result.trades.length > 0 && (
              <Card
                title="Trades"
                subtitle={
                  result.trades.length > TRADE_ROWS_SHOWN
                    ? `First ${TRADE_ROWS_SHOWN} of ${result.trades.length} fills`
                    : `${result.trades.length} fills`
                }
              >
                <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                        <th scope="col" className="text-left px-3 py-3">Fill date</th>
                        <th scope="col" className="text-left px-3 py-3">Security</th>
                        <th scope="col" className="text-left px-3 py-3">Side</th>
                        <th scope="col" className="text-right px-3 py-3">Quantity</th>
                        <th scope="col" className="text-right px-3 py-3">Price</th>
                        <th scope="col" className="text-right px-3 py-3">Cost</th>
                        <th scope="col" className="text-left px-3 py-3">Note</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40" data-testid="backtest-trades">
                      {result.trades.slice(0, TRADE_ROWS_SHOWN).map((t, i) => (
                        <tr key={`${t.fill_date}-${t.security_id}-${t.side}-${i}`}>
                          <td className="px-3 py-3">{t.fill_date}</td>
                          <td className="px-3 py-3"><SecurityCell id={t.security_id} symbols={result.symbols} asOf={t.fill_date} /></td>
                          <td className="px-3 py-3">{t.side}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{Math.abs(parseFloat(t.quantity)).toLocaleString('en-IN', { maximumFractionDigits: 4 })}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{parseFloat(t.fill_price).toFixed(2)}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{parseFloat(t.cost).toFixed(2)}</td>
                          <td className="px-3 py-3 text-slate-500">
                            {[t.partial ? 'partial' : '', t.delay_sessions > 0 ? `${t.delay_sessions} sessions late` : ''].filter(Boolean).join(', ')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            <Card title="Rebalance Log">
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/60">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 uppercase tracking-wider">
                      <th scope="col" className="text-left px-3 py-3">Decision Date</th>
                      <th scope="col" className="text-left px-3 py-3">Fill Date</th>
                      <th scope="col" className="text-right px-3 py-3">Universe</th>
                      <th scope="col" className="text-right px-3 py-3">Eligible</th>
                      <th scope="col" className="text-right px-3 py-3">Holdings</th>
                      <th scope="col" className="text-right px-3 py-3">Trades</th>
                      <th scope="col" className="text-right px-3 py-3">Cost</th>
                      <th scope="col" className="text-right px-3 py-3">NAV (pre-cost)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40">
                    {result.rebalances.map((r) => (
                      <tr key={r.fill_date} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                        <td className="px-3 py-3 text-slate-700 dark:text-slate-300">{r.decision_date}</td>
                        <td className="px-3 py-3 text-slate-700 dark:text-slate-300">{r.fill_date}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{r.universe_size}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{r.eligible_count}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{r.selected.length}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{r.trade_count}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{parseFloat(r.total_cost).toFixed(2)}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{parseFloat(r.nav_pre_cost).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}

        {!result && !isRunning && !error && (
          <EmptyState message="Pick a date range above and click 'Run Backtest' to see results." />
        )}
      </div>
    </div>
  );
}
