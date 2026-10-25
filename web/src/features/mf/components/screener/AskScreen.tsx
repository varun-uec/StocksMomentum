/**
 * Plain-language screening: "diversified equity funds with consistent five-year
 * performance and TER below 1%" becomes ordinary conditions the reader can see,
 * edit and save. The reading is the server's rule-based interpreter; it returns
 * conditions only, so every fund and number shown still comes from the screen.
 * A second question refines the current screen; "Start over" reads it afresh.
 */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { mfApi, type FilterNode, type Interpretation, type SortKey } from '../../api';
import { I } from '../icons';
import { Button, cx, inputClass } from '../ui';

const EXAMPLES = [
  'Diversified equity funds with consistent five-year performance, relatively low drawdowns and TER below 1%',
  'Flexi cap funds that beat their benchmark over 5 years',
  'Low-cost large cap funds with low volatility',
];

export function AskScreen({
  base,
  sort,
  initial,
  onApply,
}: {
  /** The current screen's top-level conditions, refined by a follow-up question. */
  base: FilterNode[];
  sort: SortKey[];
  /** A question handed over in the URL, read once on arrival. */
  initial?: string | null;
  onApply: (result: Interpretation) => void;
}) {
  const [text, setText] = useState(initial ?? '');
  const [turns, setTurns] = useState<{ asked: string; result: Interpretation }[]>([]);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const wide = typeof window === 'undefined' || !window.matchMedia || window.matchMedia('(min-width: 768px)').matches;

  const ask = async (asked: string, refine: boolean) => {
    const question = asked.trim();
    if (!question || busy) return;
    setBusy(true);
    setFailed(false);
    try {
      const result = await mfApi.interpret({ text: question, ...(refine ? { base, sort } : {}) });
      setTurns((previous) => [...(refine ? previous : []), { asked: question, result }]);
      setText('');
      onApply(result);
    } catch {
      // The screen is left as it was; the filters still work by hand.
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const once = useRef(false);
  useEffect(() => {
    if (initial && !once.current) {
      once.current = true;
      void ask(initial, false);
    }
    // Read a handed-over question once, on arrival.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  const refining = turns.length > 0;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    void ask(text, refining);
  };
  const last = turns.at(-1)?.result;

  return (
    <section aria-labelledby="ask-screen" className="rounded-card border border-mf-brand/25 bg-gradient-to-br from-mf-brand-soft/60 to-mf-surface p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="ask-screen" className="inline-flex items-center gap-2 text-sm font-semibold text-mf-ink">
          <I.ask className="h-4 w-4 text-mf-brand" /> Describe the funds you want
        </h2>
        {refining && (
          <button
            type="button"
            className="text-xs font-medium text-mf-brand-strong underline-offset-2 hover:underline"
            onClick={() => {
              setTurns([]);
              setText('');
              input.current?.focus();
            }}
          >
            Start over
          </button>
        )}
      </div>
      <form onSubmit={submit} className="mt-2 flex gap-2">
        <label htmlFor="ask-screen-input" className="sr-only">
          {refining ? 'Refine this screen in plain words' : 'Describe a screen in plain words'}
        </label>
        <input
          id="ask-screen-input"
          ref={input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          placeholder={refining ? 'Refine: “TER under 0.8%”, “remove the drawdown limit”' : 'e.g. flexi cap funds with low drawdowns and TER below 1%'}
          className={cx(inputClass, 'min-w-0 flex-1')}
        />
        <Button type="submit" variant="primary" disabled={busy || !text.trim()}>
          {busy ? 'Reading…' : refining ? 'Refine' : 'Screen'}
        </Button>
      </form>

      {failed && (
        <p role="alert" className="mt-2 text-sm text-mf-loss">
          That could not be read just now, so the screen is unchanged. The filters below still work.
        </p>
      )}

      {!refining && !failed && (
        <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label="Example requests">
          {EXAMPLES.map((example) => (
            <button key={example} type="button" onClick={() => void ask(example, false)} disabled={busy} className="max-w-full truncate rounded-full border border-mf-line bg-mf-surface px-2.5 py-1 text-left text-xs text-mf-ink-soft hover:border-mf-brand/50 hover:text-mf-ink">
              {example}
            </button>
          ))}
        </div>
      )}

      {last && (
        // Open on wide screens; on a phone a one-line summary keeps the results near the top.
        <details key={turns.length} open={wide} className="group mt-3 text-sm" aria-live="polite">
          <summary className="cursor-pointer list-none text-xs text-mf-muted [&::-webkit-details-marker]:hidden">
            {turns.length > 1 ? 'Refined with' : 'Read'} “{turns.at(-1)!.asked}” as {last.clauses.length} {last.clauses.length === 1 ? 'condition' : 'conditions'}
            {last.not_understood.length > 0 && `, ${last.not_understood.length} ${last.not_understood.length === 1 ? 'phrase' : 'phrases'} not used`}. <span className="font-medium text-mf-brand-strong group-open:hidden">Show how</span>
            <span className="hidden group-open:inline">Edit any of them below.</span>
          </summary>
          <div className="mt-2 space-y-2">
          {last.clauses.length > 0 && (
            <ul className="space-y-1">
              {last.clauses.map((c) => (
                <li key={`${c.phrase}-${c.explanation}`} className="flex gap-2">
                  <I.check className="mt-0.5 h-4 w-4 shrink-0 text-mf-gain" />
                  <span>
                    <span className="font-medium text-mf-ink">{c.explanation}</span>
                    <span className="text-mf-muted"> · from “{c.phrase}”</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {last.assumptions.length > 0 && <p className="text-xs text-mf-muted">Also assumed: {last.assumptions.join('; ')}.</p>}
          {last.not_understood.length > 0 && (
            <p className="rounded-[10px] border border-mf-warning/40 bg-mf-warning-soft px-3 py-2 text-xs text-mf-ink">
              Not used, because no screen field matches: {last.not_understood.map((w) => `“${w}”`).join(', ')}. Try other words, or pick a metric from the filters.
            </p>
          )}
          {last.notes.map((note) => (
            <p key={note} className="text-xs text-mf-muted">
              {note}
            </p>
          ))}
          </div>
        </details>
      )}
    </section>
  );
}
