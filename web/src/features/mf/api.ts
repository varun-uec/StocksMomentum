/**
 * Typed transport for the MF research API (`/api/v1/mf`, ui-ux doc 04).
 *
 * The backend returns plain dictionaries, so these interfaces are the checked
 * contract; `api.test.ts` holds the field names against recorded responses.
 * Values stay raw: fractions stay fractions until `format.ts` displays them.
 */

export const MF_API = '/api/v1/mf';

/** What every research read carries: which snapshot the numbers come from. */
export interface Envelope {
  data_revision: number;
  latest_revision: number;
  method_version: number;
  as_of: string;
  sources: string[];
}

export type Unit = 'fraction' | 'percentile' | 'count' | 'quartile' | 'rank' | 'days' | 'ratio' | 'INR' | 'INR crore' | 'years' | null;
export type FieldType = 'number' | 'enum' | 'date' | 'boolean';

export interface FieldDef {
  id: string;
  label: string;
  group: string;
  type: FieldType;
  unit: Unit;
  description: string;
  values?: string[];
  available: boolean;
  coverage: { values: number; missing: Record<string, number> };
  /** A number field's lowest and highest value in the snapshot. */
  range?: [number, number];
}

export interface FieldsResponse extends Envelope {
  registry_version: string;
  fields: FieldDef[];
}

export type Op =
  | '<' | '<=' | '>' | '>=' | '=' | '!='
  | 'in' | 'not_in' | 'between' | 'top_pct' | 'bottom_pct' | 'is_available' | 'is_missing';
export interface Condition {
  field: string;
  op: Op;
  value: unknown;
}
export type FilterNode = Condition | { all: FilterNode[] } | { any: FilterNode[] };
export interface SortKey {
  field: string;
  dir: 'asc' | 'desc';
}

export interface Preset {
  id: string;
  name: string;
  purpose: string;
  filter: { all: FilterNode[] } | { any: FilterNode[] };
  sort: SortKey[];
  columns: string[];
}

export interface Missing {
  state: 'NA' | 'NM';
  reason: string;
}

export interface ScreenRow {
  plan_option_id: number;
  amfi_code: string;
  name: string;
  values: Record<string, string | number | boolean | null>;
  states: Record<string, Missing>;
  conditions: { path: string; passed: boolean; value: unknown }[];
}

export interface ScreenRequest {
  filter: { all: FilterNode[] } | { any: FilterNode[] };
  sort: SortKey[];
  columns: string[];
  formulas?: Record<string, string>;
  page: { size: number; after?: string };
  data_revision?: number;
}

export interface ScreenResponse extends Envelope {
  total: number;
  matched: number;
  columns: string[];
  rows: ScreenRow[];
  excluded_missing: { path: string; field: string; count: number; reasons: Record<string, number> }[];
  /** For a zero-match top-level ALL: the matches without each part (`all[i]`). */
  relaxations: { path: string; matched: number }[];
  next: string | null;
}

export interface FundHit {
  amfi_code: string;
  name: string;
  amc: string;
  category: string;
  plan: string;
  option: string;
  nav_available: boolean;
  /** 'active' or 'historical'; null for a plan with no NAVs. Optional for older servers. */
  status?: string | null;
  last_nav_date?: string | null;
}

export interface FundDetail extends Envelope {
  fund: {
    plan_option_id: number;
    amfi_code: string;
    amc: string;
    scheme_name: string;
    nav_name: string;
    scheme_type: string;
    category: string;
    plan: string;
    option: string;
    isin_growth: string | null;
    isin_reinvest: string | null;
    launch_date: string | null;
  };
  classification: {
    category: string;
    source_category: string;
    asset_class: string;
    plan: string;
    option: string;
    return_basis: string;
    active: boolean;
    last_nav_date: string | null;
    since_start: string | null;
  };
  links: unknown[];
}

export interface Metrics extends Envelope {
  plan_option_id: number;
  amfi_code: string;
  name: string;
  values: Record<string, string | number | boolean | null>;
  states: Record<string, Missing>;
  anchors: Record<string, string>;
  since_label: string;
}

export interface Score extends Envelope {
  amfi_code: string;
  score: number | null;
  state: Missing | null;
  rank: number | null;
  peers_ranked: number | null;
  formula: string;
  parts: {
    field: string;
    value: number | null;
    state: Missing | null;
    category_percentile: number | null;
    percentile_state: Missing | null;
    peers_ranked: number | null;
    weight: number;
  }[];
  penalties: unknown[];
  data_quality: unknown[];
}

