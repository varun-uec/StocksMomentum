'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Badge,
  Card,
  ErrorMessage,
  LoadingSpinner,
  PageHeader,
} from '@/components/shared/Card';
import { getDataFreshness, refreshLatestMarketData } from '@/lib/api-client';
import { focusRing } from '@/lib/theme';
import type { Exchange, ExchangeRefreshResult } from '@/lib/types';

const SCOPES: { label: string; exchanges: Exchange[] }[] = [
  { label: 'NSE', exchanges: ['NSE'] },
  { label: 'BSE', exchanges: ['BSE'] },
  { label: 'NSE + BSE', exchanges: ['NSE', 'BSE'] },
];

const STATUS_COLOR: Record<string, 'emerald' | 'amber' | 'rose'> = {
  success: 'emerald',
  partial: 'amber',
  failed: 'rose',
};

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className="text-lg font-semibold text-slate-800 dark:text-slate-200 tabular-nums">
        {value.toLocaleString()}
      </div>
    </div>
  );
}

function ResultCard({ result }: { result: ExchangeRefreshResult }) {
  return (
    <Card
      title={result.exchange}
      badge={
        result.provider_error
          ? { text: 'Failed', color: 'rose' }
          : { text: `${result.rows_written.toLocaleString()} rows written`, color: 'emerald' }
      }
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Stat label="Bars fetched" value={result.bars_fetched} />
        <Stat label="Matched" value={result.securities_matched} />
        <Stat label="Missing" value={result.securities_missing} />
        <Stat label="Unmapped" value={result.securities_unmapped} />
      </div>
      {result.provider_error && (
        <p className="mt-3 text-xs text-rose-600 dark:text-rose-400">{result.provider_error}</p>
      )}
      {result.warnings.map((warning) => (
        <p key={warning} className="mt-3 text-xs text-amber-600 dark:text-amber-400">
          {warning}
        </p>
      ))}
    </Card>
  );
}

export default function DataPage() {
  const queryClient = useQueryClient();
  const [scopeIndex, setScopeIndex] = useState(0);

  const { data: freshness } = useQuery({
    queryKey: ['data-freshness'],
    queryFn: getDataFreshness,
  });

  const refresh = useMutation({
    mutationFn: () => refreshLatestMarketData(SCOPES[scopeIndex].exchanges),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['data-freshness'] }),
  });

  const summary = refresh.data;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Market Data"
        subtitle="Ingest the latest completed trading session on demand"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <Card title="Stored data">
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Latest stored bar
              </div>
              <div className="text-lg font-semibold tabular-nums">
                {freshness?.latest_bar_date ?? '—'}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Sessions missed
              </div>
              <div className="text-lg font-semibold tabular-nums">
                {freshness?.sessions_missed ?? '—'}
              </div>
            </div>
            {freshness && (
              <Badge color={freshness.classification === 'STALE' ? 'rose' : 'emerald'}>
                {freshness.classification}
              </Badge>
            )}
          </div>
        </Card>

        <Card
          title="Refresh latest market data"
          subtitle="Fetches one session (the latest completed one) and upserts it. Repeat runs are idempotent. This does not start a screening run."
        >
          <div className="flex flex-wrap items-center gap-3">
            <div
              role="radiogroup"
              aria-label="Exchange scope"
              className="flex items-center gap-0.5 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-0.5"
            >
              {SCOPES.map((scope, i) => (
                <button
                  key={scope.label}
                  type="button"
                  role="radio"
                  aria-checked={i === scopeIndex}
                  onClick={() => setScopeIndex(i)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${focusRing} ${
                    i === scopeIndex
                      ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-300 shadow-sm'
                      : 'text-slate-500 dark:text-slate-400'
                  }`}
                >
                  {scope.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => refresh.mutate()}
              disabled={refresh.isPending}
              className={`px-4 py-2 rounded-md text-sm font-medium bg-indigo-600 text-white disabled:opacity-60 ${focusRing}`}
            >
              {refresh.isPending ? 'Refreshing…' : 'Refresh Latest Market Data'}
            </button>
          </div>

          {refresh.isPending && (
            <div className="mt-4">
              <LoadingSpinner text="Fetching the latest session…" />
            </div>
          )}
          {refresh.isError && (
            <div className="mt-4">
              <ErrorMessage
                message={
                  refresh.error instanceof Error ? refresh.error.message : 'Refresh failed.'
                }
                onRetry={() => refresh.mutate()}
              />
            </div>
          )}
        </Card>

        {summary && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <Badge color={STATUS_COLOR[summary.overall_status] ?? 'slate'}>
                {summary.overall_status}
              </Badge>
              <span className="text-sm text-slate-600 dark:text-slate-400">
                Session {summary.target_date} · {summary.duration_seconds.toFixed(2)}s
              </span>
            </div>
            {summary.results.map((result) => (
              <ResultCard key={result.exchange} result={result} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
