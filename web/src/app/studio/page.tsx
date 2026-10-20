/**
 * Strategy Studio (FR-25, ADR-014): state a hypothesis, change registered rules
 * within their bounds, and judge the result in three labelled classes.
 *
 * The page never shows a performance figure outside a labelled result, and it
 * never calls a result "validated".
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createFamily,
  executeScreening,
  getRun,
  getEvaluations,
  getFamilies,
  getRuleRegistry,
  getStrategyDetail,
  listStrategies,
  retryEvaluation,
  saveStudioStrategy,
  submitEvaluation,
} from '@/lib/api-client';
import { Card, EmptyState, LoadingSpinner, PageHeader } from '@/components/shared/Card';
import { focusRing } from '@/lib/theme';
import { useStrategy } from '@/app/strategy-context';
import {
  RESULT_CLASSES,
  editable,
  holdoutSpent,
  labelOf,
  lineage,
  problems,
  rulesFor,
  scratchConfig,
  setEngine,
  setRule,
  toggleRule,
  type Evaluation,
  type Family,
  type ResultClass,
  type RuleRegistry,
  type StudioConfig,
  type StudioStrategy,
} from '@/lib/studio';

const field = `rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-1 text-sm ${focusRing}`;
const button = `rounded-md px-3 py-1.5 text-sm font-medium border transition-colors disabled:opacity-50 ${focusRing}`;
const primary = `${button} bg-indigo-600 text-white border-indigo-600 hover:bg-indigo-700`;
const secondary = `${button} bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 hover:border-indigo-400`;

/** The `detail` of an RFC-7807 error, or the message itself. */
function problemText(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  const body = message.replace(/^API \d+: /, '');
  try {
    return (JSON.parse(body) as { detail?: string }).detail ?? body;
  } catch {
    return body;
  }
}