export interface Confidence {
  data_revision: number;
  as_of: string;
  method_version: number;
  sources: { source: string; rows: number; first: string; last: string }[];
  amfi_code: string;
  status: string;
  first_nav: string | null;
  last_nav: string | null;
  history_days: number;
  valid_navs: number;
  gaps_over_7_days: number;
  longest_gap_days: number;
  excluded_navs: number;
  jump_flags: number;
  category: string;
  category_basis: string;
  notes: string[];
}

export type Point = [string, number];

export interface NavRow {
  date: string;
  nav: string;
  anomaly: string | null;
  source: string;
  revision: number;
}

export interface Annual extends Envelope {
  calendar: { period: string; return: number | null; partial: boolean }[];
  financial: { period: string; return: number | null; partial: boolean }[];
  monthly: { year: number; month: number; return: number | null }[];
}

export interface Drawdown {
  depth: number;
  peak: string;
  trough: string;
  recovery: string | null;
  fall_days: number;
  recovery_days: number | null;
}

export interface Underwater extends Envelope {
  series: Point[];
  recovery: {
    depth: number;
    recovered: number;
    not_recovered: number;
    min_days: number | null;
    median_days: number | null;
    p90_days: number | null;
    max_days: number | null;
  }[];
  dd_now: number | null;
  dd_now_days: number | null;
  underwater_max_days: number | null;
}

export interface RankCell {
  rank: number;
  count: number;
  pct: number;
  quartile: number;
}

export interface RankHistory extends Envelope {
  group: { category: string; plan: string; option: string; funds_with_nav: number };
  history: { month: string; ret_1y: RankCell | null; cagr_3y: RankCell | null }[];
}

export interface DirectRegular extends Envelope {
  pair: Record<'direct' | 'regular', { amfi_code: string; name: string; ret_1y: number | null; cagr_3y: number | null; cagr_5y: number | null }> | null;
  dr_gap_1y: number | null;
  dr_gap_3y: number | null;
  dr_wealth_10y: number | null;
  label: string;
}

export interface NearDuplicates extends Envelope {
  count: number;
  state: Missing | null;
  listed: { amfi_code: string; name: string; correlation: number; common_days: number }[];
}

export interface RegimeWindow {
  start: string;
  end: string;
  kind: string;
  proxy_return: number;
  ongoing?: boolean;
}

export interface Regimes extends Envelope {
  proxy: { category: string; label: string; levels: Point[]; plan: string; option: string };
  windows: RegimeWindow[];
}

export interface FundRegimes extends Envelope {
  proxy_label: string;
  windows: (RegimeWindow & { fund_return: number | null; state: Missing | null; difference: number | null; capture: number | null })[];
}

export interface RiskFree extends Envelope {
  series: string;
  unit: string;
  points: Point[];
  method: string;
  acknowledgement: string;
}

export interface CompareResponse extends Envelope {
  start: string;
  funds: { plan_option_id: number; amfi_code: string; name: string; values: Metrics['values']; states: Metrics['states']; anchors: Record<string, string>; since_label: string }[];
  series: Record<string, Point[]>;
  correlations: { a: string; b: string; correlation: number | null; observations: number }[];
  average_correlation: number | null;
}

export interface Frontier extends Envelope {
  risk: string;
  return: string;
  points: { amfi_code: string; name: string; vol_3y: number; cagr_3y: number; downside_dev_3y: number | null; frontier: boolean }[];
}

export interface Transitions extends Envelope {
  group: { category: string; plan: string; option: string };
  funds_with_nav: number;
  counts: number[][];
  shares: (number | null)[][];
}

export interface BacktestPeriod {
  months: number;
  first_signal: string;
  last_signal: string;
  strategy_growth: number;
  median_growth: number;
  strategy_annualised: number;
  median_annualised: number;
  beat_share: number;
}

export interface Backtest extends Envelope {
  strategy: Record<string, string | number>;
  funds_with_nav: number;
  summary: { in_sample: BacktestPeriod | null; holdout: BacktestPeriod | null; whole: BacktestPeriod | null };
  regimes_spanned: RegimeWindow[];
  limits: string[];
  months: { signal_month: string; picks: string[]; strategy: number; median: number }[];
}

export type CalculatorKind = 'sip' | 'lumpsum' | 'swp' | 'stp';
export type TaxClass = 'equity' | 'debt' | 'other';

