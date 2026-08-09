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
  weight: string;
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
  // Diagnostics over the momentum-SCORE series, not over returns. They carry
  // no profit meaning and must never be rendered with a % or profit colouring.
  max_momentum_score_drawdown: string;
  avg_pass_rate: string;
  avg_top_rank_stability: string;
  momentum_score_stability: string;
  momentum_score_downside_stability: string;
  momentum_score_gain_loss_ratio: string;
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
  security_count: number;
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

export interface DataFreshnessDTO {
  latest_bar_date: string | null;
  as_of: string;
  sessions_missed: number;
  classification: 'FRESH' | 'MARKET_CLOSED' | 'STALE';
  next_session: string | null;
  calendar_source: string;
}

export interface StrategySummary {
  id: number;
  name: string;
  description: string | null;
  version: number;
  is_active: boolean;
  kind: string;
  config_hash: string;
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
  kind: string;
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

/**
 * Whether a response's return-derived metrics could be computed at all.
 * `forward_returns_available: false` means every `null` metric on that
 * response is *unmeasured*, not *measured as zero*.
 */
export interface Measurability {
  forward_returns_available: boolean;
  reason: string | null;
}

export interface AlphaAnalysisResponse {
  strategy_name: string;
  strategy_id: number;
  period_label: string;
  start_date: string;
  end_date: string;
  comparisons: BenchmarkComparison[];
  best_alpha: string | null;
  worst_alpha: string | null;
  avg_alpha: string | null;
  measurability: Measurability;
}

export interface StrategyScorecard {
  strategy_name: string;
  strategy_id: number;
  period_label: string;
  start_date: string | null;
  end_date: string | null;
  total_trading_days: number;
  total_runs: number;
  // `null` = not measurable; see `measurability`. Never 0 as a stand-in.
  cagr: string | null;
  annual_return: string | null;
  cumulative_return: string | null;
  avg_holding_return: string | null;
  best_return: string | null;
  worst_return: string | null;
  win_rate: string | null;
  avg_winner: string | null;
  avg_loser: string | null;
  total_wins: number | null;
  total_losses: number | null;
  profit_factor: string | null;
  max_drawdown: string | null;
  max_drawdown_duration: number | null;
  volatility: string | null;
  downside_volatility: string | null;
  sharpe_ratio: string | null;
  sortino_ratio: string | null;
  calmar_ratio: string | null;
  information_ratio: string | null;
  alpha: string | null;
  beta: string | null;
  r_squared: string | null;
  avg_pass_rate: string;
  avg_momentum_score: string;
  avg_buy_setup_score: string;
  false_positive_rate: string | null;
  false_negative_rate: string | null;
  measurability: Measurability;
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
  contribution_to_successful: string | null;
  contribution_to_unsuccessful: string | null;
  avg_return_when_passes: string | null;
  avg_return_when_fails: string | null;
  return_delta: string | null;
  significance_score: string | null;
  // Return-derived verdicts. `null` = unmeasured, which is not the same as
  // `false` and must never drive a rule change (2026-08-09 audit S6).
  is_weak: boolean | null;
  is_redundant: boolean | null;
  is_high_value: boolean | null;
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
  measurability: Measurability;
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
  correlation_with_outcome: string | null;
  improves_performance: boolean | null;
  // Replaces `standalone_performance`, which published the run's average
  // momentum *score* as if it were a return (2026-08-09 audit §1.2.4/§2.3).
  avg_forward_return_when_engine_scores_high: string | null;
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
  measurability: Measurability;
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
  false_positive_rate: string | null;
  false_negative_rate: string | null;
}

// ── Phase 6: Live on-demand analysis, price series, watchlist ──────────

/** Every computed indicator, serialized as decimal strings by the backend. */
export interface IndicatorSnapshot {
  sma50: string | null;
  sma150: string | null;
  sma200: string | null;
  ema10: string | null;
  ema21: string | null;
  rsi14: string | null;
  atr14: string | null;
  adr_pct: string | null;
  high_52w: string | null;
  low_52w: string | null;
  pct_above_low_52w: string | null;
  pct_below_high_52w: string | null;
  sma200_slope_pct: string | null;
  rs_rating: string | null;
  rs_percentile: string | null;
  rs_line_slope: string | null;
  avg_volume50: string | null;
  rel_volume: string | null;
  adx14: string | null;
  plus_di14: string | null;
  minus_di14: string | null;
  macd_line: string | null;
  macd_signal: string | null;
  macd_histogram: string | null;
  // Phase 6.3 — signed % distance of the close from each key moving average.
  pct_from_sma50: string | null;
  pct_from_sma200: string | null;
  // Phase 6.4 — additional raw oscillators. Values only, no verdicts.
  stoch_k14: string | null;
  stoch_d14: string | null;
  williams_r14: string | null;
  cci20: string | null;
  roc12: string | null;
  [key: string]: string | null;
}

/** Phase 6.2 — stock vs benchmark-index performance over one lookback period. */
export interface RelativeStrengthPoint {
  period: '1m' | '3m' | '6m' | '12m';
  sessions: number;
  stock_return_pct: string | null;
  index_return_pct: string | null;
  excess_return_pct: string | null;
}

export interface StopLossSuggestion {
  level: string | null;
  method: string;
}

export interface LiveStockAnalysis {
  symbol: string;
  verdict: 'PASSED' | 'FAILED' | 'INDETERMINATE' | 'INSUFFICIENT_DATA';
  data_as_of: string;
  refreshed: boolean;
  bars_fetched: number;
  data_sufficient: boolean;
  explanation: StockExplanation | null;
  indeterminate_rules: string[];
  rs_basis: Record<string, unknown>;
  indicators: IndicatorSnapshot;
  suggested_stop: StopLossSuggestion | null;
  /** Phase 6.5 — trailing (chandelier) downside cap. Also not a target. */
  trailing_stop: StopLossSuggestion | null;
  /** Phase 6.2 — empty when the benchmark index has no ingested history. */
  relative_strength_vs_index: RelativeStrengthPoint[];
  benchmark_index: string | null;
}

// ── Phase 6.6 / 6.7: universe-level market context ─────────────────────

export interface MarketBreadth {
  as_of: string;
  evaluated: number;
  above_sma50: number;
  above_sma50_of: number;
  pct_above_sma50: string | null;
  above_sma200: number;
  above_sma200_of: number;
  pct_above_sma200: string | null;
  new_52w_highs: number;
  new_52w_lows: number;
  high_low_of: number;
}

export interface SectorRelativeStrength {
  sector: string;
  constituents: number;
  rank: number;
  /** Equal-weighted mean excess return per period, keyed '1m' | '3m' | '6m' | '12m'. */
  excess_return_pct: Record<string, string | null>;
}

export interface MarketContext {
  as_of: string;
  benchmark_index: string | null;
  breadth: MarketBreadth;
  sectors: SectorRelativeStrength[];
}

export interface OHLCVBarDTO {
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
}

export interface SecurityOHLCVDTO {
  symbol: string;
  bars: OHLCVBarDTO[];
}

export interface SecuritySearchResult {
  symbol: string;
  name: string;
  sector: string | null;
}

// ── Phase 9: per-bar indicator series (chart sub-panes) ─────────────────

export interface IndicatorSeriesBarDTO {
  date: string;
  /** Decimal-string values from the backend; null when undefined that bar. */
  rsi14: string | null;
  atr14: string | null;
  adx14: string | null;
  macd_line: string | null;
  macd_signal: string | null;
  macd_histogram: string | null;
}

export interface SecurityIndicatorSeriesDTO {
  symbol: string;
  bars: IndicatorSeriesBarDTO[];
}

export interface WatchlistResponse {
  symbols: string[];
}

/** One watchlisted symbol's momentum snapshot (GET /watchlist/detail). */
export interface WatchlistItemDTO {
  symbol: string;
  in_latest_run: boolean;
  momentum_score: string | null;
  buy_setup_score: string | null;
  rank: number | null;
  rank_change: number | null;
  rs_rating: number | null;
  pct_below_high_52w: string | null;
  close: string | null;
  change_pct: string | null;
}

export interface WatchlistDetailResponse {
  strategy: string;
  run_id: number | null;
  items: WatchlistItemDTO[];
}

// ── Phase 7: Elliott Wave labelling ────────────────────────────────────

export interface ElliottPivot {
  bar_date: string;
  price: string;
  kind: 'H' | 'L';
}

export interface ElliottWaveLabel {
  label: string;
  bar_date: string;
  price: string;
}

export interface ElliottProjectionZone {
  low: string;
  high: string;
  basis: string;
}

export interface ElliottSubdivision {
  of_label: string;
  degree: string;
  labels: ElliottWaveLabel[];
}

export interface ElliottWaveCount {
  pattern: 'impulse' | 'correction';
  direction: 'up' | 'down';
  degree: string;
  labels: ElliottWaveLabel[];
  current_position: string;
  rules_applied: string[];
  /** False when the count ends before the latest confirmed pivot (no projection). */
  is_current: boolean;
  projection: ElliottProjectionZone | null;
  subdivisions: ElliottSubdivision[];
}

export interface ElliottWaveAnalysis {
  symbol: string;
  as_of: string | null;
  threshold_pct: string;
  bars_analyzed: number;
  pivots: ElliottPivot[];
  primary: ElliottWaveCount | null;
  alternative: ElliottWaveCount | null;
  notes: string[];
}

// ── Phase 8: chart pattern recognition ─────────────────────────────────

export interface PatternCriterion {
  label: string;
  met: boolean;
  detail: string;
  required: boolean;
}

export interface PatternGeometryPoint {
  bar_date: string;
  price: string;
}

export interface PatternGeometryLine {
  name: string;
  points: PatternGeometryPoint[];
}

export interface DetectedPattern {
  pattern: string;
  display_name: string;
  starts_on: string;
  ends_on: string;
  /** Share of the pattern's criteria met, 0–100. Not a probability or a verdict. */
  completion_score: number;
  criteria: PatternCriterion[];
  geometry: PatternGeometryLine[];
}

export interface ChartPatternAnalysis {
  symbol: string;
  as_of: string | null;
  threshold_pct: string;
  bars_analyzed: number;
  pivots: ElliottPivot[];
  patterns: DetectedPattern[];
  notes: string[];
}