export default function StudioPage() {
  const queryClient = useQueryClient();
  const { strategyHash } = useStrategy();
  const registry = useQuery({ queryKey: ['studio-rules'], queryFn: getRuleRegistry, staleTime: Infinity });
  const families = useQuery({ queryKey: ['studio-families'], queryFn: getFamilies });
  const [familyId, setFamilyId] = useState<number | null>(null);
  const [searchParams] = useSearchParams();
  const requestedReturn = searchParams.get('from');
  const returnPath = requestedReturn?.startsWith('/') && !requestedReturn.startsWith('//') ? requestedReturn : undefined;
  const family = families.data?.find((f) => f.id === familyId) ?? null;
  const mainRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (familyId !== null || !strategyHash || !families.data) return;
    const selected = families.data.find((item) => item.members.some((member) => member.config_hash === strategyHash));
    if (selected) setFamilyId(selected.id);
  }, [families.data, familyId, strategyHash]);
  // On a narrow screen the family view sits below the list and the form; bring it into view.
  const choose = (id: number) => {
    setFamilyId(id);
    if (!window.matchMedia('(min-width: 1024px)').matches) {
      requestAnimationFrame(() => mainRef.current?.scrollIntoView({ block: 'start' }));
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader
        title="Strategy Studio"
        subtitle="State a hypothesis, change registered rules within their bounds, and judge the change."
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
        <ol aria-label="Research workflow" className="grid sm:grid-cols-3 gap-3 text-xs text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 pb-4">
          <li><span className="font-semibold text-indigo-700 dark:text-indigo-300">01 · Hypothesis</span><p className="mt-1">Group related configurations in a family.</p></li>
          <li><span className="font-semibold text-indigo-700 dark:text-indigo-300">02 · Evidence</span><p className="mt-1">Inspect screening and in-sample research separately.</p></li>
          <li><span className="font-semibold text-indigo-700 dark:text-indigo-300">03 · Hold-out</span><p className="mt-1">Use the family’s bounded out-of-sample evaluation deliberately.</p></li>
        </ol>
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 grid gap-6 lg:grid-cols-[18rem_1fr]">
        <aside className="space-y-4">
          <Card title="Families">
            {families.isError && <p role="alert" className="text-xs text-rose-700 dark:text-rose-300">Could not load families. <button type="button" className="underline" onClick={() => families.refetch()}>Retry</button></p>}
            {families.isLoading && <LoadingSpinner text="Loading families…" />}
            {families.data?.length === 0 && <EmptyState message="No families yet." />}
            <ul className="space-y-1">
              {families.data?.map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() => choose(f.id)}
                    aria-current={f.id === familyId}
                    className={`w-full text-left rounded-md px-2 py-1.5 text-sm ${focusRing} ${
                      f.id === familyId ? 'bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300' : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    <span className="block line-clamp-2">{f.hypothesis}</span>
                    <span className="text-xs text-slate-500">{f.members.length} configs · from {f.root === 'scratch' ? 'scratch' : 'a strategy file'}</span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <NewFamily
            onCreated={(f) => {
              void queryClient.invalidateQueries({ queryKey: ['studio-families'] });
              choose(f.id);
            }}
            registry={registry.data}
          />
        </aside>
        <div ref={mainRef} className="min-w-0 space-y-6 scroll-mt-16">
          {!family && <EmptyState message="Choose a family, or state a new hypothesis." />}
          {family && registry.data && <FamilyView key={family.id} family={family} registry={registry.data} returnPath={returnPath} />}
        </div>
      </div>
    </div>
  );
}

function NewFamily({ registry, onCreated }: { registry?: RuleRegistry; onCreated: (f: Family) => void }) {
  const strategies = useQuery({ queryKey: ['strategies'], queryFn: () => listStrategies() });
  const [hypothesis, setHypothesis] = useState('');
  const [start, setStart] = useState('');
  const [name, setName] = useState('');
  const create = useMutation({
    mutationFn: async () => {
      if (start === 'scratch') {
        if (!registry) throw new Error('The rule registry has not loaded.');
        return createFamily({ hypothesis, config: scratchConfig(registry, name), parent_config_hash: null });
      }
      const detail = await getStrategyDetail(start);
      return createFamily({
        hypothesis,
        config: editable(detail.config as Record<string, unknown>, name),
        parent_config_hash: detail.config_hash,
      });
    },
    onSuccess: (f) => {
      setHypothesis('');
      setName('');
      onCreated(f);
    },
  });
  return (
    <Card title="New family" subtitle="One hypothesis, one root. Neither can change later.">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <label className="block text-xs font-medium">
          Hypothesis, in one sentence
          <textarea
            className={`${field} mt-1 w-full`}
            rows={3}
            value={hypothesis}
            onChange={(e) => setHypothesis(e.target.value)}
            placeholder="A tighter liquidity gate improves 120d returns of the qualified set."
          />
        </label>
        <label className="block text-xs font-medium">
          Start from
          <select className={`${field} mt-1 w-full`} value={start} onChange={(e) => setStart(e.target.value)}>
            <option value="">Choose…</option>
            {strategies.data?.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
            <option value="scratch">From scratch (nothing enabled)</option>
          </select>
        </label>
        <label className="block text-xs font-medium">
          Name of the first config
          <input className={`${field} mt-1 w-full`} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <button type="submit" className={primary} disabled={create.isPending || hypothesis.trim().length < 10 || !start || !name.trim()}>
          {create.isPending ? 'Creating…' : 'Create family'}
        </button>
        {create.isError && <p role="alert" className="text-xs text-red-600">{problemText(create.error)}</p>}
      </form>
    </Card>
  );
}

function FamilyView({ family, registry, returnPath }: { family: Family; registry: RuleRegistry; returnPath?: string }) {
  const queryClient = useQueryClient();
  const tree = useMemo(() => lineage(family), [family]);
  const [selected, setSelected] = useState(tree[tree.length - 1]?.member.config_hash ?? '');
  const member = family.members.find((m) => m.config_hash === selected);
  const [draft, setDraft] = useState<StudioConfig | null>(null);
  useEffect(() => setDraft(member ? editable(member.config) : null), [member]);
  const errors = draft ? problems(draft, registry) : {};
  const save = useMutation({
    mutationFn: () => saveStudioStrategy(family.id, { config: draft!, parent_config_hash: selected }),
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ['studio-families'] });
      setSelected(saved.config_hash);
    },
  });

  return (
    <>
      <Card title={family.hypothesis} subtitle={`Family ${family.id} · root ${family.root_config_hash.slice(0, 12)} (${family.root === 'scratch' ? 'from scratch' : 'strategy file'})`}>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Lineage</h4>
        <ul className="space-y-1" aria-label="Lineage">
          {tree.map(({ member: m, depth }) => (
            <li key={m.config_hash} style={{ paddingLeft: `${depth * 1.25}rem` }}>
              <button
                type="button"
                onClick={() => setSelected(m.config_hash)}
                aria-current={m.config_hash === selected}
                className={`rounded px-2 py-0.5 text-sm font-mono ${focusRing} ${m.config_hash === selected ? 'bg-indigo-100 dark:bg-indigo-900' : 'hover:bg-slate-100 dark:hover:bg-slate-800'}`}
              >
                {depth > 0 && '└ '}
                {m.name} v{m.version} · {m.config_hash.slice(0, 12)}
              </button>
            </li>
          ))}
        </ul>
      </Card>

      {member && <Evaluations family={family} configHash={member.config_hash} />}
      {member && <ScreenSavedConfig key={member.config_hash} member={member} returnPath={returnPath} />}

      {draft && (
        <Card title={`Change ${member?.name} v${member?.version}`} subtitle="Saving creates a new version in this family. Stored versions never change.">
          <ConfigForm config={draft} registry={registry} errors={errors} onChange={setDraft} />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <label className="text-xs font-medium">
              Name{' '}
              <input className={field} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </label>
            <button type="button" className={primary} disabled={save.isPending || Object.keys(errors).length > 0} onClick={() => save.mutate()}>
              {save.isPending ? 'Saving…' : 'Save as new version'}
            </button>
            {errors.name && <span className="text-xs text-red-600">{errors.name}</span>}
            {save.isError && <span role="alert" className="text-xs text-red-600">{problemText(save.error)}</span>}
          </div>
        </Card>
      )}
    </>
  );
}

function ScreenSavedConfig({ member, returnPath }: { member: StudioStrategy; returnPath?: string }) {
  const queryClient = useQueryClient();
  const { setStrategyName } = useStrategy();
  const [runId, setRunId] = useState<number | null>(null);
  const start = useMutation({
    mutationFn: () => executeScreening(member.name, false, member.config_hash),
    onSuccess: async (run) => {
      setRunId(run.id);
      setStrategyName(member.name, member.config_hash);
      await queryClient.invalidateQueries({ queryKey: ['strategies', 'workspace'] });
      await queryClient.invalidateQueries({ queryKey: ['strategies', 'workspace', 'with-runs'] });
      await queryClient.invalidateQueries({ queryKey: ['latest-run', member.name, member.config_hash] });
    },
  });
  const run = useQuery({
    queryKey: ['studio-workstation-run', member.config_hash, runId],
    queryFn: () => getRun(runId!),
    enabled: runId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'PENDING' || status === 'RUNNING' ? 1500 : false;
    },
  });
  const running = start.isPending || run.data?.status === 'PENDING' || run.data?.status === 'RUNNING';

  useEffect(() => {
    if (run.data?.status === 'COMPLETED') {
      void queryClient.invalidateQueries({ queryKey: ['latest-run', member.name, member.config_hash] });
    }
  }, [member.config_hash, member.name, queryClient, run.data?.status]);

  return (
    <Card title="Workstation screening" subtitle={`Saved strategy ${member.name} v${member.version} · config ${member.config_hash.slice(0, 12)}`}>
      <p className="text-xs text-slate-600 dark:text-slate-300">
        Run this exact configuration on stored EOD data to create rankings for the screener, chart Assessment and watchlist. The Studio Screening Result remains a separate point-in-time research snapshot; saved screens contain only screener filters and columns.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" className={primary} disabled={running} onClick={() => start.mutate()}>
          {running ? 'Screening…' : run.data?.status === 'FAILED' ? 'Retry screening' : 'Run this strategy'}
        </button>
        {run.data?.status === 'PENDING' && <span role="status" className="text-xs text-slate-500">Queued</span>}
        {run.data?.status === 'RUNNING' && <span role="status" className="text-xs text-slate-500">Evaluating stored bars…</span>}
        {run.data?.status === 'FAILED' && <span role="alert" className="text-xs text-rose-700 dark:text-rose-300">{run.data.error ?? 'Screening failed.'}</span>}
        {start.isError && <span role="alert" className="text-xs text-rose-700 dark:text-rose-300">{problemText(start.error)}</span>}
        {run.data?.status === 'COMPLETED' && (
          <Link className={`${secondary} inline-flex items-center`} to={`/?run=${run.data.id}`}>View run #{run.data.id} rankings</Link>
        )}
        {returnPath && <Link className={`text-xs text-[var(--ws-accent)] hover:underline ${focusRing}`} to={returnPath}>Return to chart</Link>}
      </div>
    </Card>
  );
}

function ConfigForm({
  config,
  registry,
  errors,
  onChange,
}: {
  config: StudioConfig;
  registry: RuleRegistry;
  errors: Record<string, string>;
  onChange: (c: StudioConfig) => void;
}) {
  return (
    <div className="space-y-4">
      {registry.engines.map((engineId) => {
        const engine = config.engines.find((e) => e.id === engineId) ?? { id: engineId, enabled: false, weight: '1', gate: false, rules: [] };
        const schemas = rulesFor(registry, engineId);
        return (
          <fieldset key={engineId} className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
            <legend className="px-1 text-sm font-semibold">{engineId}</legend>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <label className="inline-flex items-center gap-1.5">
                <input type="checkbox" checked={engine.enabled} onChange={(e) => onChange(setEngine(config, engineId, { enabled: e.target.checked }))} />
                Enabled
              </label>
              <label className="inline-flex items-center gap-1.5">
                <input type="checkbox" checked={engine.gate} onChange={(e) => onChange(setEngine(config, engineId, { gate: e.target.checked }))} />
                Gate (every rule must pass)
              </label>
              <label className="inline-flex items-center gap-1.5">
                Weight
                <input
                  className={`${field} w-20`}
                  value={engine.weight}
                  aria-invalid={!!errors[engineId]}
                  onChange={(e) => onChange(setEngine(config, engineId, { weight: e.target.value }))}
                />
              </label>
              {errors[engineId] && <span className="text-xs text-red-600">{errors[engineId]}</span>}
            </div>
            {registry.engines_without_rules.includes(engineId) && (
              <p className="mt-2 text-xs text-slate-500">This engine has no configurable rules.</p>
            )}
            <div className="mt-2 space-y-2">
              {schemas.map((schema) => {
                const rule = engine.rules.find((r) => r.id === schema.rule_id);
                const key = `${engineId}.${schema.rule_id}`;
                return (
                  <div key={schema.rule_id} role="group" aria-label={schema.rule_id} className="rounded-md bg-slate-50 dark:bg-slate-900/50 p-2">
                    <div className="flex flex-wrap items-center gap-3 text-sm">
                      <label className="inline-flex items-center gap-1.5 font-mono">
                        <input type="checkbox" checked={!!rule} onChange={(e) => onChange(toggleRule(config, schema, e.target.checked))} />
                        {schema.rule_id}
                      </label>
                      <span className="text-xs text-slate-500">{schema.meaning}</span>
                    </div>
                    {schema.note && <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">{schema.note}</p>}
                    {rule && (
                      <div className="mt-2 flex flex-wrap items-start gap-4 text-xs">
                        <label className="inline-flex items-center gap-1.5">
                          <input type="checkbox" checked={rule.gate} onChange={(e) => onChange(setRule(config, engineId, schema.rule_id, { gate: e.target.checked }))} />
                          Gate
                        </label>
                        <label className="inline-flex items-center gap-1.5">
                          Weight
                          <input
                            className={`${field} w-16`}
                            value={rule.weight}
                            aria-invalid={!!errors[key]}
                            onChange={(e) => onChange(setRule(config, engineId, schema.rule_id, { weight: e.target.value }))}
                          />
                        </label>
                        {schema.params.map((spec) => {
                          const error = errors[`${key}.${spec.name}`];
                          const value = String(rule.params[spec.name] ?? spec.default);
                          return (
                            <label key={spec.name} className="inline-flex flex-col gap-0.5" title={spec.meaning}>
                              <span>
                                {spec.name} <span className="text-slate-500">({spec.kind === 'choice' ? spec.choices.join(' / ') : `${spec.minimum}–${spec.maximum}`} {spec.unit})</span>
                              </span>
                              {spec.kind === 'choice' ? (
                                <select className={field} value={value} onChange={(e) => onChange(setRule(config, engineId, schema.rule_id, { param: [spec.name, e.target.value] }))}>
                                  {spec.choices.map((c) => (
                                    <option key={c} value={c}>
                                      {c}
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  className={`${field} w-24`}
                                  inputMode="decimal"
                                  value={value}
                                  aria-invalid={!!error}
                                  onChange={(e) => onChange(setRule(config, engineId, schema.rule_id, { param: [spec.name, e.target.value] }))}
                                />
                              )}
                              {error && <span className="text-red-600">{error}</span>}
                            </label>
                          );
                        })}
                        {errors[key] && <span className="text-red-600">{errors[key]}</span>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </fieldset>
        );
      })}
    </div>
  );
}

function Evaluations({ family, configHash }: { family: Family; configHash: string }) {
  const queryClient = useQueryClient();
  const key = ['studio-evaluations', family.id];
  const evaluations = useQuery({
    queryKey: key,
    queryFn: () => getEvaluations(family.id),
    refetchInterval: (q) => (q.state.data?.some((e) => e.status === 'queued' || e.status === 'running') ? 2000 : false),
  });
  const [confirming, setConfirming] = useState(false);
  const submit = useMutation({
    mutationFn: (resultClass: ResultClass) => submitEvaluation(family.id, { config_hash: configHash, result_class: resultClass }),
    onSuccess: () => {
      setConfirming(false);
      void queryClient.invalidateQueries({ queryKey: key });
    },
  });
  const retry = useMutation({ mutationFn: retryEvaluation, onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }) });
  // ponytail: any Out-of-Sample row counts as spent; a new 36-month window opens years later.
  const spent = holdoutSpent(evaluations.data ?? []);
  const list = evaluations.data ?? [];

  return (
    <Card title="Judge this config" subtitle={`Config ${configHash.slice(0, 12)}`}>
      <div className="flex flex-wrap items-center gap-2">
        {RESULT_CLASSES.filter((c) => c.id !== 'out_of_sample').map((c) => (
          <button key={c.id} type="button" className={secondary} disabled={submit.isPending} onClick={() => submit.mutate(c.id)}>
            Run {c.label}
          </button>
        ))}
        <button type="button" className={secondary} disabled={submit.isPending || spent} onClick={() => setConfirming(true)}>
          Run {labelOf('out_of_sample')}
        </button>
      </div>
      {spent && <p className="mt-2 text-xs text-slate-500">This family has used its one Out-of-Sample Evaluation on the current window.</p>}
      {confirming && (
        <div role="alertdialog" aria-label="Spend the hold-out" className="mt-3 rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/40 p-3 text-sm space-y-2">
          <p>
            A family gets one Out-of-Sample Evaluation per 36-month window. Running it now spends the hold-out for every config in this family,
            whatever the result.
          </p>
          <div className="flex gap-2">
            <button type="button" className={primary} onClick={() => submit.mutate('out_of_sample')}>
              Spend the hold-out on {configHash.slice(0, 12)}
            </button>
            <button type="button" className={secondary} onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {submit.isError && <p role="alert" className="mt-2 text-xs text-red-600">{problemText(submit.error)}</p>}
      <div className="mt-4 space-y-4">
        {list.length === 0 && <EmptyState message="No evaluations in this family yet." />}
        {list.map((e) => (
          <EvaluationView key={e.id} evaluation={e} onRetry={() => retry.mutate(e.id)} />
        ))}
      </div>
    </Card>
  );
}

const pct = (v: unknown) => (typeof v === 'number' ? `${(v * 100).toFixed(2)}%` : '—');
const num = (v: unknown, digits = 4) => (typeof v === 'number' ? v.toFixed(digits) : '—');

function EvaluationView({ evaluation: e, onRetry }: { evaluation: Evaluation; onRetry: () => void }) {
  const r = (e.result ?? {}) as Record<string, any>;
  return (
    <section aria-label={`${e.label} ${e.id}`} className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold">{e.label}</h4>
        <span className="text-xs text-slate-500 font-mono">
          #{e.id} · {e.config_hash.slice(0, 12)} · {e.window_start === e.window_end ? e.window_end : `${e.window_start} → ${e.window_end}`} · data {e.data_version}
        </span>
      </header>
      {(e.status === 'queued' || e.status === 'running') && (
        <div className="mt-2">
          <progress className="w-full" max={Math.max(e.progress_total, 1)} value={e.progress_done} aria-label="Progress" />
          <p className="text-xs text-slate-500">
            {e.status === 'queued' ? 'Queued' : `Session ${e.progress_done} of ${e.progress_total}`}
          </p>
        </div>
      )}
      {e.status === 'failed' && (
        <p className="mt-2 text-xs text-red-600">
          {e.error}{' '}
          <button type="button" className={secondary} onClick={onRetry}>
            Retry
          </button>
        </p>
      )}
      {e.status === 'completed' && e.result_class === 'screening' && <ScreeningView result={r} />}
      {e.status === 'completed' && e.result_class !== 'screening' && <HistoryView result={r} outOfSample={e.result_class === 'out_of_sample'} />}
    </section>
  );
}

function ScreeningView({ result }: { result: Record<string, any> }) {
  const selection = (result.selection ?? []) as { rank: number; symbol: string; momentum_score: string; rules: { rule_id: string; passed: boolean; explanation: string }[] }[];
  return (
    <div className="mt-2 text-sm">
      <p className="text-xs text-slate-500">
        Session {result.session}: {result.qualified} of {result.evaluated} names passed the gates. No performance figure belongs to a Screening Result.
      </p>
      <ol className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">
        {selection.map((s) => (
          <li key={s.symbol} className="py-1">
            <details>
              <summary className="cursor-pointer">
                <span className="font-mono w-8 inline-block">{s.rank}</span>
                <Link className="text-indigo-600 hover:underline" to={`/chart/${s.symbol}`}>
                  {s.symbol}
                </Link>{' '}
                <span className="text-xs text-slate-500">momentum {Number(s.momentum_score).toFixed(1)}</span>
              </summary>
              <ul className="mt-1 ml-8 text-xs space-y-0.5">
                {s.rules.map((rule) => (
                  <li key={rule.rule_id} className={rule.passed ? 'text-emerald-700 dark:text-emerald-400' : 'text-slate-500'}>
                    {rule.passed ? '✓' : '✗'} {rule.explanation}
                  </li>
                ))}
              </ul>
            </details>
          </li>
        ))}
      </ol>
    </div>
  );
}

function HistoryView({ result, outOfSample }: { result: Record<string, any>; outOfSample: boolean }) {
  const metrics = Object.entries(result.metrics ?? {}) as [string, Record<string, unknown>][];
  return (
    <div className="mt-2 space-y-2 text-sm">
      <p className="font-medium">{result.notice}</p>
      {result.unavailable && <p className="text-amber-700 dark:text-amber-400">{result.unavailable}</p>}
      {result.provenance?.label && (
        <p className="text-amber-700 dark:text-amber-400">
          {result.provenance.label}: {result.provenance.incomplete_months.join(', ')}
        </p>
      )}
      <p className="text-xs text-slate-500">
        {result.decisions} decision sessions, every {result.policy?.step}th session · {result.horizon_sessions}-session excess return over {result.benchmark} · Top {result.top_n}
        {outOfSample
          ? ` · ${result.families_on_window} famil${result.families_on_window === 1 ? 'y' : 'ies'} evaluated on this window`
          : ` · ${result.research_runs} research run${result.research_runs === 1 ? '' : 's'} in this family`}
      </p>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="pr-3 py-1">Metric</th>
              <th className="pr-3">Mean</th>
              <th className="pr-3">95% interval</th>
              <th className="pr-3">p</th>
              {outOfSample && <th className="pr-3">p, adjusted</th>}
              <th className="pr-3">Sessions</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map(([key, m]) => {
              const f = key === 'rank_ic' ? num : pct;
              return (
                <tr key={key} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="pr-3 py-1">{String(m.name)}</td>
                  <td className="pr-3">{m.available ? f(m.mean) : '—'}</td>
                  <td className="pr-3">{m.available ? `${f(m.ci_low)} to ${f(m.ci_high)}` : '—'}</td>
                  <td className="pr-3">{m.available ? num(m.p, 3) : '—'}</td>
                  {outOfSample && <td className="pr-3">{m.available ? num(m.p_adjusted, 3) : '—'}</td>}
                  <td className="pr-3">{m.available ? String(m.n) : '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul className="text-xs text-slate-600 dark:text-slate-400 list-disc ml-4">
        {metrics.map(([key, m]) => (
          <li key={key}>{String(m.statement)}</li>
        ))}
        {result.regime?.text && <li>{result.regime.text}</li>}
      </ul>
    </div>
  );
}
