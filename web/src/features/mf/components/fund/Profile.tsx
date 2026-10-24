/**
 * Profile: where the numbers come from (sources, NAV coverage, gaps, flags) and
 * what is not stored yet.
 */
import type { FundDetail } from '../../api';
import { date } from '../../format';
import { useConfidence } from '../../queries';
import { Badge, Card, ErrorState, Skeleton } from '../ui';

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
<p className="text-xs text-mf-muted">
          TER, AUM, riskometer, benchmark, managers and exit load come from AMFI&rsquo;s TER disclosure, fund performance report and the scheme summary document; see Facts & costs.
        </p>
      </div>
    </div>
  );
}
