/**
 * Screen results: a sortable table with a sticky header and fund column on wide
 * screens, cards with the same columns and order on phones. A missing value
 * shows its reason, never a zero.
 */
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router';
import type { FieldDef, ScreenRow, SortKey } from '../../api';
import { categoryShort, date, formatField, missingLabel, schemeName, tone } from '../../format';
import { useSparklines } from '../../queries';
import { Sparkline } from '../charts';
import { CompareButton, WatchButton } from '../CompareTray';
import { FundMark } from '../FundMark';
import { I } from '../icons';
import { ScoreBadge } from '../ScoreBadge';
import { cx } from '../ui';
import { METRIC_AS_OF_FIELDS } from './FilterRail';

const SIGNED = new Set(['fraction']);

function Cell({ row, column, fields, columns }: { row: ScreenRow; column: string; fields: Map<string, FieldDef>; columns?: string[] }) {
  const value = row.values[column];
  const state = row.states[column];
  if (column === 'score') return <ScoreBadge score={value as number | null} size="sm" />;
  if (state || value === null || value === undefined)
    return (
      <span className="text-mf-muted" title={missingLabel(state)}>
        —<span className="sr-only"> {missingLabel(state)}</span>
      </span>
    );
  if (column === 'category')
    return (
      <span className="inline-block max-w-[150px] truncate align-bottom" title={String(value)}>
        {categoryShort(String(value))}
      </span>
    );
  const field = fields.get(column);
  if (field?.type === 'enum')
    return (
      <span className="inline-block max-w-[150px] truncate align-bottom" title={String(value)}>
        {formatField(field, value, fields)}
      </span>
    );
  const text = field ? formatField(field, value, fields) : typeof value === 'number' ? value.toLocaleString('en-IN', { maximumFractionDigits: 4 }) : String(value);
  const t = field && SIGNED.has(field.unit ?? '') ? tone(value) : 'flat';
  // A filed value carries its filing date in the cell, so it costs no result column.
  const companion = METRIC_AS_OF_FIELDS[column];
  const filed = companion && !columns?.includes(companion) ? row.values[companion] : null;
  return (
    <span className={cx('tabular', t === 'loss' && 'text-mf-loss')}>
      {text}
      {typeof filed === 'string' && <span className="block text-[11px] font-normal leading-tight text-mf-muted">as of {date(filed)}</span>}
    </span>
  );
}

export function columnLabel(column: string, fields: Map<string, FieldDef>): string {
  return fields.get(column)?.label ?? column;
}

