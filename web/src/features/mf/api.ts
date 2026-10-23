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

export type Unit = 'fraction' | 'percentile' | 'count' | 'quartile' | 'rank' | 'days' | 'ratio' | 'INR' | null;
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
  tax_class: TaxClass;
  slab_rate?: number;
}

export interface Simulation extends Envelope {
  kind: CalculatorKind;
  codes: string[];
  summary: Record<string, number | string | null>;
  timeline: Record<string, number | string>[];
  tax: {
    rules: string;
    tax_class: string;
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
  return (await res.json()) as T;
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
  fund: (code: string, signal?: AbortSignal) => get<FundDetail>(`/funds/${code}`, signal),
  metrics: (code: string, signal?: AbortSignal) => get<Metrics>(`/funds/${code}/metrics`, signal),
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
  regimes: (signal?: AbortSignal) => get<Regimes>('/regimes', signal),
  riskFree: (signal?: AbortSignal) => get<RiskFree>('/risk-free', signal),
  compare: (codes: string[], start?: string, signal?: AbortSignal) =>
    get<CompareResponse>(`/compare${qs({ code: codes, start })}`, signal),
  frontier: (g: PeerGroup, signal?: AbortSignal) => get<Frontier>(`/peers/frontier${qs({ ...g })}`, signal),
  transitions: (g: PeerGroup, signal?: AbortSignal) => get<Transitions>(`/peers/transitions${qs({ ...g })}`, signal),
  backtest: (body: PeerGroup & { signal: 'ret_1y' | 'cagr_3y'; top: number }, signal?: AbortSignal) =>
    post<Backtest>('/backtests', body, signal),
  calculate: (kind: CalculatorKind, body: CalculatorRequest, signal?: AbortSignal) =>
    post<Simulation>(`/calculators/${kind}`, body, signal),
};

export interface PeerGroup {
  category: string;
  plan: string;
  option: string;
}
