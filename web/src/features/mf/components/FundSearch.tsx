/**
 * Fund search: name, AMFI code or ISIN → an exact plan-option (ui-ux doc 02,
 * ResearchSearch). An ARIA combobox: arrows move, Enter opens, Escape closes.
 * Requests wait 250 ms after typing and a newer query cancels the older one.
 */
import { useEffect, useId, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import type { FundHit } from '../api';
import { categoryShort, enumLabel } from '../format';
import { useFundSearch } from '../queries';
import { I } from './icons';
import { Badge, cx } from './ui';
import { useDebounced } from '../use-debounced';


export function FundSearch({
  onPick,
  placeholder = 'Search funds by name, AMFI code or ISIN',
  autoFocus,
  shortcut,
  className,
  size = 'md',
  label = 'Search funds',
}: {
  /** Default: open the fund page. */
  onPick?: (fund: FundHit) => void;
  placeholder?: string;
  autoFocus?: boolean;
  /** Focus with "/" from anywhere on the page. */
  shortcut?: boolean;
  className?: string;
  size?: 'md' | 'lg';
  label?: string;
}) {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const query = useDebounced(text.trim(), 250);
  const search = useFundSearch(query);
  const results = query.length >= 2 ? (search.data?.funds ?? []) : [];
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const statusId = useId();

  useEffect(() => setActive(0), [query]);

  useEffect(() => {
    if (!shortcut) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (e.key !== '/' || target.closest('input, textarea, select, [contenteditable="true"]')) return;
      e.preventDefault();
      inputRef.current?.focus();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [shortcut]);

  const pick = (fund: FundHit) => {
    setOpen(false);
    setText('');
    if (onPick) onPick(fund);
    else navigate(`/mf/funds/${fund.amfi_code}`);
  };

  const showList = open && query.length >= 2;
  const status = search.isFetching ? 'Searching' : `${results.length} fund${results.length === 1 ? '' : 's'} found`;

  return (
    <div className={cx('relative', className)}>
      <label className="sr-only" htmlFor={`${listId}-input`}>
        {label}
      </label>
      <div className={cx('flex items-center gap-2 rounded-control border border-mf-line-strong bg-mf-surface px-3 focus-within:border-mf-brand', size === 'lg' ? 'h-12' : 'h-10')}>
        <I.search className="h-4 w-4 shrink-0 text-mf-muted" />
        <input
          ref={inputRef}
          id={`${listId}-input`}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-describedby={statusId}
          aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          spellCheck={false}
          autoFocus={autoFocus}
          value={text}
          placeholder={placeholder}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setOpen(true);
              setActive((i) => Math.min(i + 1, results.length - 1));
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (e.key === 'Enter' && results[active]) {
              e.preventDefault();
              pick(results[active]);
            } else if (e.key === 'Escape') {
              setOpen(false);
            }
          }}
          className={cx('h-full min-w-0 flex-1 bg-transparent text-mf-ink outline-none placeholder:text-mf-muted', size === 'lg' ? 'text-[15px]' : 'text-sm')}
          style={{ outline: 'none' }}
        />
        {shortcut && !text && (
          <kbd className="hidden rounded border border-mf-line px-1.5 text-[11px] text-mf-muted sm:inline" aria-hidden="true">
            /
          </kbd>
        )}
      </div>
      <p id={statusId} className="sr-only" aria-live="polite">
        {query.length >= 2 ? status : ''}
      </p>
      {showList && (
        <ul id={listId} role="listbox" aria-label="Funds" className="mf-scroll absolute left-0 right-0 top-full z-50 mt-1.5 max-h-[60vh] overflow-y-auto rounded-[12px] border border-mf-line bg-mf-surface p-1 shadow-raised">
          {results.length === 0 && (
            <li className="px-3 py-3 text-sm text-mf-muted" role="presentation">
              {search.isFetching ? 'Searching…' : search.isError ? 'Search failed. Try again.' : 'No fund matches that name, code or ISIN.'}
            </li>
          )}
          {results.map((fund, i) => (
            <li
              key={fund.amfi_code}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(i)}
              onClick={() => pick(fund)}
              className={cx('cursor-pointer rounded-[8px] px-3 py-2', i === active && 'bg-mf-brand-soft')}
            >
              <p className="truncate text-sm font-medium text-mf-ink">{fund.name}</p>
              <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-mf-muted">
                <span>{categoryShort(fund.category)}</span>
                <span aria-hidden="true">·</span>
                <span>
                  {enumLabel(fund.plan)} · {enumLabel(fund.option)}
                </span>
                <span aria-hidden="true">·</span>
                <span>AMFI {fund.amfi_code}</span>
                {!fund.nav_available && <Badge tone="warning">No NAV history</Badge>}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
