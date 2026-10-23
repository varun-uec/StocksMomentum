/**
 * Multilingual research (ui-ux doc 03 §09): a Slice 5 capability (ADR-022). Until
 * the agent runtime ships there is no chat box and no generated answer. Each
 * example question links to the view that answers it with today's tools.
 */
import { Link } from 'react-router';
import { I } from '../components/icons';
import { Badge, DependencyPanel, PageHeader, useTitle } from '../components/ui';

const QUESTIONS = [
  { en: 'Which flexi-cap funds stayed consistent over three years?', hi: 'कौन से फ़्लेक्सी-कैप फ़ंड तीन साल तक लगातार अच्छे रहे?', to: '/mf/screen?preset=category_leaders', tool: 'Screener · Category leaders' },
  { en: 'How far did my fund fall in 2020, and when did it recover?', hi: 'Mera fund 2020 mein kitna gira aur kab recover hua?', to: '/mf/studio?mode=drawdown', tool: 'Studio · Drawdowns' },
  { en: 'Compare these funds on downside and consistency.', hi: 'इन फ़ंड्स की गिरावट और स्थिरता की तुलना करें।', to: '/mf/compare', tool: 'Compare' },
  { en: 'What would a ₹10,000 SIP have become over five years?', hi: '₹10,000 ki SIP paanch saal mein kitni ban jaati?', to: '/mf/simulate?kind=sip', tool: 'Investment lab · SIP' },
];

export default function Ask() {
  useTitle('AI research');
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Planned · Slice 5" title="Ask Wickstreet, in your language" lead="Questions in English, हिन्दी or Hinglish, answered with cited numbers from the same tools you see here. It opens an editable view you can check and save." />
      <DependencyPanel title="Research agent" needs="A1, the agent runtime with tool citations and validation (ADR-022)">
        Every number in an answer will come from a tool result, never from the model’s wording. No answer is shown until that runtime exists.
      </DependencyPanel>
      <section aria-labelledby="ask-today">
        <h2 id="ask-today" className="mb-3 font-display text-2xl">
          Answer these today
        </h2>
        <ul className="grid gap-3 md:grid-cols-2">
          {QUESTIONS.map((q) => (
            <li key={q.en}>
              <Link to={q.to} className="group block h-full rounded-card border border-mf-line bg-mf-surface p-5 shadow-card transition-colors hover:border-mf-brand/50">
                <p className="font-medium text-mf-ink">{q.en}</p>
                <p lang={/[ऀ-ॿ]/.test(q.hi) ? 'hi' : 'en'} className="mt-1 text-sm leading-[1.55] text-mf-muted">
                  {q.hi}
                </p>
                <p className="mt-3 inline-flex items-center gap-1 text-sm text-mf-brand">
                  <Badge tone="brand">Works now</Badge> {q.tool} <I.chevronRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </p>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
