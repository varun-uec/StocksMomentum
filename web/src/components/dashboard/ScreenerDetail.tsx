/**
 * The screener's detail panel (M12, M9 wireframe 5.4): the selected row's
 * last year of closes and the run's own explanation of its rank.
 */

import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from 'recharts';
import { ExplanationSummary } from '@/components/workspace/ExplanationSummary';
import { getOhlcv, getStockExplanation } from '@/lib/api-client';
import { focusRing } from '@/lib/theme';
import { useChartColors } from '@/lib/useChartColors';

function oneYearAgo(): string {
  const d = new Date();
  d.setUTCFullYear(d.getUTCFullYear() - 1);
  return d.toISOString().slice(0, 10);
}

export function ScreenerDetail({ symbol, runId, strategy }: { symbol: string; runId: number | undefined; strategy: string }) {
  const colors = useChartColors();
  const { data: prices } = useQuery({
    queryKey: ['screener-mini-chart', symbol],
    queryFn: () => getOhlcv(symbol, oneYearAgo()),
  });
  const { data: explanation, isLoading, error } = useQuery({
    queryKey: ['stock-explanation', symbol, strategy, runId],
    queryFn: () => getStockExplanation(symbol, runId, strategy),
    retry: false,
  });
  const closes = (prices?.bars ?? []).map((b) => ({ date: b.date, close: parseFloat(b.close) }));

  return (
    <aside aria-label={`${symbol} in this run`} className="rounded-xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-900 p-4 space-y-3 lg:sticky lg:top-4">
      <h2 className="text-sm font-bold">{symbol}</h2>
      <div className="h-32" aria-label={`${symbol}, last year of closes`} role="img">
        {closes.length > 1 && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={closes}>
              <YAxis hide domain={['auto', 'auto']} />
              <Tooltip
                formatter={(value) => (typeof value === 'number' ? value.toFixed(2) : String(value))}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
                contentStyle={{ backgroundColor: colors.tooltipBg, borderColor: colors.tooltipBorder, fontSize: 11 }}
              />
              <Line type="monotone" dataKey="close" dot={false} strokeWidth={1.5} stroke="#6366f1" isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      {isLoading && <p className="text-xs text-slate-500">Loading the explanation…</p>}
      {error && <p className="text-xs text-slate-500">This run has no explanation for {symbol}.</p>}
      {explanation && <ExplanationSummary explanation={explanation} />}
      <div className="flex gap-3 text-xs">
        <Link to={`/chart/${encodeURIComponent(symbol)}`} className={`text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}>
          Open chart →
        </Link>
        <Link to={`/stock/${encodeURIComponent(symbol)}?strategy=${strategy}`} className={`text-indigo-600 dark:text-indigo-400 hover:underline ${focusRing}`}>
          Full research →
        </Link>
      </div>
    </aside>
  );
}
