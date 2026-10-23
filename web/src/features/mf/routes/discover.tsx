/**
 * Discover (ui-ux doc 03 §01): start with a question, not a menu. Collections are
 * the backend presets; category cards show each category's top-scored fund and
 * 3Y CAGR median from the registry; market context is the NAV-built large-cap
 * proxy and the RBI 91-day T-bill. Nothing here is a popularity or social signal.
 */
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import type { Condition, Preset, ScreenRequest } from '../api';
import { ChartFrame, TimeChart, thin } from '../components/charts';
import { FundSearch } from '../components/FundSearch';
import { HeroArt } from '../components/HeroArt';
import { I } from '../components/icons';
import { ScoreBadge } from '../components/ScoreBadge';
import { Badge, Card, Chip, Delta, ErrorState, Loading, Segmented, Skeleton, SnapshotNote, buttonClass, cx, useTitle } from '../components/ui';
import { categoryShort, date, num, pct, schemeName } from '../format';
import { useFields, useMetrics, usePresets, useRegimes, useRiskFree, useScreen } from '../queries';
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

function Hero({ presets }: { presets?: Preset[] }) {
  return (
    <section className="relative overflow-hidden rounded-[20px] border border-mf-line bg-mf-surface shadow-card">
      <HeroArt className="absolute inset-0 h-full w-full" />
      <div className="relative max-w-2xl px-6 py-8 sm:px-10 sm:py-11">
        <h1 className="font-display text-[34px] leading-[1.08] text-mf-ink sm:text-[46px]">
          Find better
          <br />
          mutual fund investments.
        </h1>
        <p className="mt-3 text-[15px] text-mf-ink-soft sm:text-base">Deep research. Clear evidence. Confident decisions.</p>
        <div className="mt-6 max-w-lg sm:hidden">
          <FundSearch size="lg" placeholder="Search a fund, code or ISIN" />
        </div>
        <div className="mt-6 flex flex-wrap gap-2">
          {presets
            ? presets.map((p) => (
                <Link key={p.id} to={`/mf/screen?preset=${p.id}`} title={p.purpose} className="inline-flex min-h-9 items-center rounded-full border border-mf-line-strong bg-mf-surface/85 px-3.5 text-[13px] text-mf-ink-soft backdrop-blur hover:border-mf-brand hover:text-mf-brand-strong">
                  {p.name}
                </Link>
              ))
            : Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-9 w-28 rounded-full" />)}
        </div>
      </div>
    </section>
  );
}

function Facts() {
  const fields = useFields();
  const regimes = useRegimes();
  const status = fields.byId.get('status');
  const category = fields.byId.get('category');
  const first = regimes.data?.proxy.levels[0]?.[0];
  const facts = [
    { value: status ? status.coverage.values.toLocaleString('en-IN') : null, label: 'Plan options', sub: 'Every AMFI scheme plan', icon: I.layers },
    { value: category ? String((category.values ?? []).filter((c) => c !== 'Unclassified').length) : null, label: 'Categories', sub: 'SEBI categories (AMFI labels)', icon: I.grid },
    { value: first && fields.data ? `${Number(fields.data.as_of.slice(0, 4)) - Number(first.slice(0, 4))} years` : null, label: 'NAV history', sub: first ? `${date(first)} onward` : '', icon: I.calendar },
    { value: fields.data ? String(fields.data.fields.length) : null, label: 'Analytics fields', sub: fields.data ? `Method v${fields.data.method_version}` : '', icon: I.studio },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {facts.map((f) => (
        <div key={f.label} className="flex items-start justify-between gap-2 rounded-card border border-mf-line bg-mf-surface p-4 shadow-card">
          <div className="min-w-0">
            {f.value === null ? <Skeleton className="h-7 w-20" /> : <p className="text-[24px] font-semibold leading-tight tabular">{f.value}</p>}
            <p className="mt-1 text-sm text-mf-ink-soft">{f.label}</p>
            <p className="truncate text-xs text-mf-muted">{f.sub}</p>
          </div>
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[10px] bg-mf-brand-soft text-mf-brand">
            <f.icon />
          </span>
        </div>
      ))}
    </div>
  );
}

function Categories() {
  const leaders = useScreen(LEADERS);
  const rows = new Map((leaders.data?.rows ?? []).map((r) => [String(r.values.category), r]));
  return (
    <Card title="Explore by category" subtitle="Active Direct Growth plans · median 3Y CAGR of each category, and its top-scored fund" action={<Link to="/mf/screen" className="text-sm font-medium text-mf-brand hover:underline">Open screener</Link>}>
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
                  className="group block h-full rounded-[12px] border border-mf-line p-4 transition-colors duration-150 hover:border-mf-brand/50"
                  style={{ background: `linear-gradient(160deg, ${token(i % 2 ? 'warningSoft' : 'brandSoft', 0.75)}, ${token('surface')} 70%)` }}
                >
                  <p className="text-sm font-semibold text-mf-ink">{categoryShort(c)}</p>
                  {leaders.isLoading ? (
                    <Skeleton className="mt-3 h-10 w-full" />
                  ) : (
                    <>
                      <p className="mt-2 text-[22px] font-semibold leading-none tabular text-mf-ink">{pct(row?.values.cagr_3y_cat_median)}</p>
                      <p className="mt-1 text-xs text-mf-muted">median 3Y CAGR · {row?.values.cagr_3y_cat_count ?? '—'} funds ranked</p>
                      {row && (
                        <p className="mt-3 truncate border-t border-mf-line pt-2 text-xs text-mf-ink-soft">
                          Top score: <span className="font-medium">{schemeName(row.name)}</span>
                        </p>
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

function Ideas({ presets }: { presets?: Preset[] }) {
  const [active, setActive] = useState(0);
  const preset = presets?.[active];
  const body = useMemo<ScreenRequest | null>(() => {
    if (!preset) return null;
    const view = presetView(preset);
    const columns = [...new Set(['category', 'score', 'cagr_3y', 'sharpe_3y', 'score_cat_rank', 'score_cat_count', ...view.columns])];
    return { filter: filterOf(view), sort: view.sort, columns, page: { size: 4 } };
  }, [preset]);
  const screen = useScreen(body);
  return (
    <Card title="Ideas to research" subtitle={preset?.purpose} action={preset && <Link to={`/mf/screen?preset=${preset.id}`} className="text-sm font-medium text-mf-brand hover:underline">See all {screen.data ? screen.data.matched : ''}</Link>}>
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
    <Link to={`/mf/funds/${code}`} className="flex items-center gap-3 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{schemeName(m.name)}</p>
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
  return (
    <Card title="Your watchlist" action={<Link to="/mf/workspace?tab=watchlists" className="text-sm font-medium text-mf-brand hover:underline">Open</Link>}>
      {watch.loading ? (
        <Loading label="Loading watchlist" />
      ) : watch.codes.length === 0 ? (
        <p className="py-4 text-sm text-mf-muted">
          Star a fund from its page or from the screener. Your watchlist is saved on this machine’s server and comes back after a restart.
        </p>
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
      <Facts />
      <Categories />
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Ideas presets={presets.data?.presets} />
        <YourResearch />
      </div>
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
