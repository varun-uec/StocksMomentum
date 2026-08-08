/** Rule-level checklist returned by the backend explainability endpoint. */
export interface RuleResults {
  price_above_long_mas: boolean;
  ma150_above_ma200: boolean;
  ma200_trending_up: boolean;
  ma50_alignment: boolean;
  price_above_ma50: boolean;
  above_52w_low_30pct: boolean;
  within_52w_high_25pct: boolean;
  rs_rating_gte_70: boolean;
}

/** A single ranked stock row from the screening results API. */
export interface ScreeningResult {
  rank: number | null;
  security_id: number;
  symbol: string;
  close_price: string;
  momentum_score: string;
  buy_setup_score: string;
  rs_rating: string;
  metrics: {
    checklist: RuleResults;
  };
}

/** Execution summary for a screening run. */
export interface ScreeningRunSummary {
  total_evaluated: number;
  passed_count: number;
  failed_count: number;
  execution_duration_seconds: number;
}

/** Paginated API response wrapper. */
export interface RankingsResponse {
  run: {
    id: number;
    status: string;
    run_date: string;
    trigger: string;
    strategy: string;
    data_version: string;
    config_hash: string;
    started_at: string | null;
    finished_at: string | null;
    stats: Record<string, unknown> | null;
    error: string | null;
  } | null;
  items: RankingItemDTO[];
  total: number;
  limit: number;
  offset: number;
}

/** DTO returned by the rankings endpoint. */
export interface RankingItemDTO {
  rank: number;
  symbol: string;
  name: string;
  momentum_score: string;
  buy_setup_score: string;
  sector: string | null;
  rs_rating: number | null;
  explanation: Record<string, unknown> | null;
}

// ── Workspace 2: Stock Research ───────────────────────────────────────

export interface RuleExplanation {
  rule_id: string;
  engine_name: string;
  passed: boolean;
  explanation: string;
  threshold: string | null;
  actual_value: string | null;
  contribution: string;
}

export interface EngineExplanation {
  engine_name: string;
  passed: boolean;
  score: string;
  weight: string;
  contribution: string;
  rule_count: number;
  rules_passed: number;
  rules_failed: number;
  summary: string;
}

export interface StockExplanation {
  symbol: string;
  security_id: number;
  overall_passed: boolean;
  momentum_score: string;
  buy_setup_score: string;
  composite_score: string;
  rank: number | null;
  percentile: number | null;
  rule_explanations: RuleExplanation[];
  engine_explanations: EngineExplanation[];
  hard_filter_failures: string[];
  overall_rationale: string;
}

export interface ScorePoint {
  run_date: string;
  security_id: number;
  rank: number;
  momentum_score: string;
  buy_setup_score: string;
}

export interface StockHistoryResponse {
  symbol: string;
  score_history: ScorePoint[];
}

// ── Research DTOs ─────────────────────────────────────────────────────

export interface HistoricalScreeningRequest {
  strategy_name: string;
  as_of_date: string;
  symbol_filter: string[] | null;
}

export interface HistoricalScreeningResponse {
  run_id: number;
  run_date: string;
  total_evaluated: number;
  total_passed: number;
  total_failed: number;
  strategy_name: string;
}

export interface RankingComparison {
  security_id: number;
  symbol: string;
  rank_a: number | null;
  rank_b: number | null;
  rank_delta: number | null;
  direction: string | null;
}

export interface ScoreComparison {
  security_id: number;
  symbol: string;
  momentum_a: string | null;
  momentum_b: string | null;
  momentum_delta: string | null;
  buy_setup_a: string | null;
  buy_setup_b: string | null;
  buy_setup_delta: string | null;
}

export interface RuleComparison {
  security_id: number;
  symbol: string;
  rule_id: string;
  engine_id: string;
  passed_a: boolean;
  passed_b: boolean;
  changed: boolean;
}

export interface RunComparisonResponse {
  run_id_a: number;
  run_id_b: number;
  run_date_a: string;
  run_date_b: string;
  strategy_name: string;
  ranking_changed: boolean;
  score_changed: boolean;
  ranking_diffs: RankingComparison[];
  score_diffs: ScoreComparison[];
  rule_diffs: RuleComparison[];
  top_gainers: RankingComparison[];
  top_losers: RankingComparison[];
  is_identical: boolean;
}

export interface DeterminismVerificationResponse {
  run_id_a: number;
  run_id_b: number;
  is_deterministic: boolean;
  ranking_changed: boolean;
  score_changed: boolean;
  rule_diffs: number;
}

