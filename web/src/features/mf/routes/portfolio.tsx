/**
 * Portfolio and CAS (ui-ux doc 03 §07): a Slice 6 capability. This page states
 * what the service will do and what it needs. It offers no upload control and
 * shows no portfolio numbers, because neither exists yet.
 */
import { Link } from 'react-router';
import { I } from '../components/icons';
import { Badge, Card, DependencyPanel, PageHeader, buttonClass, cx, useTitle } from '../components/ui';

const STEPS = [
  { title: 'Choose your CAS file', text: 'A CAMS or KFintech consolidated account statement, read on this machine only. The password is used once and never stored.' },
  { title: 'Review before anything is saved', text: 'Every transaction, unresolved fund and possible duplicate shows in a preview. Nothing changes until you confirm.' },
  { title: 'Confirm, and undo if needed', text: 'An import is one batch you can roll back exactly. Importing the same file twice changes nothing.' },
  { title: 'See through the wrappers', text: 'Value, XIRR on your real cash flows, allocation, overlap and drift, with any unknown exposure shown as unknown.' },
];

export default function Portfolio() {
  useTitle('Portfolio');
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Planned · Slice 6" title="Your portfolio, honestly reconciled" lead="Import your CAS on this machine to see what you own, what it returned and where it overlaps. This needs the portfolio service first." />
      <ol className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {STEPS.map((s, i) => (
          <li key={s.title} className="rounded-card border border-mf-line bg-mf-surface p-5 shadow-card">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-mf-brand-soft text-sm font-semibold text-mf-brand-strong">{i + 1}</span>
            <p className="mt-3 font-medium">{s.title}</p>
            <p className="mt-1 text-sm text-mf-muted">{s.text}</p>
          </li>
        ))}
      </ol>
      <div className="grid gap-4 lg:grid-cols-2">
        <DependencyPanel title="CAS import and ledger" needs="P1, a local parser with preview, commit and undo">
          Parsing stays on this machine. Raw files and passwords never reach logs, the repository or any model.
        </DependencyPanel>
        <DependencyPanel title="Portfolio intelligence" needs="P2, plus E1 costs and E4 holdings for look-through">
          Allocation, overlap and drift need dated holdings. Until then, exposure cannot be shown without guessing.
        </DependencyPanel>
      </div>
      <Card title="What you can do today">
        <div className="flex flex-wrap gap-2">
          <Link to="/mf/workspace?tab=watchlists" className={cx(buttonClass('secondary'), '!h-auto min-h-10 !whitespace-normal py-2 text-left')}>
            <I.star className="h-4 w-4" />
            Track the funds you own in a watchlist
          </Link>
          <Link to="/mf/simulate" className={cx(buttonClass('secondary'), '!h-auto min-h-10 !whitespace-normal py-2 text-left')}>
            <I.lab className="h-4 w-4" />
            Replay your SIP in the investment lab
          </Link>
          <Link to="/mf/compare" className={cx(buttonClass('secondary'), '!h-auto min-h-10 !whitespace-normal py-2 text-left')}>
            <I.compare className="h-4 w-4" />
            Check how closely your funds move together
          </Link>
        </div>
        <p className="mt-3 text-xs text-mf-muted">
          <Badge tone="neutral">Privacy</Badge> Wickstreet runs on your machine. No portfolio data is collected.
        </p>
      </Card>
    </div>
  );
}
