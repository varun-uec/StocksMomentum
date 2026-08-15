'use client';

/**
 * Loading placeholders that match the shape of the page they stand in for.
 * A skeleton shows the structure immediately, so the reader knows what is
 * arriving instead of watching a centred spinner on an empty screen.
 */

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-slate-200 dark:bg-slate-800 ${className}`} />;
}

/** A card outline with a header bar and `lines` body rows. */
export function SkeletonCard({ lines = 3, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/50 shadow-sm ${className}`}>
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700/40">
        <Skeleton className="h-4 w-40" />
      </div>
      <div className="p-4 space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className="h-3" />
        ))}
      </div>
    </div>
  );
}

export function SkeletonMetricGrid({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-slate-200 dark:border-slate-700/40 bg-slate-50 dark:bg-slate-800/30 px-4 py-3">
          <Skeleton className="h-2.5 w-20" />
          <Skeleton className="h-5 w-16 mt-2" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 8, columns = 6 }: { rows?: number; columns?: number }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-900">
      <div className="flex gap-3 px-3 py-3 bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-3 px-3 py-3 border-b border-slate-100 dark:border-slate-800 last:border-b-0">
          {Array.from({ length: columns }).map((_, c) => (
            <Skeleton key={c} className="h-3 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Wraps a skeleton so assistive tech announces the wait once, not per block. */
export function SkeletonRegion({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className="space-y-6">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
