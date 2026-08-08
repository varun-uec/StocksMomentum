'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

interface FloatingPanelProps {
  trigger: (props: { ref: React.RefObject<HTMLButtonElement>; onClick: () => void; open: boolean }) => ReactNode;
  children: ReactNode;
  panelClassName?: string;
}

/**
 * A click-triggered panel rendered via a portal to `document.body`.
 *
 * Table cells commonly sit inside an `overflow-x-auto` scroll container so the
 * table can scroll horizontally on narrow viewports -- but per the CSS spec,
 * setting `overflow-x` to a non-visible value forces the paired `overflow-y`
 * axis to compute as `auto` too, so any `position: absolute` popover anchored
 * inside that container gets clipped instead of floating above the page. A
 * portal escapes the ancestor entirely, so the panel is never clipped
 * regardless of which row or column it opens from.
 */
export function FloatingPanel({ trigger, children, panelClassName = '' }: FloatingPanelProps) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const reposition = () => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const panelWidth = 260;
    const panelHeight = panelRef.current?.offsetHeight ?? 240;
    const margin = 8;

    let left = rect.left;
    if (left + panelWidth > window.innerWidth - margin) {
      left = window.innerWidth - panelWidth - margin;
    }
    left = Math.max(margin, left);

    let top = rect.bottom + margin;
    if (top + panelHeight > window.innerHeight - margin) {
      // Not enough room below -- flip above the trigger instead of clipping.
      top = Math.max(margin, rect.top - panelHeight - margin);
    }

    setCoords({ top, left });
  };

  useEffect(() => {
    if (!open) return;
    reposition();

    const handleOutside = (e: MouseEvent) => {
      if (
        panelRef.current?.contains(e.target as Node) ||
        triggerRef.current?.contains(e.target as Node)
      ) {
        return;
      }
      setOpen(false);
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleKey);
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleKey);
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <>
      {trigger({ ref: triggerRef, onClick: () => setOpen((v) => !v), open })}
      {open &&
        coords &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            style={{ position: 'fixed', top: coords.top, left: coords.left, zIndex: 1000 }}
            className={`w-64 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg shadow-2xl dark:shadow-black/40 ${panelClassName}`}
          >
            {children}
          </div>,
          document.body
        )}
    </>
  );
}
