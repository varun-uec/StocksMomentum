/**
 * MF design-system primitives. They use the `mf-*` theme colours only, so a theme
 * change in theme/themes.ts restyles every screen.
 */
import { cloneElement, useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type ReactElement, type ReactNode } from 'react';
import { Link } from 'react-router';
import { MfApiError } from '../api';
import { date, pct, tone } from '../format';
import { I } from './icons';

export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' ');

// ── Surfaces ────────────────────────────────────────────────────────────

export function Card({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
  id,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  id?: string;
}) {
  const headingId = useId();
  return (
    <section
      id={id}
      aria-labelledby={title ? headingId : undefined}
      className={cx('min-w-0 rounded-card border border-mf-line bg-mf-surface shadow-card', className)}
    >
      {(title || action) && (
        <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-5 pt-4">
          <div className="min-w-0">
            {title && (
              <h2 id={headingId} className="text-[15px] font-semibold text-mf-ink">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-0.5 text-xs text-mf-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={cx('px-5 pb-5', title || action ? 'pt-3' : 'pt-5', bodyClassName)}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, lead, actions, eyebrow }: { title: ReactNode; lead?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        {eyebrow && <p className="mb-1 text-xs font-medium uppercase tracking-[0.08em] text-mf-brand">{eyebrow}</p>}
        <h1 className="font-display text-[28px] leading-tight text-mf-ink sm:text-[34px]">{title}</h1>
        {lead && <p className="mt-1.5 text-[15px] text-mf-muted">{lead}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

// ── Controls ────────────────────────────────────────────────────────────

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-mf-brand text-mf-on-brand hover:bg-mf-brand-strong border border-transparent',
  secondary: 'bg-mf-surface text-mf-ink border border-mf-line-strong hover:bg-mf-sunken',
  ghost: 'bg-transparent text-mf-ink-soft border border-transparent hover:bg-mf-sunken',
  danger: 'bg-mf-surface text-mf-loss border border-mf-line-strong hover:bg-mf-loss-soft',
};

export function buttonClass(variant: Variant = 'secondary', size: 'sm' | 'md' = 'md') {
  return cx(
    'inline-flex items-center justify-center gap-1.5 rounded-control font-medium whitespace-nowrap transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50',
    size === 'sm' ? 'h-8 px-2.5 text-[13px]' : 'h-10 px-4 text-sm',
    VARIANTS[variant],
  );
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' }) {
  return <button type="button" {...props} className={cx(buttonClass(variant, size), className)} />;
}

/** A pressable chip; `pressed` makes it a toggle. */
export function Chip({
  pressed,
  onClick,
  children,
  className,
  onRemove,
}: {
  pressed?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  onRemove?: () => void;
}) {
  const base = cx(
    'inline-flex min-h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] transition-colors duration-150',
    pressed ? 'border-mf-brand bg-mf-brand-soft text-mf-brand-strong' : 'border-mf-line-strong bg-mf-surface text-mf-ink-soft hover:bg-mf-sunken',
    className,
  );
  if (onRemove)
    return (
      <span className={cx(base, 'pr-1')}>
        {onClick ? (
          <button type="button" onClick={onClick} className="text-left">
            {children}
          </button>
        ) : (
          children
        )}
        <button type="button" onClick={onRemove} aria-label={`Remove ${typeof children === 'string' ? children : 'condition'}`} className="grid h-6 w-6 place-items-center rounded-full hover:bg-mf-sunken">
          <I.x className="h-3.5 w-3.5" />
        </button>
      </span>
    );
  return (
    <button type="button" aria-pressed={pressed} onClick={onClick} className={base}>
      {children}
    </button>
  );
}

/** A single-choice button group (window, tenor, kind). */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  size = 'sm',
}: {
  label: string;
  options: readonly (T | { value: T; label: string; disabled?: boolean })[];
  value: T;
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-control border border-mf-line bg-mf-sunken p-0.5">
      {options.map((o) => {
        const opt = typeof o === 'string' ? { value: o, label: o, disabled: false } : o;
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={opt.disabled}
            onClick={() => onChange(opt.value)}
            className={cx(
              'rounded-[6px] font-medium transition-colors duration-150 disabled:opacity-40',
              size === 'sm' ? 'h-7 px-2.5 text-xs' : 'h-9 px-3.5 text-sm',
              active ? 'bg-mf-surface text-mf-brand-strong shadow-card' : 'text-mf-muted hover:text-mf-ink',
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

/** Underlined section tabs; each tab is a link, so Back returns to the previous tab and deep links work. */
export function TabLinks({ label, tabs, active }: { label: string; tabs: { id: string; label: string; to: string }[]; active: string }) {
  return (
    <nav aria-label={label} className="mf-scroll -mx-1 overflow-x-auto">
      <ul className="flex min-w-max gap-1 border-b border-mf-line px-1">
        {tabs.map((t) => (
          <li key={t.id}>
            <Link
              to={t.to}
              aria-current={t.id === active ? 'page' : undefined}
              className={cx(
                '-mb-px inline-flex h-11 items-center border-b-2 px-3 text-sm font-medium transition-colors duration-150',
                t.id === active ? 'border-mf-brand text-mf-brand-strong' : 'border-transparent text-mf-muted hover:text-mf-ink',
              )}
            >
              {t.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/**
 * A labelled control. The label points at the control and the hint describes it,
 * so a select's options and the hint never become part of the control's name.
 */
export function Field({ label, hint, children, className }: { label: string; hint?: ReactNode; children: ReactElement<{ id?: string; 'aria-describedby'?: string }>; className?: string }) {
  const id = useId();
  return (
    <div className={cx('block', className)}>
      <label htmlFor={id} className="mb-1 block text-[13px] font-medium text-mf-ink-soft">
        {label}
      </label>
      {cloneElement(children, { id, 'aria-describedby': hint ? `${id}-hint` : undefined })}
      {hint && (
        <span id={`${id}-hint`} className="mt-1 block text-xs text-mf-muted">
          {hint}
        </span>
      )}
    </div>
  );
}

export const inputClass =
  'h-10 w-full rounded-control border border-mf-line-strong bg-mf-surface px-3 text-sm text-mf-ink placeholder:text-mf-muted focus-visible:border-mf-brand';

// ── Data display ────────────────────────────────────────────────────────

type Tone = 'brand' | 'neutral' | 'warning' | 'loss' | 'info' | 'planned';
const BADGES: Record<Tone, string> = {
  brand: 'bg-mf-brand-soft text-mf-brand-strong',
  neutral: 'bg-mf-sunken text-mf-ink-soft',
  warning: 'bg-mf-warning-soft text-mf-warning',
  loss: 'bg-mf-loss-soft text-mf-loss',
  info: 'bg-mf-info-soft text-mf-info',
  planned: 'bg-mf-info-soft text-mf-info',
};

export function Badge({ tone = 'neutral', children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium', BADGES[tone], className)}>{children}</span>;
}

/** A signed return with colour and a sign; the sign carries the meaning, colour only helps. */
export function Delta({ value, digits = 1, className }: { value: unknown; digits?: number; className?: string }) {
  const t = tone(value);
  return <span className={cx('tabular', t === 'gain' && 'text-mf-gain', t === 'loss' && 'text-mf-loss', className)}>{pct(value, digits, true)}</span>;
}

export function Stat({
  label,
  value,
  sub,
  valueClass,
  help,
}: {
  label: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  valueClass?: string;
  help?: ReactNode;
}) {
  return (
    <div className="min-w-0 rounded-[12px] border border-mf-line bg-mf-surface px-4 py-3">
      <div className="flex items-center gap-1 text-xs text-mf-muted">
        {label}
        {help && <InfoTip label={typeof label === 'string' ? label : 'About this value'}>{help}</InfoTip>}
      </div>
      <div className={cx('mt-1 truncate text-[22px] font-semibold leading-tight tabular text-mf-ink', valueClass)}>{value}</div>
      {sub && <div className="mt-0.5 text-xs leading-snug text-mf-muted">{sub}</div>}
    </div>
  );
}

/** A help button that opens a small explanation; Escape or a second press closes it. */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', close);
    document.addEventListener('mousedown', close);
    return () => {
      document.removeEventListener('keydown', close);
      document.removeEventListener('mousedown', close);
    };
  }, [open]);
  return (
    <span ref={ref} className="relative inline-flex">
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="grid h-5 w-5 place-items-center rounded-full text-mf-muted hover:text-mf-brand"
      >
        <I.info className="h-3.5 w-3.5" />
      </button>
      {open && (
        <span id={id} role="note" className="absolute left-1/2 top-6 z-40 w-64 -translate-x-1/2 rounded-[10px] border border-mf-line bg-mf-surface p-3 text-left text-xs font-normal leading-relaxed text-mf-ink-soft shadow-raised">
          {children}
        </span>
      )}
    </span>
  );
}

/** A horizontal 0–100 meter with a label; used for percentiles. */
export function Meter({ value, label }: { value: number | null | undefined; label: string }) {
  const v = typeof value === 'number' ? Math.max(0, Math.min(100, value)) : null;
  return (
    <div role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={v ?? undefined} className="h-1.5 w-full overflow-hidden rounded-full bg-mf-sunken">
      {v !== null && <div className="h-full rounded-full bg-mf-brand transition-[width] duration-300" style={{ width: `${v}%` }} />}
    </div>
  );
}

// ── States ──────────────────────────────────────────────────────────────

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx('mf-skeleton', className)} />;
}

export function Loading({ label = 'Loading', className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cx('space-y-3', className)}>
      <span className="sr-only">{label}…</span>
      <Skeleton className="h-5 w-1/3" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

export function ErrorState({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const status = error instanceof MfApiError ? error.status : undefined;
  const title =
    status === 404 ? 'Not found' : status === 422 ? 'The request was not accepted' : status === 403 ? 'Not permitted by the data rights register' : 'Could not load this view';
  const detail = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className={cx('rounded-[12px] border border-mf-loss/30 bg-mf-loss-soft text-mf-ink', compact ? 'p-3 text-sm' : 'p-5')}>
      <p className="font-medium text-mf-loss">{title}</p>
      {detail && <p className="mt-1 text-sm text-mf-ink-soft">{detail}</p>}
      {onRetry && (
        <Button size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, children, action, art }: { title: string; children?: ReactNode; action?: ReactNode; art?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-card border border-dashed border-mf-line-strong bg-mf-surface/60 px-6 py-10 text-center">
      {art}
      <p className="font-display text-xl text-mf-ink">{title}</p>
      {children && <div className="mt-1.5 max-w-md text-sm text-mf-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/**
 * A capability that needs a named service or dataset first. It never shows a
 * fabricated result or an active control (ui-ux doc 02, DependencyPanel).
 */
export function DependencyPanel({ title, needs, children }: { title: string; needs: string; children?: ReactNode }) {
  return (
    <div className="rounded-[12px] border border-mf-info/25 bg-mf-info-soft/60 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="planned">Planned</Badge>
        <p className="text-sm font-medium text-mf-ink">{title}</p>
      </div>
      <p className="mt-1.5 text-[13px] text-mf-ink-soft">Needs: {needs}</p>
      {children && <div className="mt-1 text-[13px] text-mf-muted">{children}</div>}
    </div>
  );
}

/** Data as-of, snapshot revision and method: shown under every research view. */
export function SnapshotNote({ asOf, revision, method, extra }: { asOf?: string; revision?: number; method?: number; extra?: ReactNode }) {
  if (!asOf) return null;
  return (
    <p className="text-xs text-mf-muted">
      NAV data as of {date(asOf)} · snapshot {revision} · method v{method}
      {extra}
    </p>
  );
}

/** Sets the tab title while a page is open. */
export function useTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · Wickstreet`;
  }, [title]);
}

// ── Dialog ──────────────────────────────────────────────────────────────

/**
 * A modal sheet on a native <dialog>: it traps focus, closes on Escape and
 * returns focus to the opener. Bottom sheet on phones, side drawer on desktop.
 */
export function Sheet({
  open,
  onClose,
  title,
  children,
  footer,
  side = 'right',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  side?: 'right' | 'center';
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className={cx(
        'mf-dialog',
        side === 'right'
          ? 'fixed inset-x-0 bottom-0 top-auto m-0 w-full lg:inset-y-0 lg:left-auto lg:right-0 lg:h-full lg:w-[440px]'
          : 'm-auto w-[min(560px,calc(100vw-32px))]',
      )}
    >
      {open && (
        <div
          className={cx(
            'flex max-h-[88dvh] flex-col bg-mf-surface text-mf-ink shadow-raised',
            side === 'right' ? 'rounded-t-dialog lg:h-full lg:max-h-none lg:rounded-none lg:rounded-l-dialog' : 'rounded-dialog',
          )}
        >
          <header className="flex items-center justify-between gap-3 border-b border-mf-line px-5 py-3.5">
            <h2 id={titleId} className="text-base font-semibold">
              {title}
            </h2>
            <button type="button" onClick={onClose} aria-label="Close" className="grid h-10 w-10 place-items-center rounded-full text-mf-muted hover:bg-mf-sunken">
              <I.x />
            </button>
          </header>
          <div className="mf-scroll min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && <footer className="flex justify-end gap-2 border-t border-mf-line px-5 py-3 pb-[max(12px,env(safe-area-inset-bottom))]">{footer}</footer>}
        </div>
      )}
    </dialog>
  );
}
