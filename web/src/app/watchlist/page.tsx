'use client';

import { PageHeader } from '@/components/shared/Card';
import { StrategySelector } from '@/components/dashboard/StrategySelector';
import { WatchlistTable } from '@/components/stock/WatchlistTable';
import { useStrategy } from '@/app/strategy-context';
import { strategyDisplayName } from '@/lib/format';

export default function WatchlistPage() {
  const { strategyName } = useStrategy();
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader title="Watchlist" subtitle={`Tracked symbols · ${strategyDisplayName(strategyName)}`}>
        <StrategySelector />
      </PageHeader>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <WatchlistTable strategy={strategyName} />
      </div>
    </div>
  );
}
