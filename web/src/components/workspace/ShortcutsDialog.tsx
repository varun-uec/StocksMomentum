import { useEffect, useRef } from 'react';
import { SHORTCUTS } from '@/lib/shortcuts';
import { focusRing } from '@/lib/theme';

/** The workspace's keyboard shortcuts, in a native modal dialog (Esc closes). */
export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (open && dialog && !dialog.open) dialog.showModal();
    if (!open && dialog?.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby="shortcuts-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className="w-[30rem] max-w-[calc(100vw-2rem)] p-0 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xl backdrop:bg-slate-950/50"
    >
      <h2 id="shortcuts-title" className="px-4 pt-4 pb-2 text-sm font-semibold">
        Keyboard shortcuts
      </h2>
      <table className="w-full text-xs">
        <tbody>
          {SHORTCUTS.map((s) => (
            <tr key={s.keys} className="border-t border-slate-100 dark:border-slate-800">
              <th scope="row" className="px-4 py-1.5 text-left font-mono font-normal text-slate-600 dark:text-slate-300 whitespace-nowrap">
                {s.keys}
              </th>
              <td className="px-4 py-1.5 text-slate-700 dark:text-slate-300">{s.action}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <form method="dialog" className="px-4 py-3 text-right">
        <button type="submit" className={`px-3 py-1 rounded-md border border-slate-300 dark:border-slate-600 text-xs ${focusRing}`}>
          Close
        </button>
      </form>
    </dialog>
  );
}
