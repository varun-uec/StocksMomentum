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

export async function getLatestCompletedRun(): Promise<RunDTO | null> {
  const data = await fetchJson<{ items: RunDTO[]; total: number }>(
    `${API_BASE}/runs?status=completed&limit=1`,
    { cache: 'no-store' }
  );
  return data.items.length > 0 ? data.items[0] : null;
}

export async function getLatestRunForStrategy(strategy: string): Promise<RunDTO | null> {
  return fetchJson(`${API_BASE}/runs/latest?strategy=${encodeURIComponent(strategy)}`, {
    cache: 'no-store',
  });
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
  return fetchJson(`${API_BASE}/runs?${params}`, { cache: 'no-store' });
}

export async function getRun(runId: number): Promise<RunDTO> {
  return fetchJson(`${API_BASE}/runs/${runId}`, { cache: 'no-store' });
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

export async function listStrategies(): Promise<StrategySummary[]> {
  return fetchJson(`${API_BASE}/strategies`, { cache: 'no-store' });
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
