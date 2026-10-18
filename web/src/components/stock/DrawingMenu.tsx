import { useEffect, useRef, type RefObject } from 'react';
import { DRAWING_COLORS, DRAWING_WIDTHS, type ChartDrawing } from '@/components/stock/chart-drawings';
import type { PriceScale } from '@/components/stock/chart-types';
import { focusRing } from '@/lib/theme';

const COLOR_NAMES: Record<string, string> = {
  '#6366f1': 'Indigo',
  '#0ea5e9': 'Sky',
  '#10b981': 'Emerald',
  '#f59e0b': 'Amber',
  '#ef4444': 'Rose',
  '#64748b': 'Slate',
};

const MENU_CLASS =
  'absolute z-20 w-44 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg p-1.5 space-y-1.5';
const ITEM_CLASS = `px-2 py-1 rounded text-left text-xs hover:bg-slate-100 dark:hover:bg-slate-800 ${focusRing}`;

/** Focus the menu's first item; a pointer press outside it closes it. */
function useMenu(ref: RefObject<HTMLDivElement | null>, onClose: () => void): void {
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>('[role^="menuitem"]')?.focus();
    const away = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    window.addEventListener('pointerdown', away, { capture: true });
    return () => window.removeEventListener('pointerdown', away, { capture: true });
  }, [ref, onClose]);
}

function closeOnEscape(e: React.KeyboardEvent, onClose: () => void): void {
  e.stopPropagation();
  if (e.key === 'Escape') onClose();
}

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
  useMenu(ref, onClose);

  return (
    <div
      ref={ref}
      role="menu"
      aria-label="Drawing"
      onKeyDown={(e) => closeOnEscape(e, onClose)}
      style={{ left: at.x, top: at.y }}
      className={MENU_CLASS}
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
            className={ITEM_CLASS}
            onClick={() => {
              const text = window.prompt('Note text', drawing.text ?? '')?.trim().slice(0, 200);
              if (text) onChange({ ...drawing, text });
              onClose();
            }}
          >
            Edit text…
          </button>
        )}
        <button type="button" role="menuitem" className={`${ITEM_CLASS} text-rose-600 dark:text-rose-400`} onClick={onDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}

const SCALES: { id: PriceScale; label: string }[] = [
  { id: 'normal', label: 'Normal scale' },
  { id: 'log', label: 'Log scale' },
  { id: 'percent', label: 'Percent scale' },
];

/**
 * The chart's context menu (M13): reset the view, pick the price scale, open
 * the indicator list. Opened by a right-click away from any drawing, or the
 * ContextMenu key / Shift+F10 when no drawing is selected.
 */
export function ChartMenu({
  at,
  scale,
  onScale,
  onReset,
  onIndicators,
  onClose,
}: {
  at: { x: number; y: number };
  scale: PriceScale;
  onScale: (scale: PriceScale) => void;
  onReset: () => void;
  onIndicators?: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useMenu(ref, onClose);
  const run = (action: () => void) => () => {
    action();
    onClose();
  };

  return (
    <div
      ref={ref}
      role="menu"
      aria-label="Chart"
      onKeyDown={(e) => closeOnEscape(e, onClose)}
      style={{ left: at.x, top: at.y }}
      className={`${MENU_CLASS} flex flex-col`}
    >
      <button type="button" role="menuitem" className={ITEM_CLASS} onClick={run(onReset)}>
        Reset view
      </button>
      {onIndicators && (
        <button type="button" role="menuitem" className={ITEM_CLASS} onClick={run(onIndicators)}>
          Indicators…
        </button>
      )}
      <div role="group" aria-label="Price scale" className="flex flex-col border-t border-slate-100 dark:border-slate-800 pt-1">
        {SCALES.map((s) => (
          <button
            key={s.id}
            type="button"
            role="menuitemradio"
            aria-checked={scale === s.id}
            className={ITEM_CLASS}
            onClick={run(() => onScale(s.id))}
          >
            {scale === s.id ? '● ' : '○ '}
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
