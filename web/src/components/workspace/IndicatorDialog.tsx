import { useEffect, useRef, type ComponentProps } from 'react';
import { OverlayPicker } from '@/components/stock/OverlayPicker';

/** The catalogue indicator picker in a native modal dialog (Esc closes). */
export function IndicatorDialog({
  open,
  onClose,
  ...picker
}: { open: boolean; onClose: () => void } & ComponentProps<typeof OverlayPicker>) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (open && dialog && !dialog.open) dialog.showModal();
    if (!open && dialog?.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby="indicators-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className="w-[46rem] max-w-[calc(100vw-2rem)] p-0 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xl backdrop:bg-slate-950/50"
    >
      <h2 id="indicators-title" className="px-4 pt-4 pb-2 text-sm font-semibold">
        Indicators
      </h2>
      <div className="px-4">{open && <OverlayPicker {...picker} />}</div>
      <form method="dialog" className="px-4 py-3 text-right">
        <button type="submit" className="px-3 py-1 rounded-md border border-slate-300 dark:border-slate-600 text-xs">
          Close
        </button>
      </form>
    </dialog>
  );
}