export interface HistoricalRunSummary {
  run_id: number;
  strategy_name: string;
  run_date: string;
  total_evaluated: number;
  total_passed: number;
  total_failed: number;
  data_version: string;
  config_hash: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface PortfolioPerformance {
  strategy_name: string;
  run_count: number;
  first_run_date: string | null;
  last_run_date: string | null;
  avg_momentum_score: string;
  median_momentum_score: string;
  avg_buy_setup_score: string;
  median_buy_setup_score: string;
  momentum_score_volatility: string;
  buy_setup_score_volatility: string;
  max_momentum_score: string;
  min_momentum_score: string;
  max_drawdown_pct: string;
  avg_pass_rate: string;
  avg_top_rank_stability: string;
  sharpe_ratio: string;
  sortino_ratio: string;
  profit_factor: string;
}

export interface ScoreDataPoint {
  run_date: string;
  security_id: number;
  rank: number;
  momentum_score: string;
  buy_setup_score: string;
}

export interface StrategyEvaluationResponse {
  strategy_name: string;
  performance: PortfolioPerformance;
  run_summaries: HistoricalRunSummary[];
  score_history: ScoreDataPoint[];
}

export interface RuleContributionStats {
  rule_id: string;
  engine_id: string;
  pass_count: number;
  fail_count: number;
  avg_contribution: string;
  total_contribution: string;
  importance_score: string;
  pass_rate: string;
  is_redundant: boolean;
}

export interface EngineContributionStats {
  engine_name: string;
  rule_count: number;
  avg_pass_rate: string;
  avg_importance: string;
  total_importance: string;
}

export interface ContributionAnalysisResponse {
  strategy_name: string;
  run_count: number;
  date_range: string | null;
  engine_stats: EngineContributionStats[];
  top_rules: RuleContributionStats[];
  bottom_rules: RuleContributionStats[];
  redundant_rules: RuleContributionStats[];
}

export interface StrategyComparisonPoint {
  security_id: number;
  symbol: string;
  rank_a: number | null;
  rank_b: number | null;
  momentum_a: string | null;
  momentum_b: string | null;
  buy_setup_a: string | null;
  buy_setup_b: string | null;
  agreement: boolean;
}

export interface StrategyComparisonResponse {
  strategy_a_name: string;
  strategy_b_name: string;
  total_comparisons: number;
  agreement_count: number;
  agreement_rate: string;
  a_wins: number;
  b_wins: number;
  comparisons: StrategyComparisonPoint[];
  rule_level_diffs: Record<string, unknown>[];
}

export interface ParameterOverride {
  parameter_path: string;
  value: string;
}

export interface ExperimentConfig {
  base_strategy_name: string;
  overrides: ParameterOverride[];
  run_dates: string[] | null;
  symbol_filter: string[] | null;
}

export interface ExperimentResult {
  variant_label: string;
  run_id: number;
  run_date: string;
  total_evaluated: number;
  total_passed: number;
  avg_momentum_score: string;
  avg_buy_setup_score: string;
}

export interface ExperimentResponse {
  base_strategy_name: string;
  variant_label: string;
  run_count: number;
  date_range: string | null;
  base_results: ExperimentResult[];
  variant_results: ExperimentResult[];
  avg_improvement: string;
  best_run_date: string | null;
  is_better: boolean;
  summary: string;
}

export interface RunDTO {
  id: number;
  status: string;
  run_date: string;
  trigger: string;
  strategy: string;
  data_version: string;
  config_hash: string;
  started_at: string | null;
  finished_at: string | null;
  stats: Record<string, unknown> | null;
  error: string | null;
}

export interface StrategySummary {
  name: string;
  description: string;
  version: string;
  is_active: boolean;
}

export interface RuleConfigDTO {
  id: string;
  weight: string;
  params: Record<string, unknown>;
  gate: boolean;
}

export interface EngineConfigDTO {
  id: string;
  enabled: boolean;
  weight: string;
  gate: boolean;
  rules: RuleConfigDTO[];
}

export interface StrategyDetailDTO {
  id: number;
  name: string;
  version: number;
  is_active: boolean;
  config_hash: string;
  description: string | null;
  config: {
    name: string;
    version: number;
    description: string | null;
    benchmark_index: string | null;
    universe: Record<string, unknown>;
    indicators: Record<string, unknown>;
    ranking: Record<string, unknown>;
    engines: EngineConfigDTO[];
    scoring: {
      momentum_weights: Record<string, string>;
      buy_setup_weights: Record<string, string>;
    };
  };
}

// ── Phase 6: Strategy Validation & Alpha Research ──────────────────────

export interface ValidationWindow {
  label: string;
  start_date: string;
  end_date: string;
  trading_days: number;
}

export interface HistoricalValidationResult {
  strategy_name: string;
  window: ValidationWindow;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  run_ids: number[];
  summary: Record<string, unknown>;
}

export interface HistoricalValidationResponse {
  strategy_name: string;
  strategy_id: number;
  windows: HistoricalValidationResult[];
  total_trading_days: number;
  total_successful_runs: number;
  overall_pass_rate: string;
  generated_at: string;
}

export interface BenchmarkComparison {
  benchmark_code: string;
  benchmark_name: string;
  strategy_return: string;
  benchmark_return: string;
  alpha: string;
  excess_return: string;
  relative_performance: string;
  annualized_return: string;
  benchmark_annualized_return: string;
  cagr: string;
  benchmark_cagr: string;
  rolling_returns: Record<string, unknown>[];
}

export interface AlphaAnalysisResponse {
  strategy_name: string;
  strategy_id: number;
  period_label: string;
  start_date: string;
  end_date: string;
  comparisons: BenchmarkComparison[];
  best_alpha: string;
  worst_alpha: string;
  avg_alpha: string;
}

export interface StrategyScorecard {
  strategy_name: string;
  strategy_id: number;
  period_label: string;
  start_date: string | null;
  end_date: string | null;
  total_trading_days: number;
  total_runs: number;
  cagr: string;
  annual_return: string;
  cumulative_return: string;
  avg_holding_return: string;
  best_return: string;
  worst_return: string;
  win_rate: string;
  avg_winner: string;
  avg_loser: string;
  total_wins: number;
  total_losses: number;
  profit_factor: string;
  max_drawdown: string;
  max_drawdown_duration: number;
  volatility: string;
  downside_volatility: string;
  sharpe_ratio: string;
  sortino_ratio: string;
  calmar_ratio: string;
  information_ratio: string;
  alpha: string;
  beta: string;
  r_squared: string;
  avg_pass_rate: string;
  avg_momentum_score: string;
  avg_buy_setup_score: string;
  false_positive_rate: string;
  false_negative_rate: string;
  monthly_returns: Record<string, unknown>[];
  yearly_returns: Record<string, unknown>[];
  rolling_sharpe: Record<string, unknown>[];
}

export interface RuleEffectiveness {
  rule_id: string;
  engine_id: string;
  rule_name: string;
  total_evaluations: number;
  pass_count: number;
  fail_count: number;
  pass_rate: string;
  contribution_to_successful: string;
  contribution_to_unsuccessful: string;
  avg_return_when_passes: string;
  avg_return_when_fails: string;
  return_delta: string;
  significance_score: string;
  is_weak: boolean;
  is_redundant: boolean;
  is_high_value: boolean;
}

export interface RuleEffectivenessResponse {
  strategy_name: string;
  strategy_id: number;
  total_runs_analyzed: number;
  date_range: string | null;
  rules: RuleEffectiveness[];
  weak_rules: RuleEffectiveness[];
  redundant_rules: RuleEffectiveness[];
  high_value_rules: RuleEffectiveness[];
  summary: string;
}

export interface EngineEffectiveness {
  engine_id: string;
  engine_name: string;
  total_evaluations: number;
  avg_score: string;
  avg_rules_passed: string;
  avg_rules_failed: string;
  avg_pass_rate: string;
  contribution_to_final_score: string;
  correlation_with_outcome: string;
  improves_performance: boolean;
  standalone_performance: string;
}

export interface EngineEffectivenessResponse {
  strategy_name: string;
  strategy_id: number;
  total_runs_analyzed: number;
  engines: EngineEffectiveness[];
  best_engine: string;
  worst_engine: string;
  recommended_exclusions: string[];
  summary: string;
}

// Note: ParameterOverride for Phase 5 experiments uses { parameter_path, value }
// ParameterOverride for Phase 6 validation experiments uses the extended form below

export interface ValidationParameterOverride {
  parameter_path: string;
  engine_id: string | null;
  rule_id: string | null;
  old_value: string | null;
  new_value: string;
}

export interface ParameterExperimentVariant {
  name: string;
  overrides: ValidationParameterOverride[];
}

export interface ParameterExperimentRequest {
  experiment_name: string;
  base_strategy_name: string;
  variants: ParameterExperimentVariant[];
  run_dates: string[] | null;
}

export interface ParameterExperimentResult {
  variant_name: string;
  run_count: number;
  avg_momentum_score: string;
  avg_buy_setup_score: string;
  avg_pass_rate: string;
}

export interface ParameterExperimentResponse {
  experiment_name: string;
  base_strategy_name: string;
  base_result: ParameterExperimentResult;
  variants: ParameterExperimentResult[];
  best_variant: string | null;
  best_improvement: string;
  parameter_sensitivity: Record<string, unknown>;
  summary: string;
}

export interface ResearchDashboardRequest {
  strategy_name: string;
  window_years: number;
}

export interface ResearchDashboardResponse {
  strategy_name: string;
  strategy_id: number;
  scorecard: StrategyScorecard | null;
  alpha_analysis: AlphaAnalysisResponse | null;
  rule_effectiveness: RuleEffectivenessResponse | null;
  engine_effectiveness: EngineEffectivenessResponse | null;
  historical_validation: HistoricalValidationResponse | null;
  ranking_stability: string;
  false_positive_rate: string;
  false_negative_rate: string;
}
