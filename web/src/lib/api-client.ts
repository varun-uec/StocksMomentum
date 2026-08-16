/** Typed API client for Momentum25 backend. */
import type {
  RankingsResponse,
  StockExplanation,
  StockHistoryResponse,
  RunComparisonResponse,
  DeterminismVerificationResponse,
  StrategyEvaluationResponse,
  ContributionAnalysisResponse,
  StrategyComparisonResponse,
  ExperimentConfig,
  ExperimentResponse,
  HistoricalScreeningRequest,
  HistoricalScreeningResponse,
  RunDTO,
  StrategySummary,
  DataFreshnessDTO,
  Exchange,
  RefreshMarketDataResponse,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000/api/v1';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error');
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Runs ──────────────────────────────────────────────────────────────

/**
 * The API emits run status uppercase ("COMPLETED"), and every consumer must
 * agree on that. /analytics keyed off `statusCounts['completed']` and rendered
 * a permanent "Completed Runs 0" directly above a pie chart reading
 * "COMPLETED: 2" (2026-08-09 audit §1.2.7). Normalising once here, at the only
 * boundary the API crosses, means no page has to remember the convention.
 */
function normalizeRun<T extends { status: string }>(run: T): T {
  return { ...run, status: run.status.toUpperCase() };
}

function normalizeRunPage(page: { items: RunDTO[]; total: number }): {
  items: RunDTO[];
  total: number;
} {
  return { ...page, items: page.items.map(normalizeRun) };
}

export async function getLatestCompletedRun(): Promise<RunDTO | null> {
  const data = await fetchJson<{ items: RunDTO[]; total: number }>(
    `${API_BASE}/runs?status=completed&limit=1`,
    { cache: 'no-store' }
  );
  return data.items.length > 0 ? normalizeRun(data.items[0]) : null;
}

export async function getLatestRunForStrategy(strategy: string): Promise<RunDTO | null> {
  const run = await fetchJson<RunDTO | null>(
    `${API_BASE}/runs/latest?strategy=${encodeURIComponent(strategy)}`,
    { cache: 'no-store' }
  );
  return run ? normalizeRun(run) : null;
}

export async function getDataFreshness(): Promise<DataFreshnessDTO> {
  return fetchJson(`${API_BASE}/health/data-freshness`, { cache: 'no-store' });
}

export async function getRuns(
  status?: string,
  limit = 50,
  offset = 0
): Promise<{ items: RunDTO[]; total: number }> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return normalizeRunPage(
    await fetchJson<{ items: RunDTO[]; total: number }>(`${API_BASE}/runs?${params}`, {
      cache: 'no-store',
    })
  );
}

export async function getRun(runId: number): Promise<RunDTO> {
  return normalizeRun(await fetchJson<RunDTO>(`${API_BASE}/runs/${runId}`, { cache: 'no-store' }));
}

export async function executeScreening(
  strategy: string,
  force = false
): Promise<RunDTO> {
  return fetchJson(`${API_BASE}/runs/execute`, {
    method: 'POST',
    body: JSON.stringify({ strategy, force, background: true }),
  });
}

// ── Market data ───────────────────────────────────────────────────────

/**
 * Ingest the latest completed trading session. Synchronous: the response is
 * the finished summary, so there is nothing to poll. It does not start a
 * screening run.
 */
export async function refreshLatestMarketData(
  exchanges: Exchange[]
): Promise<RefreshMarketDataResponse> {
  return fetchJson(`${API_BASE}/market-data/refresh`, {
    method: 'POST',
    body: JSON.stringify({ exchanges }),
  });
}

// ── Rankings ──────────────────────────────────────────────────────────

export async function getRankings(
  runId: number,
  limit = 50,
  offset = 0
): Promise<RankingsResponse> {
  return fetchJson(
    `${API_BASE}/rankings/runs/${runId}?limit=${limit}&offset=${offset}`,
    { cache: 'no-store' }
  );
}

// ── Stocks — Explainability & History ─────────────────────────────────

export async function getStockExplanation(
  symbol: string,
  runId?: number,
  strategy = 'minervini_trend_template'
): Promise<StockExplanation> {
  const params = new URLSearchParams({ strategy });
  if (runId) params.set('run_id', String(runId));
  return fetchJson(`${API_BASE}/stocks/${symbol}?${params}`, { cache: 'no-store' });
}

export async function getStockHistory(
  symbol: string,
  strategy = 'minervini_trend_template',
  limit = 90
): Promise<StockHistoryResponse> {
  return fetchJson(
    `${API_BASE}/stocks/${symbol}/history?strategy=${strategy}&limit=${limit}`,
    { cache: 'no-store' }
  );
}

// ── Strategies ────────────────────────────────────────────────────────

