/**
 * The compare tray (ui-ux doc 02, CompareTray) and the per-fund Watch and
 * Compare buttons. The tray shows only after the first selection, holds 2–5
 * distinct funds and announces each change to screen readers.
 */
import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router';
import { schemeName } from '../format';
import { COMPARE_LIMIT, addToTray, clearTray, removeFromTray, useCompareTray, useWatchlist } from '../workspace';
import { I } from './icons';
import { Button, buttonClass, cx } from './ui';

/** Tell screen-reader users what changed; the tray's live region speaks it. */
function announce(text: string) {
  window.dispatchEvent(new CustomEvent<string>('mf-announce', { detail: text }));
}

export function CompareTray() {
  const { funds } = useCompareTray();
  const { pathname } = useLocation();
  const [message, setMessage] = useState('');
  useEffect(() => {
    const onAnnounce = (e: Event) => setMessage((e as CustomEvent<string>).detail);
    window.addEventListener('mf-announce', onAnnounce);
    return () => window.removeEventListener('mf-announce', onAnnounce);
  }, []);
  // Wide screens only: on phones the Compare tab in the bottom bar shows the count (assessment 25 Oct, rank 7).
  const hidden = funds.length === 0 || pathname.startsWith('/mf/compare');
  return (
    <>
      <p className="sr-only" aria-live="polite">
        {message}
      </p>
      {!hidden && (
        <aside aria-label="Compare tray" className="mf-rise fixed bottom-5 left-[252px] z-30 hidden max-w-[720px] lg:block">
          <div className="flex h-12 items-center gap-3 rounded-[14px] border border-mf-line bg-mf-surface/95 px-2 pl-4 shadow-raised backdrop-blur">
            <p className="shrink-0 text-sm font-medium">
              Compare <span className="text-mf-muted">{funds.length}/{COMPARE_LIMIT}</span>
            </p>
            <ul className="mf-scroll flex min-w-0 flex-1 gap-1.5 overflow-x-auto">
              {funds.map((f) => (
                <li key={f.code} className="flex shrink-0 items-center gap-1 rounded-full bg-mf-sunken py-1 pl-3 pr-1 text-xs">
                  <span className="max-w-[160px] truncate">{schemeName(f.name)}</span>
                  <button
                    type="button"
                    onClick={() => {
                      removeFromTray(f.code);
                      setMessage(`Removed ${f.name} from comparison`);
                    }}
                    aria-label={`Remove ${f.name} from comparison`}
                    className="grid h-6 w-6 place-items-center rounded-full hover:bg-mf-line"
                  >
                    <I.x className="h-3 w-3" />
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => {
                clearTray();
                setMessage('Cleared the comparison');
              }}
              className="relative px-1 text-xs text-mf-muted before:absolute before:-inset-x-1 before:-inset-y-3 before:content-[''] hover:text-mf-ink"
            >
              Clear
            </button>
            {funds.length >= 2 ? (
              <Link to={`/mf/compare?${funds.map((f) => `code=${f.code}`).join('&')}`} className={buttonClass('primary', 'sm')}>
                Compare
              </Link>
            ) : (
              <span className="text-xs text-mf-muted">Add one more</span>
            )}
          </div>
        </aside>
      )}
    </>
  );
}

export function CompareButton({ code, name, size = 'sm', label }: { code: string; name: string; size?: 'sm' | 'md'; label?: boolean }) {
  const { has, full } = useCompareTray();
  const selected = has(code);
  return (
    <Button
      size={size}
      variant={selected ? 'primary' : 'secondary'}
      aria-pressed={selected}
      title={!selected && full ? `You can compare up to ${COMPARE_LIMIT} funds` : undefined}
      aria-label={label ? undefined : `${selected ? 'Remove' : 'Add'} ${name} ${selected ? 'from' : 'to'} comparison`}
      onClick={() => {
        if (selected) {
          removeFromTray(code);
          announce(`Removed ${name} from comparison`);
        } else if (addToTray({ code, name })) announce(`Added ${name} to comparison`);
        else announce(`The comparison is full. Remove a fund to add ${name}; up to ${COMPARE_LIMIT} funds fit.`);
      }}
    >
      {selected ? <I.check className="h-4 w-4" /> : <I.compare className="h-4 w-4" />}
      {label && (selected ? 'In comparison' : 'Add to compare')}
    </Button>
  );
}

export function WatchButton({ code, name, size = 'sm', label }: { code: string; name: string; size?: 'sm' | 'md'; label?: boolean }) {
  const watch = useWatchlist();
  const on = watch.isWatched(code);
  const failed = watch.failed?.code === code;
  return (
    <span className="relative inline-flex">
      <Button
        size={size}
        variant="secondary"
        aria-pressed={on}
        disabled={watch.loading || watch.pending}
        aria-label={label ? undefined : `${on ? 'Remove' : 'Add'} ${name} ${on ? 'from' : 'to'} ${watch.destination}`}
        title={`Saves to “${watch.destination}”`}
        onClick={() => watch.toggle(code)}
        className={cx(on && 'text-mf-brand-strong')}
      >
        <I.star className={cx('h-4 w-4', on && 'fill-current')} />
        {label && (on ? 'Watching' : 'Add to watchlist')}
      </Button>
      {failed && (
        <span role="alert" className="absolute right-0 top-full z-30 mt-1.5 w-60 rounded-[10px] border border-mf-loss/30 bg-mf-surface p-2.5 text-xs text-mf-ink shadow-raised">
          Could not update “{watch.destination}”. Nothing changed.{' '}
          <button type="button" className="font-medium text-mf-brand-strong underline" onClick={watch.retry}>
            Try again
          </button>
        </span>
      )}
    </span>
  );
}
