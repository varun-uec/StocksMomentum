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
  // A fund page has its own action bar on phones; the tray stays on wide screens.
  const hidden = funds.length === 0 || pathname.startsWith('/mf/compare');
  const onFund = pathname.startsWith('/mf/funds/');
  return (
    <>
      <p className="sr-only" aria-live="polite">
        {message}
      </p>
      {!hidden && (
        <aside aria-label="Compare tray" className={cx('mf-rise fixed inset-x-3 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-30 lg:bottom-5 lg:left-[252px] lg:right-auto lg:max-w-[720px]', onFund && 'hidden lg:block')}>
          <div className="flex h-12 items-center gap-3 rounded-[14px] border border-mf-line bg-mf-surface/95 px-2 pl-4 shadow-raised backdrop-blur">
            <p className="shrink-0 text-sm font-medium">
              Compare <span className="text-mf-muted">{funds.length}/{COMPARE_LIMIT}</span>
            </p>
            <ul className="mf-scroll hidden min-w-0 flex-1 gap-1.5 overflow-x-auto sm:flex">
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
            <button type="button" onClick={clearTray} className="hidden text-xs text-mf-muted hover:text-mf-ink sm:inline">
              Clear
            </button>
            {funds.length >= 2 ? (
              <Link to={`/mf/compare?${funds.map((f) => `code=${f.code}`).join('&')}`} className={cx(buttonClass('primary', 'sm'), 'ml-auto sm:ml-0')}>
                Compare
              </Link>
            ) : (
              <span className="ml-auto text-xs text-mf-muted sm:ml-0">Add one more</span>
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
      {label && (selected ? 'In comparison' : 'Compare')}
    </Button>
  );
}

export function WatchButton({ code, name, size = 'sm', label }: { code: string; name: string; size?: 'sm' | 'md'; label?: boolean }) {
  const watch = useWatchlist();
  const on = watch.isWatched(code);
  return (
    <Button
      size={size}
      variant="secondary"
      aria-pressed={on}
      disabled={watch.loading || watch.pending}
      aria-label={label ? undefined : `${on ? 'Remove' : 'Add'} ${name} ${on ? 'from' : 'to'} watchlist`}
      onClick={() => watch.toggle(code)}
      className={cx(on && 'text-mf-brand-strong')}
    >
      <I.star className={cx('h-4 w-4', on && 'fill-current')} />
      {label && (on ? 'Watching' : 'Add to watchlist')}
    </Button>
  );
}
