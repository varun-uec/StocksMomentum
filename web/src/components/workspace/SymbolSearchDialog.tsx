import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { focusRing } from '@/lib/theme';
import { useSecuritySearch } from '@/components/workspace/useSecuritySearch';

/**
 * Symbol search over the chart (design record D1). Opened by typing on the
 * chart, `/`, or Ctrl/⌘+K, with the first typed character already in the box.
 * ↑/↓ choose, Enter opens, Esc closes and returns focus to the chart.
 * Uses the native modal `<dialog>`, which traps focus and handles Esc.
 */
export function SymbolSearchDialog({
  open,
  initialText,
  onChoose,
  onClose,
  label = 'Search symbols',
}: {
  open: boolean;
  /** The dialog's accessible name, for a search with another purpose (compare). */
  label?: string;
  initialText: string;
  onChoose: (symbol: string) => void;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(initialText);
  const [active, setActive] = useState(0);
  const { query, results, searching } = useSecuritySearch(value, 10);

  useEffect(() => setActive(0), [results]);

  // A layout effect: the opening text must be in the box before the next key
  // arrives, or a fast typist's second letter replaces the first.
  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setValue(initialText);
      dialog.showModal();
      inputRef.current?.focus({ preventScroll: true });
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open, initialText]);

  const choose = (symbol: string) => {
    onChoose(symbol.toUpperCase());
    onClose();
  };

  return (
    <dialog
      ref={dialogRef}
      aria-label={label}
      onCancel={(e) => {
        // Keep React's open state and the workspace's shortcut guard in sync
        // when Escape closes the native modal.
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose(); // a click on the backdrop
      }}
      className="w-[32rem] max-w-[calc(100vw-2rem)] mt-[12vh] p-0 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xl backdrop:bg-slate-950/50"
    >
      <form
        method="dialog"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          const chosen = results[active] ?? results[0];
          const symbol = chosen ? chosen.symbol : query;
          if (symbol) choose(symbol);
        }}
      >
        <input
          ref={inputRef}
          autoFocus
          aria-label="Symbol or company"
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls="symbol-dialog-results"
          aria-activedescendant={results[active] ? `symbol-option-${results[active].symbol}` : undefined}
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (!results.length) return;
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setActive((i) => (i + 1) % results.length);
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setActive((i) => (i <= 0 ? results.length - 1 : i - 1));
            }
          }}
          placeholder="Symbol or company…"
          className={`w-full px-4 py-3 text-base uppercase tracking-wide bg-transparent border-b border-slate-200 dark:border-slate-700 placeholder:normal-case placeholder:tracking-normal placeholder:text-slate-400 rounded-t-xl ${focusRing}`}
        />
      </form>
      <ul id="symbol-dialog-results" role="listbox" className="max-h-80 overflow-y-auto py-1">
        {results.map((r, i) => (
          <li
            key={r.symbol}
            id={`symbol-option-${r.symbol}`}
            role="option"
            aria-selected={i === active}
            onMouseEnter={() => setActive(i)}
            onClick={() => choose(r.symbol)}
            className={`flex items-baseline gap-3 px-4 py-2 cursor-pointer ${i === active ? 'bg-indigo-50 dark:bg-indigo-600/20' : ''}`}
          >
            <span className="w-28 shrink-0 text-sm font-semibold">{r.symbol}</span>
            <span className="flex-1 truncate text-sm text-slate-600 dark:text-slate-300">{r.name}</span>
            <span className="text-[11px] text-slate-400">NSE</span>
          </li>
        ))}
        {query && !results.length && (
          <li className="px-4 py-3 text-sm text-slate-500">
            {searching ? 'Searching…' : `No NSE symbol matches “${query}”.`}
          </li>
        )}
      </ul>
      <p className="px-4 py-2 border-t border-slate-200 dark:border-slate-700 text-[11px] text-slate-500">
        ↑↓ choose · Enter open · Esc close
      </p>
    </dialog>
  );
}