export function ResultsTable({
  rows,
  columns,
  fields,
  sort,
  onSort,
  stale,
}: {
  rows: ScreenRow[];
  columns: string[];
  fields: Map<string, FieldDef>;
  sort: SortKey[];
  onSort: (field: string) => void;
  stale?: boolean;
}) {
  const primary = sort[0];
  // With six or more metrics the NAV line gives way on narrower desktops, so the chosen metrics fit (review 2, rank 3).
  const compact = columns.length >= 6;
  // Width hidden to the right of the wide table, so a column never disappears without a cue (review 1, rank 3).
  const wide = useRef<HTMLDivElement>(null);
  const [hidden, setHidden] = useState(0);
  // Hide the entire contents of a column crossing either viewport edge. A paint
  // overlay can sit below sticky headers and leave misleading fragments visible.
  const [clipped, setClipped] = useState<string[]>([]);
  useEffect(() => {
    const el = wide.current;
    if (!el) return;
    const update = () => {
      setHidden(Math.max(0, el.scrollWidth - el.clientWidth - el.scrollLeft));
      const box = el.getBoundingClientRect();
      const fund = el.querySelector('thead th')?.getBoundingClientRect();
      if (!fund) return;
      const next = [...el.querySelectorAll<HTMLElement>('thead th[data-column]')].filter((th) => {
        const r = th.getBoundingClientRect();
        return r.width > 0 && (r.left < fund.right - 1 || r.right > box.right - 1);
      }).map((th) => th.dataset.column!);
      setClipped((previous) => previous.join('|') === next.join('|') ? previous : next);
    };
    update();
    el.addEventListener('scroll', update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(el);
    // A shown or removed column changes the table, not the scroller.
    if (el.firstElementChild) observer.observe(el.firstElementChild);
    return () => {
      el.removeEventListener('scroll', update);
      observer.disconnect();
    };
  }, [columns.length, rows.length]);
  // Page scroll leaves the table's own sticky header behind (it sticks only inside the
  // sideways scroller), so a synced copy floats under the 64 px app bar (QA 25 Oct, defect 10).
  const head = useRef<HTMLTableSectionElement>(null);
  const [float, setFloat] = useState<{ widths: number[]; left: number; width: number } | null>(null);
  useEffect(() => {
    const el = wide.current;
    const own = head.current;
    if (!el || !own) return;
    const BAR = 65;
    const update = () => {
      const box = el.getBoundingClientRect();
      if (box.top >= BAR || box.bottom < BAR + own.offsetHeight * 2) return setFloat((f) => (f ? null : f));
      const widths = [...own.querySelectorAll<HTMLElement>('th')].map((th) => th.getBoundingClientRect().width);
      setFloat((f) => (f && f.left === el.scrollLeft && f.width === el.clientWidth && f.widths.join() === widths.join() ? f : { widths, left: el.scrollLeft, width: el.clientWidth }));
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    el.addEventListener('scroll', update, { passive: true });
    return () => {
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
      el.removeEventListener('scroll', update);
    };
  }, [columns, rows.length, clipped]);
  /**
   * Scroll by whole columns: each stop puts a column's left edge at the sticky fund
   * column's right edge, so the Scroll button and arrow keys never stop mid-column.
   * "page" brings the column cut by the right edge to the left.
   */
  const step = (to: 'next' | 'previous' | 'page') => {
    const el = wide.current;
    if (!el) return;
    const ths = [...el.querySelectorAll<HTMLElement>('thead th')].filter((th) => th.offsetWidth > 0);
    const fund = ths[0]?.offsetWidth ?? 0;
    const starts = ths.slice(1).map((th) => th.offsetLeft - fund);
    const now = el.scrollLeft;
    const cut = ths.slice(1).find((th) => th.offsetLeft + th.offsetWidth > now + el.clientWidth + 1);
    const target =
      to === 'previous'
        ? [...starts].reverse().find((x) => x < now - 1)
        : to === 'page' && cut && cut.offsetLeft - fund > now + 1
          ? cut.offsetLeft - fund
          : starts.find((x) => x > now + 1);
    if (target !== undefined) el.scrollTo({ left: Math.max(0, target), behavior: 'smooth' });
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    step(e.key === 'ArrowRight' ? 'next' : 'previous');
  };
  /** The header row; the clone floats under the app bar once the table's own header scrolls away. */
  const headRow = (clone: boolean) => (
            <tr>
              <th scope="col" style={clone ? { width: float?.widths[0], transform: `translateX(${float?.left ?? 0}px)` } : undefined} className="sticky left-0 z-10 bg-mf-sunken px-4 py-3 text-left font-medium">
                Fund
              </th>
              <th scope="col" data-column={clone ? undefined : '__nav'} style={{ visibility: clipped.includes('__nav') ? 'hidden' : undefined, ...(clone && { width: float?.widths[1] }) }} className={cx('w-[96px] px-2 py-3 text-left font-medium', compact && 'max-2xl:hidden')}>
                3Y NAV
              </th>
              {columns.map((c, i) => {
                const active = primary?.field === c;
                return (
                  <th key={c} scope="col" data-column={clone ? undefined : c} style={{ visibility: clipped.includes(c) ? 'hidden' : undefined, ...(clone && { width: float?.widths[i + 2] }) }} aria-sort={active ? (primary.dir === 'asc' ? 'ascending' : 'descending') : 'none'} className="px-1.5 py-2.5 text-right align-bottom font-medium">
                    {/* Long labels wrap to two lines, so a column is as wide as its values, not its name. */}
                    <button type="button" tabIndex={clone ? -1 : undefined} onClick={() => onSort(c)} className={cx('ml-auto inline-flex max-w-[6.5rem] items-end gap-0.5 text-balance text-right leading-tight hover:text-mf-ink', active && 'text-mf-brand-strong')} title={fields.get(c)?.description}>
                      {columnLabel(c, fields)}
                      <I.chevronDown className={cx('h-3.5 w-3.5 shrink-0 transition-transform', !active && 'opacity-30', active && primary.dir === 'asc' && 'rotate-180')} />
                    </button>
                  </th>
                );
              })}
            </tr>
  );
  const lines = useSparklines(rows.map((r) => r.amfi_code));
  const line = (r: ScreenRow) => {
    const points = lines.data?.series[r.amfi_code];
    return <div className="w-[84px]">{points && points.length > 1 ? <Sparkline points={points} height={30} label={`${schemeName(r.name)}: month-end NAV over 3 years`} /> : <span className="block h-[30px]" aria-hidden="true" />}</div>;
  };
  return (
    <div className={cx('transition-opacity duration-150', stale && 'opacity-50')} aria-busy={stale}>
      {/* Wide screens */}
      {hidden > 8 && (
        <p className="mb-2 hidden items-center justify-end gap-2 text-xs text-mf-muted md:flex">
          More columns to the right
          <button type="button" onClick={() => step('page')} className="inline-flex items-center gap-1 rounded-full border border-mf-line-strong bg-mf-surface px-2.5 py-1 font-medium text-mf-brand-strong hover:border-mf-brand/50">
            Scroll <I.chevronRight className="h-3.5 w-3.5" />
          </button>
        </p>
      )}
      <div className="relative hidden md:block">
      {float && (
        <div aria-hidden="true" className="sticky top-[65px] z-20 h-0">
          <div className="overflow-hidden border-x border-b border-mf-line bg-mf-surface shadow-card" style={{ width: float.width + 2 }}>
            <table className="text-sm" style={{ tableLayout: 'fixed', width: float.widths.reduce((a, b) => a + b, 0), transform: `translateX(${-float.left}px)` }}>
              <thead className="bg-mf-sunken text-xs text-mf-muted">{headRow(true)}</thead>
            </table>
          </div>
        </div>
      )}
      <div ref={wide} onKeyDown={onKey} className="mf-scroll overflow-x-auto rounded-card border border-mf-line bg-mf-surface" role="region" aria-label="Screen results" tabIndex={0}>
        <table className="w-full text-sm">
          <thead ref={head} className="bg-mf-sunken text-xs text-mf-muted">
            {headRow(false)}
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.amfi_code} className="group border-t border-mf-line hover:bg-mf-sunken/50">
                <th scope="row" className="sticky left-0 z-[1] w-[232px] min-w-[208px] max-w-[232px] min-[1400px]:w-[288px] min-[1400px]:max-w-[288px] bg-mf-surface py-2 pl-4 pr-2 text-left font-normal shadow-[8px_0_12px_-10px_rgb(var(--mf-ink)/0.25)] transition-colors group-hover:bg-mf-sunken">
                  <div className="flex items-center gap-2.5">
                    <FundMark amc={String(r.values.amc ?? '')} size="sm" />
                    <div className="min-w-0 flex-1">
                      <Link to={`/mf/funds/${r.amfi_code}`} className="line-clamp-2 font-medium leading-snug text-mf-ink hover:text-mf-brand-strong" title={`${r.name} · AMFI ${r.amfi_code}`}>
                        {schemeName(r.name)}
                      </Link>
                      {/* Actions travel with the fund name, so they never cover a value. */}
                      <div className="mt-0.5 flex items-center gap-1">
                        <span className="min-w-0 flex-1 truncate text-xs text-mf-muted">{r.values.category && !columns.includes('category') ? categoryShort(String(r.values.category)) : `AMFI ${r.amfi_code}`}</span>
                        <WatchButton code={r.amfi_code} name={r.name} />
                        <CompareButton code={r.amfi_code} name={r.name} />
                      </div>
                    </div>
                  </div>
                </th>
                <td style={{ visibility: clipped.includes('__nav') ? 'hidden' : undefined }} className={cx('w-[96px] px-2 py-2', compact && 'max-2xl:hidden')}>{line(r)}</td>
                {columns.map((c) => (
                  <td key={c} style={{ visibility: clipped.includes(c) ? 'hidden' : undefined }} className="whitespace-nowrap px-1.5 py-3 text-right">
                    <Cell row={r} column={c} fields={fields} columns={columns} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>

      {/* Phones */}
      <ul className="space-y-3 md:hidden" aria-label="Screen results">
        {rows.map((r) => (
          <li key={r.amfi_code} className="rounded-card border border-mf-line bg-mf-surface p-4 shadow-card">
            <div className="flex items-start gap-3">
              {columns.includes('score') && <ScoreBadge score={r.values.score as number | null} />}
              <div className="min-w-0 flex-1">
                <Link to={`/mf/funds/${r.amfi_code}`} className="block font-medium leading-snug text-mf-ink">
                  {schemeName(r.name)}
                </Link>
                <p className="mt-0.5 text-xs text-mf-muted">{r.values.category ? categoryShort(String(r.values.category)) : `AMFI ${r.amfi_code}`}</p>
              </div>
              <div className="flex shrink-0 gap-1">
                <WatchButton code={r.amfi_code} name={r.name} />
                <CompareButton code={r.amfi_code} name={r.name} />
              </div>
            </div>
            <dl className="mt-3 grid grid-cols-3 gap-x-3 gap-y-2">
              {columns
                .filter((c) => c !== 'score' && c !== 'category')
                .slice(0, 6)
                .map((c) => (
                  <div key={c} className="min-w-0">
                    <dt className="truncate text-[11px] text-mf-muted">{columnLabel(c, fields)}</dt>
                    <dd className="text-sm font-medium">
                      <Cell row={r} column={c} fields={fields} columns={columns} />
                    </dd>
                  </div>
                ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}
