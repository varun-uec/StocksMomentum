/**
 * Discover (ui-ux doc 03 §01): start with a question, not a menu. Collections are
 * the backend presets; category cards show each category's top-scored fund and
 * 3Y CAGR median from the registry; market context is the NAV-built large-cap
 * proxy and the RBI 91-day T-bill. Nothing here is a popularity or social signal.
 */
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import type { Condition, Preset, ScreenRequest } from '../api';
import { ChartFrame, Sparkline, TimeChart, thin } from '../components/charts';
import { FundSearch } from '../components/FundSearch';
import { HeroArt } from '../components/HeroArt';
import { I } from '../components/icons';
import { ScoreBadge } from '../components/ScoreBadge';
import { Badge, Card, Chip, Delta, ErrorState, Loading, Segmented, Skeleton, SnapshotNote, buttonClass, cx, useTitle } from '../components/ui';
import { categoryShort, date, num, pct, schemeName } from '../format';
import { EXAMPLES, useRecentFunds } from '../context';
import { useFields, useMetrics, usePresets, useRegimes, useRiskFree, useScreen, useSparklines } from '../queries';
import { token } from '../theme/themes';
import { sinceYears } from '../series';
import { UNIVERSE, encodeView, filterOf, presetView } from '../view-spec';
import { useWatchlist } from '../workspace';

const CATEGORIES = [
  'Equity Scheme - Large Cap Fund',
  'Equity Scheme - Flexi Cap Fund',
  'Equity Scheme - Mid Cap Fund',
  'Equity Scheme - Small Cap Fund',
  'Equity Scheme - ELSS',
  'Hybrid Scheme - Aggressive Hybrid Fund',
  'Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage',
  'Debt Scheme - Corporate Bond Fund',
];

const LEADERS: ScreenRequest = {
  filter: { all: [...UNIVERSE, { field: 'category', op: 'in', value: CATEGORIES }, { field: 'score_cat_rank', op: '=', value: 1 }] },
  sort: [{ field: 'category', dir: 'asc' }],
  columns: ['category', 'score', 'cagr_3y', 'cagr_3y_cat_median', 'cagr_3y_cat_count'],
  page: { size: 20 },
};

export const categoryLink = (category: string) =>
  `/mf/screen?v=${encodeView({
    mode: 'all',
    conditions: [...UNIVERSE, { field: 'category', op: 'in', value: [category] } as Condition],
    sort: [{ field: 'score', dir: 'desc' }],
    columns: ['score', 'cagr_3y', 'cagr_5y', 'sharpe_3y', 'mdd_3y', 'consistency_3y', 'score_cat_rank'],
    formulas: {},
  })}`;

const REGIME_WORDS: Record<string, string> = { crash: 'crash', correction: 'correction', recovery: 'recovery' };

/**
 * The first viewport answers a question (audit 5.1): search and collections on the
 * left, today's market evidence on the right, and the registry facts as one line.
 */
