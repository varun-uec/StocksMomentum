/**
 * Profile: where the numbers come from (sources, NAV coverage, gaps, flags) and
 * what is not stored yet. Holdings: a named dependency (E4), never guessed data.
 */
import type { FundDetail } from '../../api';
import { date } from '../../format';
import { useConfidence } from '../../queries';
import { Badge, Card, DependencyPanel, ErrorState, Skeleton } from '../ui';

export function Profile({ code, detail }: { code: string; detail: FundDetail }) {
  const conf = useConfidence(code);
  const c = conf.data;
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card title="Data behind this page" subtitle="Each NAV keeps its source and import revision">
        {conf.isError ? (
          <ErrorState error={conf.error} compact />
        ) : !c ? (
          <Skeleton className="h-48" />
        ) : (
          <div className="space-y-4">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              {[
                ['Status', c.status],
                ['History', `${c.history_days.toLocaleString('en-IN')} days`],
                ['Valid NAVs', c.valid_navs.toLocaleString('en-IN')],
                ['First and last NAV', `${date(c.first_nav)} – ${date(c.last_nav)}`],
                ['Gaps over 7 days', String(c.gaps_over_7_days)],
                ['Longest gap', `${c.longest_gap_days} days`],
                ['Excluded NAVs', String(c.excluded_navs)],
                ['Jump flags', String(c.jump_flags)],
                ['Category basis', c.category_basis.toUpperCase()],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-mf-muted">{k}</dt>
                  <dd className="tabular">{v}</dd>
                </div>
              ))}
            </dl>
            <div>
              <p className="mb-1.5 text-xs text-mf-muted">Sources</p>
              <ul className="space-y-1 text-sm">
                {c.sources.map((s) => (
                  <li key={s.source} className="flex flex-wrap items-center gap-2">
                    <Badge>{s.source.toUpperCase()}</Badge>
                    {s.rows.toLocaleString('en-IN')} NAVs, {date(s.first)} – {date(s.last)}
                  </li>
                ))}
              </ul>
            </div>
            {c.notes.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-xs text-mf-muted">
                {c.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Card>
      <div className="space-y-4">
        <Card title="Scheme record" subtitle="As AMFI's scheme master names it">
          <dl className="space-y-2.5 text-sm">
            {[
              ['Scheme', detail.fund.scheme_name],
              ['NAV name', detail.fund.nav_name],
              ['Scheme type', detail.fund.scheme_type],
              ['Category as filed', detail.classification.source_category],
              ['ISIN (growth)', detail.fund.isin_growth ?? '—'],
              ['ISIN (reinvest)', detail.fund.isin_reinvest ?? '—'],
              ['Return basis', detail.classification.return_basis.toUpperCase()],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-mf-muted">{k}</dt>
                <dd className="break-words">{v}</dd>
              </div>
            ))}
          </dl>
        </Card>
        <DependencyPanel title="Expense ratio, AUM, fund manager, exit load and riskometer" needs="E1, AMC monthly disclosures with a rights grant">
          These come from AMC disclosures, not NAVs. They stay empty until a licensed source is imported; they are never estimated.
        </DependencyPanel>
      </div>
    </div>
  );
}

export function Holdings() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <DependencyPanel title="Portfolio holdings and their changes" needs="E4, dated AMC portfolio disclosures">
        Holdings, top positions, sector weights and month-on-month changes need each AMC’s monthly portfolio file. The page will show the disclosure date and any weight it cannot resolve.
      </DependencyPanel>
      <DependencyPanel title="Overlap with other funds" needs="E4 holdings for both funds">
        The Peers tab shows NAV correlation today. Correlation says two funds move together; it does not say they own the same stocks.
      </DependencyPanel>
      <DependencyPanel title="Sector, style and valuation" needs="E7, a security classification with dated coverage">
        Style boxes and valuation ratios depend on holdings plus a stock data supplier.
      </DependencyPanel>
      <DependencyPanel title="Benchmark-relative risk" needs="E3, the scheme's licensed total-return index">
        Alpha, beta, tracking error and capture ratios need the official benchmark. The Risk tab uses a NAV-built proxy and labels it.
      </DependencyPanel>
    </div>
  );
}