export interface CalculatorRequest {
  code: string;
  amount: number;
  day?: number;
  start: string;
  end?: string;
  step_up?: number;
  instalment?: number;
  target?: string;
  /** Omitted: the server takes the class from the fund's category, or asks for it. */
  tax_class?: TaxClass;
  slab_rate?: number;
  /** Pins the run to a saved snapshot instead of the latest. */
  data_revision?: number;
}

export interface Simulation extends Envelope {
  kind: CalculatorKind;
  codes: string[];
  summary: Record<string, number | string | null>;
  timeline: Record<string, number | string>[];
  tax: {
    rules: string;
    tax_class: string | null;
    total: number | null;
    years: { year: string; short_term: number; long_term: number; slab: number; tax: number }[];
    sales_not_modelled: number;
    reason: string | null;
  } | null;
  cautions: string[];
}

export interface RollingSipStart {
  start: string;
  end: string;
  invested: number;
  value: number;
  xirr: number | null;
  sip_drawdown: number | null;
}

export interface RollingSip extends Envelope {
  tenor: string;
  amount: number;
  summary: {
    starts: number;
    worst: RollingSipStart | null;
    best: RollingSipStart | null;
    median_xirr: number | null;
    positive_share: number | null;
    worst_sip_drawdown: number | null;
  };
  starts: RollingSipStart[];
}

/** A failed call: the HTTP status and the problem's title and detail. */
export class MfApiError extends Error {
  constructor(
    readonly status: number,
    readonly title: string,
    readonly detail: string,
  ) {
    super(detail || title || `HTTP ${status}`);
  }
}

async function problem(res: Response): Promise<MfApiError> {
  try {
    const body = await res.json();
    const detail = Array.isArray(body.detail)
      ? body.detail.map((d: { msg?: string }) => d.msg).join('; ')
      : String(body.detail ?? '');
    return new MfApiError(res.status, String(body.title ?? res.statusText), detail);
  } catch {
    return new MfApiError(res.status, res.statusText, '');
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${MF_API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!res.ok) throw await problem(res);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

/** Query string from defined values; arrays repeat the key (`code=a&code=b`). */
export function qs(params: Record<string, string | number | undefined | (string | number)[]>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue;
    for (const v of Array.isArray(value) ? value : [value]) search.append(key, String(v));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

const get = <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal });
const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body), signal });

