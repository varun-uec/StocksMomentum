import type { SaveStatus } from '@/lib/server-document';

const time = (d: Date) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

/**
 * One line that says whether the owner's work is safe (design record D4).
 * Takes every document on screen and reports the least safe state.
 */
export function SaveState({
  documents,
}: {
  documents: { status: SaveStatus; savedAt: Date | null; retry: () => void }[];
}) {
  const failed = documents.find((d) => d.status === 'error');
  if (failed) {
    return (
      <span role="status" className="text-xs text-rose-600 dark:text-rose-400">
        Not saved.{' '}
        <button type="button" className="underline" onClick={() => documents.forEach((d) => d.retry())}>
          Retry
        </button>
      </span>
    );
  }
  if (documents.some((d) => d.status === 'unsaved' || d.status === 'saving')) {
    return <span role="status" className="text-xs text-slate-500">Saving…</span>;
  }
  if (documents.some((d) => d.status === 'loading' || d.status === 'conflict')) return null;
  const last = documents.map((d) => d.savedAt).filter((d): d is Date => d !== null).sort((a, b) => +b - +a)[0];
  return (
    <span role="status" data-testid="save-state" className="text-xs text-emerald-700 dark:text-emerald-400">
      {last ? `Saved ✓ ${time(last)}` : 'Saved ✓'}
    </span>
  );
}

/** Shown when this window and another changed the same drawing (design record D5). */
export function ConflictNotice({ symbol, onResolve }: { symbol: string; onResolve: (choice: 'mine' | 'theirs') => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-sm text-amber-900 dark:text-amber-200">
      <span>⚠ Your drawings on {symbol} changed in another window.</span>
      <button type="button" onClick={() => onResolve('theirs')} className="px-2 py-1 rounded-md border border-amber-400 dark:border-amber-600 text-xs font-medium">
        Keep theirs
      </button>
      <button type="button" onClick={() => onResolve('mine')} className="px-2 py-1 rounded-md bg-amber-600 text-white text-xs font-medium">
        Apply mine
      </button>
    </div>
  );
}
