/**
 * The chart workspace (M11): Find → Analyse → Draw → Restore.
 *
 * Chart first: the chart takes the free height. Everything the owner sets here
 * (range, moving averages, panes, drawings) is saved on the server as they
 * work, and comes back on reload or in another browser (ADR-013 §5).
 */

import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router';
import { DEFAULT_STRATEGY } from '@/app/strategy-context';
import { LoadingSpinner } from '@/components/shared/Card';
import { PriceChart } from '@/components/stock/PriceChart';
import { useChartShell } from '@/components/stock/useChartShell';
import { SaveState } from '@/components/workspace/SaveState';
import { SymbolSearchDialog } from '@/components/workspace/SymbolSearchDialog';
import { useSecuritySearch } from '@/components/workspace/useSecuritySearch';
import { useSymbolDrawings, useWorkspaceChart } from '@/lib/workspace';

const CHART_ID = 'main';
/** Shown on a fresh install, before the owner has opened any symbol. */
const FIRST_SYMBOL = 'RELIANCE';
/** Header, toolbar and footer around the chart, in px. */
const CHROME_HEIGHT = 300;

function useChartHeight(): number {
  const measure = () => Math.max(320, window.innerHeight - CHROME_HEIGHT);
  const [height, setHeight] = useState(measure);
  useEffect(() => {
    const onResize = () => setHeight(measure());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return height;
}

/** True when a key press should open symbol search instead of typing somewhere. */
function opensSearch(e: KeyboardEvent): { initial: string } | null {
  const target = e.target as HTMLElement | null;
  if (target?.closest('input, textarea, select, [contenteditable="true"], dialog')) return null;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') return { initial: '' };
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  if (e.key === '/') return { initial: '' };
  if (/^[a-z0-9]$/i.test(e.key)) return { initial: e.key };
  return null;
}

export default function ChartPage() {
  const { symbol: routeSymbol } = useParams();
  const workspace = useWorkspaceChart(CHART_ID);

  if (!routeSymbol) {
    if (!workspace.ready) return <LoadingSpinner />;
    return <Navigate replace to={`/chart/${workspace.chart.symbol ?? FIRST_SYMBOL}`} />;
  }
  return <ChartWorkspace symbol={routeSymbol.toUpperCase()} />;
}

function ChartWorkspace({ symbol }: { symbol: string }) {
  const navigate = useNavigate();
  const height = useChartHeight();
  const shell = useChartShell(symbol, DEFAULT_STRATEGY, CHART_ID, { weekly: true });
  const workspace = useWorkspaceChart(CHART_ID);
  const drawings = useSymbolDrawings(symbol);
  const [search, setSearch] = useState<{ open: boolean; initial: string }>({ open: false, initial: '' });

  // Remember the open symbol, so `/chart` and the next visit reopen it.
  useEffect(() => {
    if (workspace.ready && workspace.chart.symbol !== symbol) workspace.update({ symbol });
  }, [workspace.ready, workspace.chart.symbol, symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const open = opensSearch(e);
      if (!open) return;
      e.preventDefault();
      setSearch({ open: true, initial: open.initial });
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const name = useSecuritySearch(symbol, 1).results.find((r) => r.symbol === symbol)?.name;
  const last = shell.bars.at(-1);
  const prev = shell.bars.at(-2);
  const change = last && prev ? (parseFloat(last.close) / parseFloat(prev.close) - 1) * 100 : null;

  return (
    <main className="max-w-screen-2xl mx-auto px-2 sm:px-4 py-3">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-2">
        <h1 className="text-lg font-bold tracking-tight">
          <button
            type="button"
            onClick={() => setSearch({ open: true, initial: '' })}
            title="Change symbol (type, /, or Ctrl/⌘+K)"
            className="hover:text-indigo-600 dark:hover:text-indigo-400"
          >
            {symbol}
          </button>
        </h1>
        {name && <span className="text-sm text-slate-500 dark:text-slate-400">{name}</span>}
        {last && <span className="text-sm font-semibold tabular-nums">{parseFloat(last.close).toFixed(2)}</span>}
        {change !== null && (
          <span className={`text-sm tabular-nums ${change >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
            {change >= 0 ? '+' : ''}
            {change.toFixed(2)}%
          </span>
        )}
        <span className="flex-1" />
        <SaveState documents={[workspace, drawings]} />
      </header>

      {shell.ready ? (
        <PriceChart {...shell.chartProps} height={height} />
      ) : (
        <LoadingSpinner />
      )}

      <SymbolSearchDialog
        open={search.open}
        initialText={search.initial}
        onChoose={(next) => navigate(`/chart/${encodeURIComponent(next)}`)}
        onClose={() => setSearch((s) => ({ ...s, open: false }))}
      />
    </main>
  );
}