export const mfApi = {
  fields: (signal?: AbortSignal) => get<FieldsResponse>('/screener/fields', signal),
  presets: (signal?: AbortSignal) => get<{ presets: Preset[] }>('/screener/presets', signal),
  screen: (body: ScreenRequest, signal?: AbortSignal) => post<ScreenResponse>('/screener/run', body, signal),
  search: (q: string, limit = 8, signal?: AbortSignal) =>
    get<Envelope & { funds: FundHit[] }>(`/funds${qs({ q, limit })}`, signal),
  sparklines: (codes: string[], signal?: AbortSignal) =>
    get<Envelope & { series: Record<string, Point[]> }>(`/funds/sparklines${qs({ code: codes })}`, signal),
  fund: (code: string, signal?: AbortSignal) => get<FundDetail>(`/funds/${code}`, signal),
  metrics: (code: string, signal?: AbortSignal, dataRevision?: number) =>
    get<Metrics>(`/funds/${code}/metrics${qs({ data_revision: dataRevision })}`, signal),
  score: (code: string, signal?: AbortSignal) => get<Score>(`/funds/${code}/score`, signal),
  confidence: (code: string, signal?: AbortSignal) => get<Confidence>(`/funds/${code}/confidence`, signal),
  navs: (code: string, start?: string, signal?: AbortSignal) =>
    get<Envelope & { navs: NavRow[] }>(`/funds/${code}/navs${qs({ start })}`, signal),
  annual: (code: string, signal?: AbortSignal) => get<Annual>(`/funds/${code}/annual`, signal),
  rolling: (code: string, window: '1y' | '3y' | '5y', signal?: AbortSignal) =>
    get<Envelope & { window: string; points: Point[] }>(`/funds/${code}/rolling${qs({ window })}`, signal),
  drawdowns: (code: string, top = 5, signal?: AbortSignal) =>
    get<Envelope & { drawdowns: Drawdown[] }>(`/funds/${code}/drawdowns${qs({ top })}`, signal),
  underwater: (code: string, signal?: AbortSignal) => get<Underwater>(`/funds/${code}/underwater`, signal),
  rankHistory: (code: string, signal?: AbortSignal) => get<RankHistory>(`/funds/${code}/rank-history`, signal),
  directRegular: (code: string, signal?: AbortSignal) => get<DirectRegular>(`/funds/${code}/direct-regular`, signal),
  nearDuplicates: (code: string, signal?: AbortSignal) => get<NearDuplicates>(`/funds/${code}/near-duplicates`, signal),
  fundRegimes: (code: string, signal?: AbortSignal) => get<FundRegimes>(`/funds/${code}/regimes`, signal),
  rollingSip: (code: string, p: { tenor: string; amount: number; day?: number; step_up?: number }, signal?: AbortSignal) =>
    get<RollingSip>(`/funds/${code}/rolling-sip${qs(p)}`, signal),
  profile: (code: string, signal?: AbortSignal) => get<FundProfile>(`/funds/${code}/profile`, signal),
  holdings: (code: string, asOf?: string, signal?: AbortSignal) => get<FundHoldings>(`/funds/${code}/holdings${qs({ as_of: asOf })}`, signal),
  overlap: (codes: string[], signal?: AbortSignal, dataRevision?: number) =>
    get<Overlap>(`/holdings/overlap${qs({ code: codes, data_revision: dataRevision })}`, signal),
  benchmark: (code: string, signal?: AbortSignal) => get<FundBenchmark>(`/funds/${code}/benchmark`, signal),
  regimes: (signal?: AbortSignal) => get<Regimes>('/regimes', signal),
  portfolio: (target?: string, signal?: AbortSignal) => get<PortfolioView>(`/portfolio${qs({ target })}`, signal),
  previewCas: (body: { pdf_base64: string; password: string }) => post<CasPreview>('/portfolio/preview', body),
  importCas: (body: { pdf_base64: string; password: string }) => post<CasImport>('/portfolio/imports', body),
  undoImport: (id: string) => request<void>(`/portfolio/imports/${id}`, { method: 'DELETE' }),
  riskFree: (signal?: AbortSignal) => get<RiskFree>('/risk-free', signal),
  compare: (codes: string[], start?: string, signal?: AbortSignal, dataRevision?: number) =>
    get<CompareResponse>(`/compare${qs({ code: codes, start, data_revision: dataRevision })}`, signal),
  frontier: (g: PeerGroup, signal?: AbortSignal) => get<Frontier>(`/peers/frontier${qs({ ...g })}`, signal),
  transitions: (g: PeerGroup, signal?: AbortSignal) => get<Transitions>(`/peers/transitions${qs({ ...g })}`, signal),
  backtest: (body: PeerGroup & { signal: 'ret_1y' | 'cagr_3y'; top: number }, signal?: AbortSignal) =>
    post<Backtest>('/backtests', body, signal),
  calculate: (kind: CalculatorKind, body: CalculatorRequest, signal?: AbortSignal) =>
    post<Simulation>(`/calculators/${kind}`, body, signal),
};

/** A dated value: `[date, value]`. TER and AUM rows hold only the dates the value changed. */
export type Dated<T = number> = [string, T];

/** AMFI's facts for one fund (doc 21 C14, C15): as filed, with their dates. */
export interface FundProfile extends Envelope {
  amfi_code: string;
  scheme: { sd_id: number; name: string } | null;
  reason?: string;
  plan?: 'regular' | 'direct';
  summary?: Record<string, string | number | null>;
  states?: Record<string, Missing>;
  document?: Record<string, { text: string; as_of: string } | null>;
  managers?: { name: string; since: string; years: number }[];
  ter?: Record<'regular' | 'direct', Dated[]>;
  ter_base?: Record<'regular' | 'direct', Dated[]>;
  aum_cr?: Dated[];
  riskometer?: Dated<string>[];
  /** Latest AMFI riskometer report date; distinct from the last value-change point. */
  riskometer_as_of?: string | null;
  /** IDCW payouts of this plan-option: record date, ₹ per unit. */
  idcw?: Dated[];
  source?: string;
  notes?: string[];
}

export interface BenchmarkRow {
  horizon: '1y' | '3y' | '5y' | '10y';
  fund: number | null;
  benchmark: number | string | null;
  excess: number | string | null;
  information_ratio: number | string | null;
}

