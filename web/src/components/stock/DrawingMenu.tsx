import { useEffect, useRef } from 'react';
import { DRAWING_COLORS, DRAWING_WIDTHS, type ChartDrawing } from '@/components/stock/chart-drawings';
import { focusRing } from '@/lib/theme';

const COLOR_NAMES: Record<string, string> = {
  '#6366f1': 'Indigo',
  '#0ea5e9': 'Sky',
  '#10b981': 'Emerald',
  '#f59e0b': 'Amber',
  '#ef4444': 'Rose',
  '#64748b': 'Slate',
};

/**
 * A drawing's context menu (M13): colour, line width, text, delete. Opened by
 * a right-click on the drawing, or the ContextMenu key / Shift+F10 when it is
 * selected. Esc or a click elsewhere closes it.
 */
export function DrawingMenu({
  drawing,
  at,
  onChange,
  onDelete,
  onClose,
}: {
  drawing: ChartDrawing;
  at: { x: number; y: number };
  onChange: (next: ChartDrawing) => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>('[role^="menuitem"]')?.focus();
    const away = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    window.addEventListener('pointerdown', away, { capture: true });
    return () => window.removeEventListener('pointerdown', away, { capture: true });
  }, [onClose]);

  const item = `px-2 py-1 rounded text-left text-xs hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`;
  return (
    <div
      ref={ref}
      role="menu"
      aria-label="Drawing"
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === 'Escape') onClose();
      }}
      style={{ left: at.x, top: at.y }}
      className="absolute z-20 w-44 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg p-1.5 space-y-1.5"
    >
      <div role="group" aria-label="Colour" className="flex gap-1">
        {DRAWING_COLORS.map((color) => (
          <button
            key={color}
            type="button"
            role="menuitemradio"
            aria-checked={drawing.color === color}
            aria-label={COLOR_NAMES[color]}
            title={COLOR_NAMES[color]}
            onClick={() => onChange({ ...drawing, color })}
            style={{ backgroundColor: color }}
            className={`w-5 h-5 rounded-full ${focusRing} ${drawing.color === color ? 'ring-2 ring-offset-1 ring-slate-500' : ''}`}
          />
        ))}
      </div>
      <div role="group" aria-label="Line width" className="flex gap-1">
        {DRAWING_WIDTHS.map((width) => (
          <button
            key={width}
            type="button"
            role="menuitemradio"
            aria-checked={(drawing.width ?? 2) === width}
            aria-label={`Width ${width}`}
            onClick={() => onChange({ ...drawing, width })}
            className={`flex-1 h-6 flex items-center justify-center rounded ${focusRing} ${(drawing.width ?? 2) === width ? 'bg-indigo-100 dark:bg-indigo-600/25' : 'hover:bg-slate-100 dark:hover:bg-slate-800'}`}
          >
            <span className="block w-5 bg-current rounded" style={{ height: width }} />
          </button>
        ))}
      </div>
      <div className="flex flex-col">
        {drawing.kind === 'text' && (
          <button
            type="button"
            role="menuitem"
            className={item}
            onClick={() => {
              const text = window.prompt('Note text', drawing.text ?? '')?.trim().slice(0, 200);
              if (text) onChange({ ...drawing, text });
              onClose();
            }}
          >
            Edit text…
          </button>
        )}
        <button type="button" role="menuitem" className={`${item} text-rose-600 dark:text-rose-400`} onClick={onDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}
