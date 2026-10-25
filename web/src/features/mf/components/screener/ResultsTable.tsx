/**
 * Screen results: a sortable table with a sticky header and fund column on wide
 * screens, cards with the same columns and order on phones. A missing value
 * shows its reason, never a zero.
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import type { FieldDef, ScreenRow, SortKey } from '../../api';
import { categoryShort, formatField, missingLabel, schemeName, tone } from '../../format';
import { useSparklines } from '../../queries';
import { Sparkline } from '../charts';
import { CompareButton, WatchButton } from '../CompareTray';
import { FundMark } from '../FundMark';
import { I } from '../icons';
import { ScoreBadge } from '../ScoreBadge';
import { cx } from '../ui';

const SIGNED = new Set(['fraction']);

function Cell({ row, column, fields }: { row: ScreenRow; column: string; fields: Map<string, FieldDef> }) {
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
  const text = field ? formatField(field, value, fields) : typeof value === 'number' ? value.toLocaleString('en-IN', { maximumFractionDigits: 4 }) : String(value);
  const t = field && SIGNED.has(field.unit ?? '') ? tone(value) : 'flat';
  return <span className={cx('tabular', t === 'loss' && 'text-mf-loss')}>{text}</span>;
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
  useEffect(() => {
    const el = wide.current;
    if (!el) return;
    const update = () => setHidden(Math.max(0, el.scrollWidth - el.clientWidth - el.scrollLeft));
    update();
    el.addEventListener('scroll', update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => {
      el.removeEventListener('scroll', update);
      observer.disconnect();
    };
  }, [columns.length, rows.length]);
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
          <button type="button" onClick={() => wide.current?.scrollBy({ left: 320, behavior: 'smooth' })} className="inline-flex items-center gap-1 rounded-full border border-mf-line-strong bg-mf-surface px-2.5 py-1 font-medium text-mf-brand-strong hover:border-mf-brand/50">
            Scroll <I.chevronRight className="h-3.5 w-3.5" />
          </button>
        </p>
      )}
      <div className="relative hidden md:block">
      <div ref={wide} className="mf-scroll overflow-x-auto rounded-card border border-mf-line bg-mf-surface" role="region" aria-label="Screen results" tabIndex={0}>
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-mf-sunken text-xs text-mf-muted">
            <tr>
              <th scope="col" className="sticky left-0 z-10 bg-mf-sunken px-4 py-3 text-left font-medium">
                Fund
              </th>
              <th scope="col" className={cx('w-[96px] px-2 py-3 text-left font-medium', compact && 'max-2xl:hidden')}>
                3Y NAV
              </th>
              {columns.map((c) => {
                const active = primary?.field === c;
                return (
                  <th key={c} scope="col" aria-sort={active ? (primary.dir === 'asc' ? 'ascending' : 'descending') : 'none'} className="px-1.5 py-2.5 text-right align-bottom font-medium">
                    {/* Long labels wrap to two lines, so a column is as wide as its values, not its name. */}
                    <button type="button" onClick={() => onSort(c)} className={cx('ml-auto inline-flex max-w-[6.5rem] items-end gap-0.5 text-balance text-right leading-tight hover:text-mf-ink', active && 'text-mf-brand-strong')} title={fields.get(c)?.description}>
                      {columnLabel(c, fields)}
                      <I.chevronDown className={cx('h-3.5 w-3.5 shrink-0 transition-transform', !active && 'opacity-30', active && primary.dir === 'asc' && 'rotate-180')} />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.amfi_code} className="group border-t border-mf-line hover:bg-mf-sunken/50">
                <th scope="row" className="sticky left-0 z-[1] w-[232px] min-w-[208px] max-w-[232px] bg-mf-surface py-2 pl-4 pr-2 text-left font-normal shadow-[8px_0_12px_-10px_rgb(var(--mf-ink)/0.25)] transition-colors group-hover:bg-mf-sunken">
                  <div className="flex items-center gap-2.5">
                    <FundMark amc={String(r.values.amc ?? '')} size="sm" />
                    <div className="min-w-0 flex-1">
                      <Link to={`/mf/funds/${r.amfi_code}`} className="block truncate font-medium leading-snug text-mf-ink hover:text-mf-brand-strong" title={`${r.name} · AMFI ${r.amfi_code}`}>
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
                <td className={cx('w-[96px] px-2 py-2', compact && 'max-2xl:hidden')}>{line(r)}</td>
                {columns.map((c) => (
                  <td key={c} className="whitespace-nowrap px-1.5 py-3 text-right">
                    <Cell row={r} column={c} fields={fields} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* A cut-off column fades out at the edge, so it reads as "more to the right", not as a clipped number. */}
      {hidden > 8 && <div className="pointer-events-none absolute inset-y-px right-px w-16 rounded-r-card bg-gradient-to-l from-mf-surface via-mf-surface/80 to-transparent" aria-hidden="true" />}
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
                      <Cell row={r} column={c} fields={fields} />
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
