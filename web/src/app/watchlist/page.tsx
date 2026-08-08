'use client';

import { PageHeader } from '@/components/shared/Card';
import { WatchlistTable } from '@/components/stock/WatchlistTable';
import { DEFAULT_HORIZON } from '@/lib/horizons';

export default function WatchlistPage() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader title="Watchlist" subtitle={`Tracked symbols · ${DEFAULT_HORIZON.label} horizon`} />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <WatchlistTable strategy={DEFAULT_HORIZON.strategyName} />
      </div>
    </div>
  );
}
