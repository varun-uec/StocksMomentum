/**
 * Screener (ui-ux doc 03 §02): express a thesis, inspect its consequences.
 * The view lives in the URL (`?preset=`, `?v=`, `?screen=` for a saved one), so
 * Back and reload restore it. Results page through the backend cursor; export
 * pages through every match at the same revision and can be cancelled.
 */
import { useInfiniteQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { MfApiError, mfApi, type Condition, type FieldDef, type ScreenRequest, type ScreenRow } from '../api';
import { I } from '../components/icons';
import { ConditionEditor } from '../components/screener/ConditionEditor';
import { FilterRail } from '../components/screener/FilterRail';
import { FormulaEditor } from '../components/screener/FormulaEditor';
import { ResultsTable, columnLabel } from '../components/screener/ResultsTable';
import { Badge, Button, Chip, EmptyState, ErrorState, Field, Loading, PageHeader, Segmented, Sheet, SnapshotNote, cx, inputClass, useTitle } from '../components/ui';
import { download, screenCsv } from '../csv';
import { categoryShort, enumLabel } from '../format';
import { useFields, usePresets } from '../queries';
import { decodeView, defaultView, describe, encodeView, filterOf, isCondition, presetView, type ScreenView } from '../view-spec';
import { isConflict, useRecordMutations, useRecords, type ResearchRecord } from '../workspace';
import { useDebounced } from '../use-debounced';

const PAGE = 50;
const EXPORT_PAGE = 500;
const MAX_COLUMNS = 12;

interface ScreenBody {
  view: ScreenView;
  preset?: string;
}


const short = (v: string) => (v.includes(' - ') ? categoryShort(v) : enumLabel(v));

function requestOf(view: ScreenView): Omit<ScreenRequest, 'page'> {
  return { filter: filterOf(view), sort: view.sort, columns: view.columns, formulas: view.formulas };
}

export default function Screen() {
  useTitle('Mutual fund screener');
  const [params, setParams] = useSearchParams();
  const fields = useFields();
  const presets = usePresets();
  const saved = useRecords<ScreenBody>('screen');
  const presetId = params.get('preset');
  const savedId = params.get('screen');
  const encoded = params.get('v');

  // Resolve the view from the URL.
  const decoded = useMemo(() => (encoded ? decodeView(encoded) : null), [encoded]);
  const savedRecord = savedId ? saved.data?.find((r) => r.id === savedId) : undefined;
  const preset = presetId ? presets.data?.presets.find((p) => p.id === presetId) : undefined;
  const badLink = !!encoded && !decoded;
  const view: ScreenView | null = decoded ?? savedRecord?.body.view ?? (preset ? presetView(preset) : null) ?? (presetId && !presets.data ? null : savedId && saved.isLoading ? null : defaultView());

  const setView = (next: ScreenView) => {
    const p = new URLSearchParams();
    if (savedId) p.set('screen', savedId);
    p.set('v', encodeView(next));
    setParams(p, { replace: true });
  };
  const choose = (next: URLSearchParams) => setParams(next);

  // Debounce the serialised request: a string compares by value, so an unchanged view never re-arms the timer.
  const requestKey = view ? JSON.stringify(requestOf(view)) : '';
  const debouncedKey = useDebounced(requestKey, 300);
  const request = useMemo<Omit<ScreenRequest, 'page'> | null>(() => (debouncedKey ? JSON.parse(debouncedKey) : null), [debouncedKey]);
  const results = useInfiniteQuery({
    queryKey: ['mf', 'screen-pages', request],
    queryFn: ({ pageParam, signal }) => mfApi.screen({ ...request!, page: { size: PAGE, ...(pageParam ? { after: pageParam } : {}) } }, signal),
    initialPageParam: '' as string,
    getNextPageParam: (last) => last.next ?? undefined,
    enabled: !!request && !!fields.data,
    staleTime: 5 * 60_000,
    placeholderData: (previous) => previous,
  });
  const first = results.data?.pages[0];
  const rows: ScreenRow[] = useMemo(() => results.data?.pages.flatMap((p) => p.rows) ?? [], [results.data]);
  const stale = results.isPlaceholderData || (results.isFetching && !results.isFetchingNextPage) || requestKey !== debouncedKey;

  const [editing, setEditing] = useState<{ field: FieldDef; index?: number } | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [draft, setDraft] = useState<ScreenView | null>(null);
  const [formulasOpen, setFormulasOpen] = useState(false);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);

  if (fields.isError) return <ErrorState error={fields.error} onRetry={() => fields.refetch()} />;
  if (!view || !fields.data) return <Loading label="Loading the screener" />;

  const byId = new Map(fields.byId);
  for (const name of Object.keys(view.formulas))
    byId.set(name, { id: name, label: name, group: 'Formulas', type: 'number', unit: null, description: view.formulas[name], available: true, coverage: { values: 0, missing: {} } });

  const saveCondition = (c: Condition) => {
    const conditions = [...view.conditions];
    if (editing?.index !== undefined) conditions[editing.index] = c;
    else conditions.push(c);
    const columns = view.columns.includes(c.field) || view.columns.length >= MAX_COLUMNS || !fields.byId.has(c.field) ? view.columns : [...view.columns, c.field];
    setView({ ...view, conditions, columns });
    setEditing(null);
  };

  const onSort = (field: string) => {
    const current = view.sort[0];
    const dir: 'asc' | 'desc' = current?.field === field && current.dir === 'desc' ? 'asc' : 'desc';
    setView({ ...view, sort: [{ field, dir }, ...view.sort.filter((s) => s.field !== field)].slice(0, 5) });
  };

  const excluded = (first?.excluded_missing ?? []).filter((e) => e.count > 0);
  const error = results.error;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mutual fund screener"
        lead={`Find funds that match your thesis, with ${fields.data.fields.length} analytics fields from the method v${fields.data.method_version} snapshot.`}
        actions={
          <>
            <div className="mr-2 text-right">
              <p className="text-[22px] font-semibold leading-none tabular" aria-live="polite">
                {first ? first.matched.toLocaleString('en-IN') : '—'} <span className="text-sm font-normal text-mf-muted">funds</span>
              </p>
              <p className="text-xs text-mf-muted">of {first?.total.toLocaleString('en-IN') ?? '—'} plan options</p>
            </div>
            <Button onClick={() => setSaveOpen(true)}>
              <I.bookmark className="h-4 w-4" />
              {savedRecord ? 'Save changes' : 'Save screen'}
            </Button>
            <ExportButton request={request} total={first?.matched} />
          </>
        }
      />

      {/* Presets and saved screens */}
      <div className="mf-scroll -mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="group" aria-label="Preset and saved screens">
        <Chip pressed={!presetId && !savedId && !encoded} onClick={() => choose(new URLSearchParams())}>
          Default
        </Chip>
        {presets.data?.presets.map((p) => (
          <Chip key={p.id} pressed={presetId === p.id && !encoded} onClick={() => choose(new URLSearchParams({ preset: p.id }))} className="shrink-0">
            <span title={p.purpose}>{p.name}</span>
          </Chip>
        ))}
        {saved.data?.map((r) => (
          <Chip key={r.id} pressed={savedId === r.id} onClick={() => choose(new URLSearchParams({ screen: r.id }))} className="shrink-0">
            <I.bookmark className="h-3.5 w-3.5" />
            {r.name}
          </Chip>
        ))}
      </div>
      {preset && !encoded && <p className="-mt-3 text-sm text-mf-muted">{preset.purpose}</p>}
      {badLink && (
        <div role="alert" className="rounded-[12px] border border-mf-warning/40 bg-mf-warning-soft p-3 text-sm">
          This link’s screen could not be read; it may be from another version. Showing the default screen.{' '}
          <button type="button" className="font-medium underline" onClick={() => choose(new URLSearchParams())}>
            Open the default screen
          </button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside aria-label="Filters" className="hidden lg:block">
          <div className="mf-scroll sticky top-24 max-h-[calc(100dvh-7rem)] overflow-y-auto pr-1">
            <FilterRail view={view} fields={fields.byId} onChange={setView} onPickField={(field) => setEditing({ field })} />
          </div>
        </aside>

        <div className="min-w-0 space-y-4">
          {/* Conditions */}
          <section aria-label="Conditions" className="rounded-card border border-mf-line bg-mf-surface p-4 shadow-card">
            <div className="flex flex-wrap items-center gap-2">
              <Segmented
                label="Match"
                value={view.mode}
                onChange={(mode) => setView({ ...view, mode })}
                options={[
                  { value: 'all', label: 'Match all' },
                  { value: 'any', label: 'Match any' },
                ]}
              />
              {view.conditions.map((c, i) => (
                <Chip
                  key={i}
                  onClick={isCondition(c) && byId.has(c.field) ? () => setEditing({ field: byId.get(c.field)!, index: i }) : undefined}
                  onRemove={() => setView({ ...view, conditions: view.conditions.filter((_, j) => j !== i) })}
                >
                  {describe(c, byId, short)}
                </Chip>
              ))}
              <Button size="sm" variant="ghost" className="lg:hidden" onClick={() => { setDraft(view); setFiltersOpen(true); }}>
                <I.screen className="h-4 w-4" />
                Filters ({view.conditions.length})
              </Button>
              {view.conditions.length > 0 && (
                <button type="button" onClick={() => setView({ ...view, conditions: [] })} className="ml-auto text-xs text-mf-muted hover:text-mf-ink">
                  Clear all
                </button>
              )}
            </div>
            {excluded.length > 0 && (
              <details className="mt-3 text-xs text-mf-muted">
                <summary className="cursor-pointer">
                  {excluded.reduce((n, e) => n + e.count, 0).toLocaleString('en-IN')} exclusions because a value is missing. A missing value never matches.
                </summary>
                <ul className="mt-2 space-y-1 pl-4">
                  {excluded.map((e) => (
                    <li key={e.path}>
                      {columnLabel(e.field, byId)}: {e.count.toLocaleString('en-IN')} ({Object.entries(e.reasons).map(([k, n]) => `${k.replace(/_/g, ' ')} ${n}`).join(', ')})
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>

          {/* Result controls */}
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 whitespace-nowrap text-sm text-mf-muted">
              Sort by
              <select className={cx(inputClass, 'h-9 w-auto')} value={view.sort[0]?.field ?? ''} onChange={(e) => setView({ ...view, sort: [{ field: e.target.value, dir: view.sort[0]?.dir ?? 'desc' }] })}>
                {[...new Set([...(view.sort[0] ? [view.sort[0].field] : []), ...view.columns])].map((c) => (
                  <option key={c} value={c}>
                    {columnLabel(c, byId)}
                  </option>
                ))}
              </select>
            </label>
            {view.sort[0] && (
              <Button size="sm" variant="ghost" onClick={() => onSort(view.sort[0].field)} title="Reverse the sort">
                {view.sort[0].dir === 'desc' ? 'High to low' : 'Low to high'}
              </Button>
            )}
            <div className="ml-auto flex gap-2">
              <Button size="sm" onClick={() => setColumnsOpen(true)}>
                <I.grid className="h-4 w-4" />
                Columns ({view.columns.length})
              </Button>
              <Button size="sm" onClick={() => setFormulasOpen(true)}>
                <I.plus className="h-4 w-4" />
                Formula{Object.keys(view.formulas).length ? `s (${Object.keys(view.formulas).length})` : ''}
              </Button>
            </div>
          </div>

          {error && (
            <div className="space-y-2">
              <ErrorState error={error} onRetry={() => results.refetch()} />
              {rows.length > 0 && <p className="text-xs text-mf-muted">The results below are not updated: they belong to the previous conditions.</p>}
            </div>
          )}
          {!first && !error ? (
            <Loading label="Running the screen" />
          ) : first && first.matched === 0 ? (
            <EmptyState title="No fund matches every condition">
              {first.relaxations.length ? (
                <div className="mt-2 space-y-2">
                  <p>Removing one condition would match:</p>
                  <ul className="flex flex-wrap justify-center gap-2">
                    {first.relaxations.map((r) => {
                      const index = Number(r.path.match(/\[(\d+)\]/)?.[1]);
                      const c = view.conditions[index];
                      return (
                        c && (
                          <li key={r.path}>
                            <Button size="sm" disabled={r.matched === 0} onClick={() => setView({ ...view, conditions: view.conditions.filter((_, j) => j !== index) })}>
                              Remove “{describe(c, byId, short)}” → {r.matched.toLocaleString('en-IN')}
                            </Button>
                          </li>
                        )
                      );
                    })}
                  </ul>
                </div>
              ) : (
                'Loosen a condition or match any instead of all.'
              )}
            </EmptyState>
          ) : (
            rows.length > 0 && (
              <>
                <ResultsTable rows={rows} columns={view.columns} fields={byId} sort={view.sort} onSort={onSort} stale={stale && !error} />
                <div className="flex flex-col items-center gap-2 py-2">
                  <p className="text-xs text-mf-muted">
                    Showing {rows.length.toLocaleString('en-IN')} of {first?.matched.toLocaleString('en-IN')}
                  </p>
                  {results.hasNextPage && (
                    <Button onClick={() => results.fetchNextPage()} disabled={results.isFetchingNextPage}>
                      {results.isFetchingNextPage ? 'Loading…' : `Load ${Math.min(PAGE, (first?.matched ?? 0) - rows.length)} more`}
                    </Button>
                  )}
                </div>
              </>
            )
          )}
          <SnapshotNote asOf={first?.as_of} revision={first?.data_revision} method={first?.method_version} extra=" · past NAV performance does not predict future returns" />
        </div>
      </div>

      <ConditionEditor field={editing?.field ?? null} initial={editing?.index !== undefined ? (view.conditions[editing.index] as Condition) : undefined} onSave={saveCondition} onClose={() => setEditing(null)} />
      <FormulaEditor
        open={formulasOpen}
        onClose={() => setFormulasOpen(false)}
        formulas={view.formulas}
        fields={fields.byId}
        onChange={(formulas) => {
          const added = Object.keys(formulas).filter((n) => !(n in view.formulas));
          const removed = Object.keys(view.formulas).filter((n) => !(n in formulas));
          setView({
            ...view,
            formulas,
            columns: [...view.columns.filter((c) => !removed.includes(c)), ...added].slice(0, MAX_COLUMNS),
            sort: view.sort.filter((s) => !removed.includes(s.field)),
            conditions: view.conditions.filter((c) => !(isCondition(c) && removed.includes(c.field))),
          });
        }}
      />
      <ColumnsSheet open={columnsOpen} onClose={() => setColumnsOpen(false)} view={view} fields={byId} onChange={setView} />
      <SaveSheet open={saveOpen} onClose={() => setSaveOpen(false)} view={view} record={savedRecord} presetId={presetId ?? undefined} onSaved={(id) => setParams(new URLSearchParams({ screen: id, v: encodeView(view) }), { replace: true })} />
      <Sheet
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Filters"
        footer={
          <>
            <Button onClick={() => setFiltersOpen(false)}>Cancel</Button>
            <Button
              variant="primary"
              onClick={() => {
                if (draft) setView(draft);
                setFiltersOpen(false);
              }}
            >
              Apply filters
            </Button>
          </>
        }
      >
        {draft && (
          <>
            <ul className="mb-4 flex flex-wrap gap-2">
              {draft.conditions.map((c, i) => (
                <li key={i}>
                  <Chip onRemove={() => setDraft({ ...draft, conditions: draft.conditions.filter((_, j) => j !== i) })}>{describe(c, byId, short)}</Chip>
                </li>
              ))}
            </ul>
            <FilterRail
              view={draft}
              fields={fields.byId}
              onChange={setDraft}
              onPickField={(field) => {
                setView(draft);
                setFiltersOpen(false);
                setEditing({ field });
              }}
            />
          </>
        )}
      </Sheet>
    </div>
  );
}

function ColumnsSheet({ open, onClose, view, fields, onChange }: { open: boolean; onClose: () => void; view: ScreenView; fields: Map<string, FieldDef>; onChange: (v: ScreenView) => void }) {
  const [query, setQuery] = useState('');
  const q = query.toLowerCase();
  const list = [...fields.values()].filter((f) => !q || f.label.toLowerCase().includes(q) || f.id.includes(q));
  const full = view.columns.length >= MAX_COLUMNS;
  return (
    <Sheet open={open} onClose={onClose} title="Columns">
      <p className="mb-3 text-sm text-mf-muted">
        {view.columns.length} of at most {MAX_COLUMNS} columns. Order follows your choices; the first sort key stays visible.
      </p>
      <input className={`${inputClass} mb-3`} placeholder="Find a field" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Find a field" />
      <ul className="space-y-0.5">
        {list.map((f) => {
          const on = view.columns.includes(f.id);
          return (
            <li key={f.id}>
              <label className="flex min-h-10 cursor-pointer items-center gap-3 rounded-[8px] px-2 text-sm hover:bg-mf-sunken">
                <input type="checkbox" checked={on} disabled={!on && full} onChange={() => onChange({ ...view, columns: on ? view.columns.filter((c) => c !== f.id) : [...view.columns, f.id] })} />
                <span className="flex-1">{f.label}</span>
                <span className="text-xs text-mf-muted">{f.group}</span>
              </label>
            </li>
          );
        })}
      </ul>
    </Sheet>
  );
}

function SaveSheet({
  open,
  onClose,
  view,
  record,
  presetId,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  view: ScreenView;
  record?: ResearchRecord<ScreenBody>;
  presetId?: string;
  onSaved: (id: string) => void;
}) {
  const [name, setName] = useState('');
  const { create, save } = useRecordMutations<ScreenBody>('screen');
  useEffect(() => {
    if (open) setName(record?.name ?? '');
  }, [open, record]);
  const error = create.error ?? save.error;
  const busy = create.isPending || save.isPending;
  const body = { view, ...(presetId ? { preset: presetId } : {}) };
  const done = (r: ResearchRecord<ScreenBody>) => {
    onSaved(r.id);
    onClose();
  };
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={record ? 'Save screen' : 'Save this screen'}
      footer={
        <>
          {record && (
            <Button disabled={busy || !name.trim()} onClick={() => create.mutate({ name: `${name.trim()} (copy)`, body }, { onSuccess: done })}>
              Save as new
            </Button>
          )}
          <Button
            variant="primary"
            disabled={busy || !name.trim()}
            onClick={() => (record ? save.mutate({ record, draft: { name: name.trim(), body } }, { onSuccess: done }) : create.mutate({ name: name.trim(), body }, { onSuccess: done }))}
          >
            {busy ? 'Saving…' : record ? 'Save changes' : 'Save'}
          </Button>
        </>
      }
    >
      <Field label="Name">
        <input className={inputClass} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} placeholder="Consistent flexi caps" autoFocus />
      </Field>
      <p className="mt-3 text-sm text-mf-muted">The screen keeps its conditions, sort, columns and formulas. It reruns on the latest snapshot when you open it.</p>
      {error && (
        <div className="mt-3">
          {isConflict(error) ? (
            <p role="alert" className="rounded-[10px] bg-mf-warning-soft p-3 text-sm text-mf-warning">
              Another window saved this screen first. Your edits are still here: use “Save as new”, or reopen the screen to see the other version.
            </p>
          ) : (
            <ErrorState error={error} compact />
          )}
        </div>
      )}
      <Badge tone="neutral" className="mt-4">
        Saved on this machine’s Wickstreet server
      </Badge>
    </Sheet>
  );
}

function ExportButton({ request, total }: { request: Omit<ScreenRequest, 'page'> | null; total?: number }) {
  const [progress, setProgress] = useState<{ loaded: number; controller: AbortController } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const run = async () => {
    if (!request) return;
    const controller = new AbortController();
    setError(null);
    setProgress({ loaded: 0, controller });
    try {
      const rows: ScreenRow[] = [];
      let after: string | undefined;
      let first: Awaited<ReturnType<typeof mfApi.screen>> | undefined;
      do {
        const page = await mfApi.screen({ ...request, page: { size: EXPORT_PAGE, ...(after ? { after } : {}) }, ...(first ? { data_revision: first.data_revision } : {}) }, controller.signal);
        first ??= page;
        rows.push(...page.rows);
        after = page.next ?? undefined;
        setProgress({ loaded: rows.length, controller });
      } while (after);
      download(`wickstreet-screen-${first.as_of}-r${first.data_revision}.csv`, screenCsv(request.columns, rows, { ...first, filter: request.filter, sort: request.sort, formulas: request.formulas }));
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) setError(e);
    } finally {
      setProgress(null);
    }
  };
  if (progress)
    return (
      <Button onClick={() => progress.controller.abort()} aria-live="polite">
        Exporting {progress.loaded.toLocaleString('en-IN')}/{total?.toLocaleString('en-IN') ?? '…'} · Cancel
      </Button>
    );
  return (
    <>
      <Button onClick={run} disabled={!request || !total}>
        <I.download className="h-4 w-4" />
        Export CSV
      </Button>
      {error instanceof MfApiError && <span role="alert" className="text-xs text-mf-loss">Export failed: {error.message}</span>}
    </>
  );
}
