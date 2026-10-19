import { useEffect, useRef, useState, type ReactNode } from 'react';

/** A compact inspector with native disclosure semantics and predictable dismissal. */
export function InspectorDisclosure({ label, name, children }: { label: ReactNode; name?: string; children: ReactNode }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) ref.current.open = false;
    };
    document.addEventListener('pointerdown', away, true);
    return () => document.removeEventListener('pointerdown', away, true);
  }, [open]);
  return <details ref={ref} className="study-options" onToggle={(e) => setOpen(e.currentTarget.open)} onKeyDown={(e) => {
    if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); if (ref.current) ref.current.open = false; ref.current?.querySelector('summary')?.focus(); }
  }}><summary className="workstation-button" aria-label={name}>{label}</summary>{children}</details>;
}
