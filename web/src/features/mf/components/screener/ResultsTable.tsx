/**
 * Screen results: a sortable table with a sticky header and fund column on wide
 * screens, cards with the same columns and order on phones. A missing value
 * shows its reason, never a zero.
 */
import { Link } from 'react-router';
import type { FieldDef, ScreenRow, SortKey } from '../../api';
import { categoryShort, formatField, missingLabel, schemeName, tone } from '../../format';
import { CompareButton, WatchButton } from '../CompareTray';
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
  return (
    <div className={cx('transition-opacity duration-150', stale && 'opacity-50')} aria-busy={stale}>
      {/* Wide screens */}
      <div className="mf-scroll hidden overflow-x-auto rounded-card border border-mf-line bg-mf-surface md:block" role="region" aria-label="Screen results" tabIndex={0}>
        <table className="w-full min-w-[760px] text-sm">
          <thead className="sticky top-0 z-10 bg-mf-sunken text-xs text-mf-muted">
            <tr>
              <th scope="col" className="sticky left-0 z-10 bg-mf-sunken px-4 py-3 text-left font-medium">
                Fund
              </th>
              {columns.map((c) => {
                const active = primary?.field === c;
                return (
                  <th key={c} scope="col" aria-sort={active ? (primary.dir === 'asc' ? 'ascending' : 'descending') : 'none'} className="px-2.5 py-3 text-right font-medium">
                    <button type="button" onClick={() => onSort(c)} className={cx('inline-flex items-center gap-1 whitespace-nowrap text-right hover:text-mf-ink', active && 'text-mf-brand-strong')} title={fields.get(c)?.description}>
                      {columnLabel(c, fields)}
                      <I.chevronDown className={cx('h-3.5 w-3.5 transition-transform', !active && 'opacity-30', active && primary.dir === 'asc' && 'rotate-180')} />
                    </button>
                  </th>
                );
              })}
              <th scope="col" className="px-3 py-3 text-right font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.amfi_code} className="group border-t border-mf-line hover:bg-mf-sunken/50">
                <th scope="row" className="sticky left-0 w-[240px] max-w-[240px] bg-mf-surface px-4 py-3 text-left font-normal group-hover:bg-mf-sunken">
                  <Link to={`/mf/funds/${r.amfi_code}`} className="block truncate font-medium text-mf-ink hover:text-mf-brand-strong">
                    {schemeName(r.name)}
                  </Link>
                  <span className="text-xs text-mf-muted">
                    {r.name.match(/(Direct|Regular)/i)?.[0] ?? ''} · AMFI {r.amfi_code}
                  </span>
                </th>
                {columns.map((c) => (
                  <td key={c} className="whitespace-nowrap px-2.5 py-3 text-right">
                    <Cell row={r} column={c} fields={fields} />
                  </td>
                ))}
                <td className="px-3 py-2">
                  <div className="flex justify-end gap-1">
                    <WatchButton code={r.amfi_code} name={r.name} />
                    <CompareButton code={r.amfi_code} name={r.name} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
            <div className="mt-3 flex gap-2">
              <WatchButton code={r.amfi_code} name={r.name} label />
              <CompareButton code={r.amfi_code} name={r.name} label />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
