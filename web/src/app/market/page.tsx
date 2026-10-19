/**
 * Phase 6.6 / 6.7 — universe-level market context.
 *
 * Separate from the stock-detail pages because every figure here describes the
 * tracked universe as a whole, not any one security.
 */

import { useQuery } from '@tanstack/react-query';
import { ErrorMessage, LoadingSpinner, PageHeader } from '@/components/shared/Card';
import { MarketBreadthPanel } from '@/components/market/MarketBreadthPanel';
import { SectorStrengthTable } from '@/components/market/SectorStrengthTable';
import { getMarketContext } from '@/lib/api-client';
import type { MarketContext } from '@/lib/types';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Reject malformed JSON at this API boundary before it reaches nested panels. */
function isMarketContext(value: unknown): value is MarketContext {
  if (!isRecord(value) || typeof value.as_of !== 'string') return false;
  if (value.benchmark_index !== null && typeof value.benchmark_index !== 'string') return false;
  if (!Array.isArray(value.sectors)) return false;
  const breadth = value.breadth;
  if (!isRecord(breadth)) return false;
  if (value.sectors_unavailable_reason !== null && typeof value.sectors_unavailable_reason !== 'string') return false;

  const numericBreadth = [
    'evaluated', 'above_sma50', 'above_sma50_of', 'above_sma200', 'above_sma200_of',
    'new_52w_highs', 'new_52w_lows', 'high_low_of',
  ];
  const percentageBreadth = ['pct_above_sma50', 'pct_above_sma200'];
  if (numericBreadth.some((key) => typeof breadth[key] !== 'number')) return false;
  if (typeof breadth.as_of !== 'string') return false;
  if (percentageBreadth.some((key) => breadth[key] !== null && typeof breadth[key] !== 'string')) return false;

  return value.sectors.every((sector) => {
    if (!isRecord(sector) || typeof sector.sector !== 'string') return false;
    if (typeof sector.constituents !== 'number' || typeof sector.rank !== 'number') return false;
    const excessReturns = sector.excess_return_pct;
    if (!isRecord(excessReturns)) return false;
    return ['1m', '3m', '6m', '12m'].every(
      (period) => excessReturns[period] === null || typeof excessReturns[period] === 'string',
    );
  });
}

export default function MarketPage() {
  const { data: responseData, isLoading, error } = useQuery({
    queryKey: ['market-context'],
    queryFn: () => getMarketContext(),
  });
  const data = isMarketContext(responseData) ? responseData : undefined;
  const incompleteResponse = responseData !== undefined && data === undefined;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Market"
        subtitle={
          data
            ? `Universe breadth and sector strength as of ${data.as_of}`
            : 'Universe breadth and sector strength'
        }
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {isLoading && <LoadingSpinner text="Computing universe breadth…" />}
        {error && (
          <ErrorMessage message="Market context could not be computed. This needs ingested price history for the universe." />
        )}
        {incompleteResponse && (
          <ErrorMessage message="Market context response was incomplete. Reload after checking the API response." />
        )}
        {data && (
          <>
            <MarketBreadthPanel breadth={data.breadth} />
            <SectorStrengthTable
              sectors={data.sectors}
              benchmarkIndex={data.benchmark_index}
              unavailableReason={data.sectors_unavailable_reason}
            />
          </>
        )}
      </div>
    </div>
  );
}
