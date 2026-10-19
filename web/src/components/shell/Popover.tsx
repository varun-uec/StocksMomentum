/**
 * A toolbar button that opens a panel of controls below it: the ☰ app menu,
 * the layout chooser and the chart settings. A disclosure, not an ARIA menu,
 * because the panels hold links, checkboxes and radios. Escape or a click
 * outside closes it; Escape returns focus to the button.
 */

import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router';
import { focusRing } from '@/lib/theme';

export function Popover({
  label,
  title,
  icon,
  panelLabel,
  panelClassName = '',
  className = '',
  nav = false,
  children,
}: {
  /** The panel is navigation (the app menu), not a group of controls. */
  nav?: boolean;
  /** The button's accessible name. */
  label: string;
  title?: string;
  icon: React.ReactNode;
  /** The panel's accessible name; defaults to `label`. */
  panelLabel?: string;
  panelClassName?: string;
  className?: string;
  children: (close: () => void) => React.ReactNode;
}) {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const id = `popover-${label.toLowerCase().replace(/\W+/g, '-')}`;

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    rootRef.current?.querySelector<HTMLElement>(`#${id} a, #${id} input:checked, #${id} input, #${id} button`)?.focus();
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, id]);

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        title={title ?? label}
        onClick={() => setOpen((o) => !o)}
        className={`ws-icon-button ${focusRing}`}
      >
        {icon}
      </button>
      {open &&
        (nav ? (
          <nav id={id} aria-label={panelLabel ?? label} className={`ws-popover top-[34px] ${panelClassName}`}>
            {children(() => setOpen(false))}
          </nav>
        ) : (
          <div id={id} role="group" aria-label={panelLabel ?? label} className={`ws-popover top-[34px] ${panelClassName}`}>
            {children(() => setOpen(false))}
          </div>
        ))}
    </div>
  );
}