function Hero({ presets }: { presets?: Preset[] }) {
  return (
    <section className="relative overflow-hidden rounded-[20px] border border-mf-line bg-mf-surface shadow-card">
      <HeroArt className="absolute inset-0 h-full w-full opacity-70" />
      <div className="relative grid gap-6 px-5 py-6 sm:px-8 sm:py-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,1fr)] lg:items-center">
        <div className="min-w-0">
          <h1 className="font-display text-[30px] leading-[1.08] text-mf-ink sm:text-[40px]">Find better mutual fund investments.</h1>
          <p className="mt-2 text-[15px] text-mf-ink-soft">Ten years of real NAVs, explained. Search a fund, or start from a question.</p>
          <div className="mt-5 max-w-xl">
            <FundSearch size="lg" label="Search funds from the home page" placeholder="Try “parag”, “sbi smallcap” or an AMFI code" />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {presets
              ? presets.map((p) => (
                  <Link key={p.id} to={`/mf/screen?preset=${p.id}`} title={p.purpose} className="mf-tap inline-flex min-h-9 items-center rounded-full border border-mf-line-strong bg-mf-surface/85 px-3.5 text-[13px] text-mf-ink-soft backdrop-blur transition-colors hover:border-mf-brand hover:text-mf-brand-strong">
                    {p.name}
                  </Link>
                ))
              : Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-9 w-28 rounded-full" />)}
          </div>
          <Facts />
        </div>
        <MarketPulse />
      </div>
    </section>
  );
}

/** The registry in one line: what the numbers on this site rest on. */
function Facts() {
  const fields = useFields();
  const regimes = useRegimes();
  const status = fields.byId.get('status');
  const category = fields.byId.get('category');
  const first = regimes.data?.proxy.levels[0]?.[0];
  const facts = [
    status && `${status.coverage.values.toLocaleString('en-IN')} plan options`,
    category && `${(category.values ?? []).filter((c) => c !== 'Unclassified').length} SEBI categories`,
    first && `NAVs from ${date(first)}`,
    fields.data && `${fields.data.fields.length} fields · method v${fields.data.method_version}`,
  ].filter(Boolean);
  return (
    <p className="mt-5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-mf-muted">
      {facts.length ? facts.map((f, i) => <span key={i} className="tabular">{i > 0 && <span aria-hidden="true" className="mr-3">·</span>}{f}</span>) : <Skeleton className="h-4 w-72" />}
    </p>
  );
}

/** Today's market evidence: the proxy's current phase, its last year, and the risk-free rate. */
function MarketPulse() {
  const regimes = useRegimes();
  const riskFree = useRiskFree();
  const year = useMemo(() => sinceYears(regimes.data?.proxy.levels ?? [], 1), [regimes.data]);
  const phase = regimes.data?.windows[regimes.data.windows.length - 1];
  const rate = riskFree.data?.points[riskFree.data.points.length - 1];
  return (
    <aside aria-label="Market today" className="rounded-[16px] border border-mf-line bg-mf-surface/90 p-4 shadow-card backdrop-blur sm:p-5">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-mf-muted">Market today</p>
        {regimes.data && <span className="text-[11px] text-mf-muted">NAVs to {date(regimes.data.as_of)}</span>}
      </div>
      {regimes.isLoading ? (
        <Skeleton className="mt-3 h-[150px]" />
      ) : regimes.isError ? (
        <ErrorState error={regimes.error} compact />
      ) : (
        <>
          {phase && (
            <p className="mt-2 text-[15px] leading-snug text-mf-ink">
              {phase.ongoing ? <>Large caps are in a <b>{REGIME_WORDS[phase.kind] ?? phase.kind}</b> phase since {date(phase.start)}: </> : <>The last large-cap <b>{REGIME_WORDS[phase.kind] ?? phase.kind}</b> ran {date(phase.start)} to {date(phase.end)}: </>}
              <b className={cx('tabular', phase.proxy_return < 0 ? 'text-mf-loss' : 'text-mf-brand-strong')}>{pct(phase.proxy_return, 1, true)}</b>.
            </p>
          )}
          <div className="mt-3 h-[84px]">{year.length > 1 && <Sparkline points={year} height={84} label="Large-cap proxy level over the last year" />}</div>
          <p className="mt-1 text-[11px] text-mf-muted">Large-cap proxy, last 12 months. Built from fund NAVs; not an official index.</p>
        </>
      )}
      <div className="mt-3 flex items-center justify-between gap-3 border-t border-mf-line pt-3">
        <div>
          <p className="text-[11px] text-mf-muted">Risk-free rate (91-day T-bill)</p>
          <p className="text-lg font-semibold tabular text-mf-ink">{rate ? `${rate[1].toFixed(2)}%` : '—'}</p>
        </div>
        <a href="#mf-market" className="text-sm font-medium text-mf-brand-strong hover:underline">
          Market context ↓
        </a>
      </div>
    </aside>
  );
}

function Categories() {
  const leaders = useScreen(LEADERS);
  const rows = new Map((leaders.data?.rows ?? []).map((r) => [String(r.values.category), r]));
  const lines = useSparklines([...rows.values()].map((r) => r.amfi_code));
  return (
    <Card title="Explore by category" subtitle="Active Direct Growth plans · each category's median 3Y CAGR, and the NAV of its top-scored fund (not a category average)" action={<Link to="/mf/screen" className="text-sm font-medium text-mf-brand hover:underline">Open screener</Link>}>
      {leaders.isError ? (
        <ErrorState error={leaders.error} onRetry={() => leaders.refetch()} compact />
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {CATEGORIES.map((c, i) => {
            const row = rows.get(c);
            return (
              <li key={c}>
                <Link
                  to={categoryLink(c)}
                  className="group block h-full rounded-[14px] border border-mf-line p-4 transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-mf-brand/50 hover:shadow-raised motion-reduce:hover:translate-y-0"
                  style={{ background: `linear-gradient(160deg, ${token(i % 2 ? 'warningSoft' : 'brandSoft', 0.75)}, ${token('surface')} 70%)` }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-mf-ink">{categoryShort(c)}</p>
                    <I.arrowUpRight className="h-4 w-4 text-mf-muted opacity-0 transition-opacity duration-150 group-hover:opacity-100" />
                  </div>
                  {leaders.isLoading ? (
                    <Skeleton className="mt-3 h-24 w-full" />
                  ) : (
                    <>
                      <p className="mt-2 text-[24px] font-semibold leading-none tabular text-mf-ink">{pct(row?.values.cagr_3y_cat_median)}</p>
                      <p className="mt-1 text-xs text-mf-muted">median 3Y CAGR of {row?.values.cagr_3y_cat_count ?? '—'} funds with 3 years of NAVs</p>
                      {row && (
                        <div className="mt-3 border-t border-mf-line pt-2">
                          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-mf-muted">Top fund’s NAV, 3 years</p>
                          <div className="h-[34px]">
                            {lines.data?.series[row.amfi_code] && <Sparkline points={lines.data.series[row.amfi_code]} height={34} label={`${schemeName(row.name)}, the category's top-scored fund: month-end NAV over 3 years. Not a category average.`} />}
                          </div>
                          <p className="mt-1 flex items-center gap-2 text-xs text-mf-ink-soft">
                            <ScoreBadge score={row.values.score as number | null} size="sm" />
                            <span className="min-w-0 truncate">
                              Top score · <span className="font-medium">{schemeName(row.name)}</span>
                            </span>
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

/** Equity collections first: most first-time investors start there (audit 3.1). */
const IDEA_ORDER = ['calm_equity', 'consistent_large_caps', 'ten_year_compounders', 'shallow_drawdown_hybrids', 'category_leaders', 'steady_debt'];

function Ideas({ presets: all }: { presets?: Preset[] }) {
  const rank = (id: string) => (IDEA_ORDER.includes(id) ? IDEA_ORDER.indexOf(id) : IDEA_ORDER.length);
  const presets = all && [...all].sort((a, b) => rank(a.id) - rank(b.id));
  const [active, setActive] = useState(0);
  const preset = presets?.[active];
  const body = useMemo<ScreenRequest | null>(() => {
    if (!preset) return null;
    const view = presetView(preset);
    const columns = [...new Set(['category', 'score', 'cagr_3y', 'sharpe_3y', 'score_cat_rank', 'score_cat_count', ...view.columns])];
    return { filter: filterOf(view), sort: view.sort, columns, page: { size: 4 } };
  }, [preset]);
  const screen = useScreen(body);
  const lines = useSparklines((screen.data?.rows ?? []).map((r) => r.amfi_code));
  return (
    <Card title="Ideas to research" subtitle={preset && <>Why these funds: {preset.purpose.charAt(0).toLowerCase() + preset.purpose.slice(1)}</>} action={preset && <Link to={`/mf/screen?preset=${preset.id}`} className="text-sm font-medium text-mf-brand hover:underline">See all {screen.data ? screen.data.matched : ''}</Link>}>
      <div className="mf-scroll -mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        {presets?.map((p, i) => (
          <Chip key={p.id} pressed={i === active} onClick={() => setActive(i)} className="shrink-0">
            {p.name}
          </Chip>
        ))}
      </div>
      <div className="mt-3">
        {screen.isError ? (
          <ErrorState error={screen.error} onRetry={() => screen.refetch()} compact />
        ) : !screen.data ? (
          <Loading label="Loading ideas" />
        ) : screen.data.rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-mf-muted">No fund matches this collection today.</p>
        ) : (
          <ul className={cx('divide-y divide-mf-line transition-opacity', screen.isPlaceholderData && 'opacity-50')}>
            {screen.data.rows.map((r) => (
              <li key={r.amfi_code}>
                <Link to={`/mf/funds/${r.amfi_code}`} className="group flex items-center gap-3 py-3">
                  <ScoreBadge score={r.values.score as number | null} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-mf-ink group-hover:text-mf-brand-strong">{schemeName(r.name)}</p>
                    <p className="mt-0.5 truncate text-xs text-mf-muted">
                      {categoryShort(String(r.values.category))} · <span className="tabular">{pct(r.values.cagr_3y)}</span> 3Y CAGR · Sharpe <span className="tabular">{num(r.values.sharpe_3y)}</span>
                      {r.values.score_cat_rank != null && ` · rank ${r.values.score_cat_rank}/${r.values.score_cat_count}`}
                    </p>
                  </div>
                  <div className="hidden w-24 shrink-0 sm:block">
                    {lines.data?.series[r.amfi_code] && <Sparkline points={lines.data.series[r.amfi_code]} height={30} label={`${schemeName(r.name)}: month-end NAV over 3 years`} />}
                  </div>
                  <I.chevronRight className="h-4 w-4 text-mf-muted" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

const WINDOWS = { '1Y': 1, '3Y': 3, '5Y': 5, Max: 99 } as const;
type Window = keyof typeof WINDOWS;

function MarketContext() {
  const regimes = useRegimes();
  const riskFree = useRiskFree();
  const [window, setWindow] = useState<Window>('3Y');
  const levels = useMemo(() => thin(sinceYears(regimes.data?.proxy.levels ?? [], WINDOWS[window]), 500), [regimes.data, window]);
  const latestWindow = regimes.data?.windows[regimes.data.windows.length - 1];
  const rates = useMemo(() => sinceYears(riskFree.data?.points ?? [], 5), [riskFree.data]);
  const lastRate = riskFree.data?.points[riskFree.data.points.length - 1];
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartFrame
        title="Large-cap market proxy"
        subtitle={regimes.data?.proxy.label ?? 'NAV-built proxy, not an official index'}
        controls={<Segmented label="Window" options={Object.keys(WINDOWS) as Window[]} value={window} onChange={setWindow} />}
        footnote={latestWindow && `Last proxy ${latestWindow.kind}: ${date(latestWindow.start)} to ${date(latestWindow.end)}, ${pct(latestWindow.proxy_return, 1, true)}`}
        table={{ columns: ['Date', 'Proxy level'], rows: thin(levels, 120).map(([d, v]) => [date(d), v.toFixed(2)]) }}
      >
        {regimes.isError ? (
          <ErrorState error={regimes.error} onRetry={() => regimes.refetch()} compact />
        ) : regimes.isLoading ? (
          <Skeleton className="h-[220px]" />
        ) : (
          <TimeChart label="Large-cap proxy level over time" area height={220} series={[{ id: 'proxy', label: 'Proxy level', points: levels }]} format={(v) => v.toFixed(0)} />
        )}
      </ChartFrame>
      <ChartFrame
        title="Risk-free rate"
        subtitle="RBI 91-day T-bill cut-off yield, used in Sharpe ratios"
        legend={lastRate && <span className="text-[22px] font-semibold tabular text-mf-ink">{lastRate[1].toFixed(2)}%</span>}
        footnote={
          <>
            {lastRate && `Latest auction ${date(lastRate[0])}. `}
            {riskFree.data?.acknowledgement}
          </>
        }
        table={{ columns: ['Auction', 'Yield % a year'], rows: rates.map(([d, v]) => [date(d), v.toFixed(2)]) }}
      >
        {riskFree.isError ? (
          <ErrorState error={riskFree.error} onRetry={() => riskFree.refetch()} compact />
        ) : riskFree.isLoading ? (
          <Skeleton className="h-[220px]" />
        ) : (
          <TimeChart label="91-day T-bill yield over five years" height={220} series={[{ id: 'rate', label: 'Yield', points: rates, color: token('info') }]} format={(v) => `${v.toFixed(1)}%`} />
        )}
      </ChartFrame>
    </div>
  );
}

function WatchRow({ code }: { code: string }) {
  const metrics = useMetrics(code);
  const m = metrics.data;
  if (!m) return <Skeleton className="my-2 h-10" />;
  return (
    <Link to={`/mf/funds/${code}`} className="group flex items-center gap-3 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium group-hover:text-mf-brand-strong">{schemeName(m.name)}</p>
        <p className="text-xs text-mf-muted">{categoryShort(String(m.values.category))}</p>
      </div>
      <div className="text-right text-xs">
        <p className="tabular text-sm font-medium">{pct(m.values.cagr_3y)}</p>
        <p className="text-mf-muted">3Y CAGR</p>
      </div>
      <div className="w-16 text-right text-xs">
        <Delta value={m.values.ret_1y} className="text-sm font-medium" />
        <p className="text-mf-muted">1Y</p>
      </div>
    </Link>
  );
}

function YourResearch() {
  const watch = useWatchlist();
  const recent = useRecentFunds();
  return (
    <Card title="Your research" subtitle={`${watch.codes.length} watched · ${recent.length} opened recently`} action={<Link to="/mf/workspace?tab=watchlists" className="text-sm font-medium text-mf-brand hover:underline">Open workspace</Link>}>
      {watch.loading ? (
        <Loading label="Loading watchlist" />
      ) : watch.codes.length === 0 ? (
        recent.length ? (
          <>
            <p className="pb-1 text-xs font-medium uppercase tracking-[0.06em] text-mf-muted">Opened recently</p>
            <div className="divide-y divide-mf-line">
              {recent.slice(0, 5).map((code) => (
                <WatchRow key={code} code={code} />
              ))}
            </div>
            <p className="pt-3 text-xs text-mf-muted">Star a fund to keep it here for good.</p>
          </>
        ) : (
          <div className="py-2">
            <p className="text-sm text-mf-ink-soft">Nothing here yet. Start with one of these:</p>
            <div className="mt-2 divide-y divide-mf-line">
              {EXAMPLES.map((e) => (
                <WatchRow key={e.code} code={e.code} />
              ))}
            </div>
          </div>
        )
      ) : (
        <div className="divide-y divide-mf-line">
          {watch.codes.slice(0, 6).map((code) => (
            <WatchRow key={code} code={code} />
          ))}
        </div>
      )}
    </Card>
  );
}

export default function Discover() {
  useTitle('Discover mutual funds');
  const presets = usePresets();
  const fields = useFields();
  return (
    <div className="space-y-6">
      <h1 className="sr-only">Discover</h1>
      <Hero presets={presets.data?.presets} />
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Ideas presets={presets.data?.presets} />
        <YourResearch />
      </div>
      <Categories />
      <section aria-labelledby="mf-market">
        <div className="mb-3 flex items-center gap-2">
          <h2 id="mf-market" className="font-display text-2xl text-mf-ink">
            Market context
          </h2>
          <Badge tone="info">Proxy</Badge>
        </div>
        <MarketContext />
      </section>
      <SnapshotNote asOf={fields.data?.as_of} revision={fields.data?.data_revision} method={fields.data?.method_version} extra={` · sources ${fields.data?.sources.join(', ')}`} />
    </div>
  );
}
