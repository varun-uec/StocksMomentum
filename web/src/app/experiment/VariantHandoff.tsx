import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { getEvaluation } from '@/lib/api-client';
import { Badge, Card } from '@/components/shared/Card';
import { focusRing } from '@/lib/theme';
import { joinableFamilies, type Family, type VariantForm, type VariantRun } from '@/lib/studio';

const field = `w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm placeholder-slate-400 dark:placeholder-slate-500 ${focusRing}`;
const label = 'block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5';

/** Form for a variant: its name and the hypothesis it tests (ADR-014 section 12). */
export function VariantForm({
  form,
  onChange,
  families,
}: {
  form: VariantForm;
  onChange: (next: VariantForm) => void;
  families: Family[];
}) {
  const joinable = joinableFamilies(families, form.parentHash);
  const family = joinable.find((f) => f.id === form.familyId);
  return (
    <fieldset className="space-y-3 border border-slate-200 dark:border-slate-700 rounded-lg p-3">
      <legend className="px-1 text-xs font-semibold text-slate-500 uppercase tracking-wider">Variant in Strategy Studio</legend>
      <p className="text-sm text-slate-600 dark:text-slate-400">
        Overrides make a variant of the base strategy. Strategy Studio saves it in a family and runs it as Historical Research — In-Sample.
        Not evidence of future returns. It never uses the hold-out.
      </p>
      <div>
        <label htmlFor="variant-name" className={label}>
          Variant name
        </label>
        <input
          id="variant-name"
          type="text"
          maxLength={80}
          value={form.name}
          onChange={(e) => onChange({ ...form, name: e.target.value })}
          className={`max-w-xs ${field}`}
        />
      </div>
      <div role="radiogroup" aria-label="Hypothesis" className="space-y-2">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="variant-hypothesis-mode"
            checked={form.mode === 'new'}
            onChange={() => onChange({ ...form, mode: 'new', confirmed: false })}
            className={focusRing}
          />
          State a hypothesis (new family)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="variant-hypothesis-mode"
            checked={form.mode === 'existing'}
            onChange={() => onChange({ ...form, mode: 'existing', confirmed: false })}
            className={focusRing}
          />
          Join an existing family
        </label>
      </div>
      {form.mode === 'new' ? (
        <div>
          <label htmlFor="variant-hypothesis" className={label}>
            Hypothesis, in one sentence
          </label>
          <textarea
            id="variant-hypothesis"
            rows={2}
            maxLength={300}
            value={form.hypothesis}
            onChange={(e) => onChange({ ...form, hypothesis: e.target.value })}
            placeholder="A lower RS floor keeps more winners in the qualified set."
            className={`max-w-lg ${field}`}
          />
        </div>
      ) : (
        <div className="space-y-2">
          <label htmlFor="variant-family" className={label}>
            Family of the base strategy
          </label>
          <select
            id="variant-family"
            value={form.familyId ?? ''}
            onChange={(e) => onChange({ ...form, familyId: e.target.value ? Number(e.target.value) : null, confirmed: false })}
            className={`max-w-lg ${field}`}
          >
            <option value="">{joinable.length ? 'Choose a family' : 'No family starts from this base strategy'}</option>
            {joinable.map((f) => (
              <option key={f.id} value={f.id}>
                Family {f.id}: {f.hypothesis}
              </option>
            ))}
          </select>
          {family && (
            <>
              <blockquote className="border-l-2 border-slate-300 dark:border-slate-600 pl-3 text-sm italic text-slate-700 dark:text-slate-300">
                {family.hypothesis}
              </blockquote>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.confirmed}
                  onChange={(e) => onChange({ ...form, confirmed: e.target.checked })}
                  className={focusRing}
                />
                This hypothesis covers my variant.
              </label>
            </>
          )}
        </div>
      )}
    </fieldset>
  );
}

const STATUS_TEXT = { queued: 'Queued', running: 'Running', completed: 'Completed', failed: 'Failed' } as const;

/** What the handoff did: parent, variant, hypothesis, and the run with its result-class label. */
export function VariantResult({ run }: { run: VariantRun }) {
  const { data: evaluation = run.evaluation } = useQuery({
    queryKey: ['evaluation', run.evaluation.id],
    queryFn: () => getEvaluation(run.evaluation.id),
    initialData: run.evaluation,
    refetchInterval: (q) => (q.state.data && ['queued', 'running'].includes(q.state.data.status) ? 2000 : false),
  });
  const progress = evaluation.progress_total
    ? ` (${evaluation.progress_done} of ${evaluation.progress_total} decisions)`
    : '';
  return (
    <Card title="Variant handed to Strategy Studio" subtitle={`${run.variant.name} v${run.variant.version} vs ${run.parent.name}`}>
      <section aria-label="Variant run" className="space-y-3 text-sm">
        <dl className="grid grid-cols-1 sm:grid-cols-[10rem_1fr] gap-x-4 gap-y-1.5">
          <dt className="text-slate-500">Parent strategy</dt>
          <dd>
            {run.parent.name} v{run.parent.version} <code className="text-xs">{run.parent.config_hash.slice(0, 12)}</code>
          </dd>
          <dt className="text-slate-500">Variant</dt>
          <dd>
            {run.variant.name} v{run.variant.version} <code className="text-xs">{run.variant.config_hash.slice(0, 12)}</code>
            {run.reused_variant && ' (already stored)'}
          </dd>
          <dt className="text-slate-500">Overrides</dt>
          <dd>
            <ul>
              {run.overrides.map((o) => (
                <li key={o.parameter_path}>
                  <code className="text-xs">{o.parameter_path}</code> = {String(o.value)}
                </li>
              ))}
            </ul>
          </dd>
          <dt className="text-slate-500">Hypothesis</dt>
          <dd>
            {run.family.hypothesis} <span className="text-xs text-slate-500">(family {run.family.id})</span>
          </dd>
          <dt className="text-slate-500">Result class</dt>
          <dd>
            <Badge color="indigo">{evaluation.label}</Badge>
          </dd>
          <dt className="text-slate-500">Status</dt>
          <dd>
            <span role="status">
              {STATUS_TEXT[evaluation.status]}
              {progress}
            </span>
            {evaluation.error && <span className="text-rose-600 dark:text-rose-400"> — {evaluation.error}</span>}
          </dd>
          <dt className="text-slate-500">Research runs</dt>
          <dd>
            {run.research_runs} research run{run.research_runs === 1 ? '' : 's'} in this family
            {run.reused_run && '. This run already existed, so it is not counted again.'}
          </dd>
        </dl>
        <p className="font-medium">{run.notice}</p>
        <p>
          <Link to="/studio" className={`text-indigo-600 dark:text-indigo-400 hover:underline rounded ${focusRing}`}>
            Open Strategy Studio for the full result
          </Link>
        </p>
      </section>
    </Card>
  );
}