export async function listStrategies(withRuns = false): Promise<StrategySummary[]> {
  const params = withRuns ? '?with_runs=true' : '';
  return fetchJson(`${API_BASE}/strategies${params}`, { cache: 'no-store' });
}

export async function getStrategyDetail(
  name: string
): Promise<import('./types').StrategyDetailDTO> {
  return fetchJson(`${API_BASE}/strategies/${name}`, { cache: 'no-store' });
}

// ── Research: Historical Replay ───────────────────────────────────────

export async function historicalScreen(
  body: HistoricalScreeningRequest
): Promise<HistoricalScreeningResponse> {
  return fetchJson(`${API_BASE}/research/historical/screen`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ── Research: Run Comparison ──────────────────────────────────────────

export async function compareRuns(
  runIdA: number,
  runIdB: number
): Promise<RunComparisonResponse> {
  return fetchJson(
    `${API_BASE}/research/compare/runs?run_id_a=${runIdA}&run_id_b=${runIdB}`,
    { method: 'POST' }
  );
}

export async function verifyDeterminism(
  asOfDate: string,
  strategyName = 'minervini_trend_template'
): Promise<DeterminismVerificationResponse> {
  return fetchJson(
    `${API_BASE}/research/verify/determinism?as_of_date=${asOfDate}&strategy_name=${strategyName}`,
    { method: 'POST' }
  );
}

// ── Research: Strategy Evaluation ─────────────────────────────────────

export async function evaluateStrategy(
  strategyName: string,
  maxRuns = 50,
  dateFrom?: string,
  dateTo?: string
): Promise<StrategyEvaluationResponse> {
  const params = new URLSearchParams();
  params.set('max_runs', String(maxRuns));
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  return fetchJson(
    `${API_BASE}/research/evaluate/${strategyName}?${params}`,
    { cache: 'no-store' }
  );
}

// ── Research: Contribution Analysis ───────────────────────────────────

export async function getContributionAnalysis(
  strategyName: string,
  maxRuns = 20
): Promise<ContributionAnalysisResponse> {
  return fetchJson(
    `${API_BASE}/research/contribution/${strategyName}?max_runs=${maxRuns}`,
    { cache: 'no-store' }
  );
}

// ── Research: Strategy Comparison ─────────────────────────────────────

export async function compareStrategies(
  strategyA: string,
  strategyB: string,
  maxRuns = 20
): Promise<StrategyComparisonResponse> {
  return fetchJson(
    `${API_BASE}/research/compare/strategies?strategy_a=${strategyA}&strategy_b=${strategyB}&max_runs=${maxRuns}`,
    { cache: 'no-store' }
  );
}

// ── Research: Experiment Laboratory ───────────────────────────────────

export async function runExperiment(
  config: ExperimentConfig
): Promise<ExperimentResponse> {
  return fetchJson(`${API_BASE}/research/experiment/run`, {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

// ── Phase 6: Strategy Validation & Alpha Research ──────────────────────

export async function getHistoricalValidation(
  strategyName: string,
  windowYears = 1
): Promise<import('./types').HistoricalValidationResponse> {
  return fetchJson(
    `${API_BASE}/validation/historical/${strategyName}?window_years=${windowYears}`,
    { cache: 'no-store' }
  );
}

export async function getAlphaAnalysis(
  strategyName: string,
  maxRuns = 252
): Promise<import('./types').AlphaAnalysisResponse> {
  return fetchJson(
    `${API_BASE}/validation/alpha/${strategyName}?max_runs=${maxRuns}`,
    { cache: 'no-store' }
  );
}

export async function getStrategyScorecard(
  strategyName: string,
  maxRuns = 252,
  dateFrom?: string,
  dateTo?: string
): Promise<import('./types').StrategyScorecard> {
  const params = new URLSearchParams();
  params.set('max_runs', String(maxRuns));
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  return fetchJson(
    `${API_BASE}/validation/scorecard/${strategyName}?${params}`,
    { cache: 'no-store' }
  );
}

export async function getRuleEffectiveness(
  strategyName: string,
  maxRuns = 100
): Promise<import('./types').RuleEffectivenessResponse> {
  return fetchJson(
    `${API_BASE}/validation/rules/${strategyName}?max_runs=${maxRuns}`,
    { cache: 'no-store' }
  );
}

export async function getEngineEffectiveness(
  strategyName: string,
  maxRuns = 100
): Promise<import('./types').EngineEffectivenessResponse> {
  return fetchJson(
    `${API_BASE}/validation/engines/${strategyName}?max_runs=${maxRuns}`,
    { cache: 'no-store' }
  );
}

export async function runParameterExperiment(
  body: import('./types').ParameterExperimentRequest
): Promise<import('./types').ParameterExperimentResponse> {
  return fetchJson(`${API_BASE}/validation/experiment/run`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getResearchDashboard(
  body: import('./types').ResearchDashboardRequest
): Promise<import('./types').ResearchDashboardResponse> {
  return fetchJson(`${API_BASE}/validation/dashboard`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ── Phase 6: Live analysis, price series, watchlist ────────────────────

export async function getLiveStockAnalysis(
  symbol: string,
  refresh = false,
  strategy = 'minervini_trend_template'
): Promise<import('./types').LiveStockAnalysis> {
  const params = new URLSearchParams({ strategy, refresh: String(refresh) });
  return fetchJson(`${API_BASE}/stocks/${symbol}/live?${params}`, { cache: 'no-store' });
}

export async function getOhlcv(
  symbol: string,
  from?: string,
  to?: string
): Promise<import('./types').SecurityOHLCVDTO> {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  return fetchJson(`${API_BASE}/securities/${symbol}/ohlcv?${params}`, { cache: 'no-store' });
}

/** Daily closes for a benchmark index (e.g. NIFTY500), for chart overlays. */
export async function getIndexCloses(
  indexCode: string,
  from?: string,
  to?: string
): Promise<import('./types').IndexClosesDTO> {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  return fetchJson(`${API_BASE}/indices/${indexCode}/closes?${params}`, { cache: 'no-store' });
}

/** Symbol/company-name typeahead for the nav lookup. */
export async function searchSecurities(
  q: string,
  limit = 8,
  signal?: AbortSignal
): Promise<import('./types').SecuritySearchResult[]> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return fetchJson(`${API_BASE}/securities?${params}`, { cache: 'no-store', signal });
}

/** Universe-level breadth and sector relative strength (Phase 6.6/6.7). */
export async function getMarketContext(
  asOf?: string
): Promise<import('./types').MarketContext> {
  const params = new URLSearchParams();
  if (asOf) params.set('as_of', asOf);
  return fetchJson(`${API_BASE}/market/context?${params}`, { cache: 'no-store' });
}

export async function getWatchlist(): Promise<import('./types').WatchlistResponse> {
  return fetchJson(`${API_BASE}/watchlist`, { cache: 'no-store' });
}

/**
 * Enriched watchlist rows for one strategy, evaluated server-side in a
 * single request (no per-row client fan-out).
 */
export async function getWatchlistDetail(
  strategy: string
): Promise<import('./types').WatchlistDetailResponse> {
  const params = new URLSearchParams({ strategy });
  return fetchJson(`${API_BASE}/watchlist/detail?${params}`, { cache: 'no-store' });
}

export async function addToWatchlist(
  symbol: string
): Promise<import('./types').WatchlistResponse> {
  return fetchJson(`${API_BASE}/watchlist/${symbol}`, { method: 'POST' });
}

export async function removeFromWatchlist(
  symbol: string
): Promise<import('./types').WatchlistResponse> {
  return fetchJson(`${API_BASE}/watchlist/${symbol}`, { method: 'DELETE' });
}

/**
 * Elliott Wave labelling of the stored price history.
 *
 * `thresholdPct` is the finest degree to label; the backend coarsens the top
 * degree away from it. `strategy` selects whose indicator configuration the
 * wave-personality checks read, matching the chart's indicator panes.
 */
export async function getElliottWave(
  symbol: string,
  lookbackDays: number,
  thresholdPct: number,
  strategy: string
): Promise<import('./types').ElliottWaveAnalysis> {
  const params = new URLSearchParams({
    lookback_days: String(lookbackDays),
    threshold_pct: String(thresholdPct),
    strategy,
  });
  return fetchJson(`${API_BASE}/stocks/${symbol}/elliott-wave?${params}`, { cache: 'no-store' });
}

/**
 * Phase 9 — per-bar indicator series for the chart sub-panes (RSI/ATR/ADX/MACD).
 * The series is produced by the same indicator functions as `/live`, so its last
 * bar is always the live endpoint's latest values.
 */
export async function getIndicatorSeries(
  symbol: string,
  strategy = 'minervini_trend_template'
): Promise<import('./types').SecurityIndicatorSeriesDTO> {
  const params = new URLSearchParams({ strategy });
  return fetchJson(`${API_BASE}/stocks/${symbol}/indicators/series?${params}`, {
    cache: 'no-store',
  });
}

/**
 * Phase 8 — chart-pattern detection. Explicitly user-triggered: this is a POST
 * that runs only when the user asks for it, never on page load.
 */
export async function detectChartPatterns(
  symbol: string,
  lookbackDays: number,
  thresholdPct: number
): Promise<import('./types').ChartPatternAnalysis> {
  const params = new URLSearchParams({
    lookback_days: String(lookbackDays),
    threshold_pct: String(thresholdPct),
  });
  return fetchJson(`${API_BASE}/stocks/${symbol}/chart-patterns?${params}`, {
    method: 'POST',
    cache: 'no-store',
  });
}