/** AMFI's returns against the Tier 1 benchmark, and statistics against a labelled proxy (doc 21 C12). */
export interface FundBenchmark extends Envelope {
  amfi_code: string;
  scheme: { sd_id: number; name: string } | null;
  reason?: string;
  plan?: string;
  benchmark?: string | null;
  riskometer_benchmark?: string | null;
  official?: { as_of: string | null; rows: BenchmarkRow[]; history: Record<string, string | number | null>[]; source: string };
  proxy?: { benchmark: string; code: string; name: string; tracking_error: number | null; gap_3y: number | null } | null;
  proxy_stats?: Record<string, number | string | null>;
  states?: Record<string, Missing>;
  tracking_error_filed?: number | string | null;
  method?: string;
}

export interface HoldingLine {
  name: string;
  isin: string | null;
  industry: string | null;
  section: string;
  asset: 'equity' | 'debt' | 'cash' | 'derivative' | 'other';
  weight: number;
  value: number | null;
  cap: string | null;
}

export interface HoldingsSummary {
  as_of: string;
  count: number;
  weight_sum: number;
  reconciled: boolean;
  assets: Record<string, number>;
  top10_weight: number;
  effective_holdings: number | null;
  sectors: Record<string, number>;
  market_cap: Record<string, number>;
  ratings: Record<string, number>;
}

export interface WeightMove {
  name: string;
  isin: string | null;
  before: number;
  after: number;
  change: number;
}

/** A fund's monthly portfolio disclosure (doc 21 C16). */
export interface FundHoldings extends Envelope {
  amfi_code: string;
  scheme: { sd_id: number; name: string } | null;
  reason?: string;
  portfolio_as_of?: string;
  dates: string[];
  summary?: HoldingsSummary;
  lines?: HoldingLine[];
  changes?: Record<'added' | 'removed' | 'increased' | 'decreased', WeightMove[]> | null;
  previous_as_of?: string | null;
  trend?: Record<string, number | string | null>[];
  method?: string;
}

export interface OverlapPair {
  a: string;
  b: string;
  reason?: string;
  a_as_of?: string;
  b_as_of?: string;
  same_month?: boolean;
  common_count?: number;
  weighted_overlap?: number;
  sector_overlap?: number;
  common?: { name: string; isin: string | null; a: number; b: number }[];
}

export interface Overlap extends Envelope {
  funds: { code: string; name: string; as_of: string | null }[];
  pairs: OverlapPair[];
  method: string;
}

/** A CAS preview: what an import would add. Nothing is stored. */
export interface CasPreview {
  file_sha256: string;
  already_imported: boolean;
  period_from: string | null;
  period_to: string | null;
  cas_type: string;
  transactions: number;
  schemes: { scheme: string; folio: string; isin: string | null; amfi_code: string | null; known: boolean; closing_units: string; statement_value: string | null }[];
  warnings: string[];
}

export interface CasImport {
  id: string;
  file_sha256: string;
  period_from: string | null;
  period_to: string | null;
  cas_type: string;
  added: number;
  duplicates: number;
  closings: number;
  created_at: string;
  new?: boolean;
}

export interface PortfolioPosition {
  scheme: string;
  folio: string;
  code: string | null;
  isin: string | null;
  units: string;
  invested: number;
  withdrawn: number;
  value: number | null;
  xirr: number | null;
  reconciled: boolean | null;
  fund: { name: string; category: string; asset_class: string; plan: string; ter: number | null; score: number | null; nav_date: string | null; holdings: string | null } | null;
}

/** The caller's portfolio, valued with the research snapshot (Slice 6). */
export interface PortfolioView {
  imports: CasImport[];
  summary: {
    as_of: string;
    value: number;
    invested: number;
    withdrawn: number;
    gain: number;
    xirr: number | null;
    positions: number;
    unvalued: string[];
    allocation: Record<string, Record<string, number>>;
    costs: { weighted_ter: number | null; annual_cost: number; ter_coverage: number | null; regular_plan_share: number; direct_switch_saving: number };
    reconciliation: { checked: number; matched: number; gaps: { scheme: string; folio: string; ledger: string; statement: string }[] };
  };
  positions: PortfolioPosition[];
  look_through: { coverage: number; securities: { name: string; isin: string | null; weight: number; funds: string[] }[]; sectors: Record<string, number>; market_cap: Record<string, number> };
  overlaps: { a: string; b: string; weighted_overlap: number; common_count: number; same_month: boolean }[];
  alternatives: Record<string, { code: string; name: string; score: number | null; ter: number | null; cagr_3y: number | null; excess_3y: number | null }[]>;
  rebalance: { asset_class: string; current: number; target: number; trade: number }[] | null;
}

export interface PeerGroup {
  category: string;
  plan: string;
  option: string;
}
