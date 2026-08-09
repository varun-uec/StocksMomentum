'use client';

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

export default function MarketPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['market-context'],
    queryFn: () => getMarketContext(),
  });

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
