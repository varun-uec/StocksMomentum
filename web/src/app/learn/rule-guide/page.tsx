'use client';

import { useQuery } from '@tanstack/react-query';
import { getStrategyDetail } from '@/lib/api-client';
import { PageHeader, LoadingSpinner, ErrorMessage, Badge } from '@/components/shared/Card';
import { Prose, SectionHeading } from '@/components/learn/MethodologyNote';
import type { EngineConfigDTO, RuleConfigDTO } from '@/lib/types';
import { focusRing } from '@/lib/theme';

interface RuleMeta {
  purpose: string;
  rationale: string;
  passExample: string;
  failExample: string;
}

const RULE_META: Record<string, RuleMeta> = {
  tt_close_above_sma150_200: {
    purpose: 'Confirms price is trading above both its intermediate and long-term trend.',
    rationale: 'A stock still below either average has not confirmed a Stage 2 shift.',
    passExample: 'Close ₹250, SMA150 ₹230, SMA200 ₹220 → passes.',
    failExample: 'Close ₹250, SMA150 ₹230, SMA200 ₹260 → fails (still below SMA200).',
  },
  tt_sma150_above_sma200: {
    purpose: 'Confirms the intermediate-term trend has overtaken the long-term trend.',
    rationale: 'This crossover is one of the clearest objective markers of a Stage 1→2 transition.',
    passExample: 'SMA150 ₹230 > SMA200 ₹220 → passes.',
    failExample: 'SMA150 ₹218 ≤ SMA200 ₹220 → fails (transition not yet confirmed).',
  },
  tt_sma200_uptrend: {
    purpose: 'Confirms the long-term average itself is rising, not just that price is above it.',
    rationale: 'A flat or falling 200-day average means the "uptrend" could be a temporary bounce within a longer downtrend.',
    passExample: 'SMA200 up 2% over the slope window → passes.',
    failExample: 'SMA200 flat or down over the slope window → fails.',
  },
  tt_sma_stack: {
    purpose: 'Confirms the full moving-average stack is in bullish order (50 above 150 and 200).',
    rationale: 'A properly stacked set of averages is the clearest visual signature of a healthy Stage 2 trend.',
    passExample: 'SMA50 ₹245 > SMA150 ₹230 and > SMA200 ₹220 → passes.',
    failExample: 'SMA50 ₹225 < SMA150 ₹230 → fails (short-term average has rolled under).',
  },
  tt_close_above_sma50: {
    purpose: 'Confirms short-term price action is still constructive, not just the longer averages.',
    rationale: 'Price below its own 50-day average often precedes a deeper pullback.',
    passExample: 'Close ₹250 > SMA50 ₹245 → passes.',
    failExample: 'Close ₹240 < SMA50 ₹245 → fails.',
  },
  tt_above_52w_low: {
    purpose: 'Confirms the stock has already moved meaningfully off its 52-week low.',
    rationale: 'A stock still hugging its lows has not demonstrated the strength Stage 2 requires, regardless of other signals.',
    passExample: 'Close is 40% above the 52-week low → passes (above the minimum).',
    failExample: 'Close is 10% above the 52-week low → fails — this is precisely the "near 52-week lows" case the methodology excludes.',
  },
  tt_near_52w_high: {
    purpose: 'Confirms the stock is trading near its highs, not in the middle or bottom of its range.',
    rationale: 'Genuine leaders make new highs; a stock far from its highs is not yet demonstrating leadership.',
    passExample: 'Close is 8% below the 52-week high → passes (within the maximum).',
    failExample: 'Close is 40% below the 52-week high → fails.',
  },
  tt_rs_rating_min: {
    purpose: 'Confirms the stock is outperforming the broader universe, not just rising in absolute terms.',
    rationale: 'A stock can rise while still lagging a strong market — that is not leadership.',
    passExample: 'RS rating 85 (top 15% of the universe) → passes.',
    failExample: 'RS rating 55 (below-median performance) → fails.',
  },
  rs_rating: {
    purpose: 'Scores the degree of relative outperformance, not just a pass/fail floor.',
    rationale: 'Among stocks that already clear the RS ≥ 70 gate, higher RS still indicates a stronger leader.',
    passExample: 'RS rating 99 → maximum contribution.',
    failExample: 'RS rating 70 (at the floor) → minimal contribution.',
  },
  rs_line_uptrend: {
    purpose: 'Confirms the RS line itself (price relative to the benchmark) is trending up, not just RS rating being high.',
    rationale: 'A high but declining RS rating can signal fading, not strengthening, leadership.',
    passExample: 'RS line slope positive over the lookback window → passes.',
    failExample: 'RS line rolling over even as RS rating remains elevated → fails.',
  },
  rs_sector_relative: {
    purpose: 'Confirms outperformance versus sector peers specifically, not just the whole market.',
    rationale: 'Sector leadership is often a leading indicator of stock-specific leadership.',
    passExample: 'Stock RS above the sector median → passes.',
    failExample: 'No sector classification available → rule cannot evaluate (data gap, not a fail).',
  },
  rs_industry_relative: {
    purpose: 'Confirms outperformance versus the narrower industry peer group.',
    rationale: 'Industry-level comparison is a finer-grained leadership signal than sector alone.',
    passExample: 'Stock RS above the industry median → passes.',
    failExample: 'No sector classification available → rule cannot evaluate (data gap, not a fail).',
  },
  vol_liquidity_min: {
    purpose: 'Enforces a minimum tradeable liquidity floor.',
    rationale: 'A stock too illiquid to enter or exit in size is not a viable candidate, regardless of its technical picture. This is a hard gate.',
    passExample: 'Estimated daily turnover ₹15 crore ≥ ₹1 crore minimum → passes.',
    failExample: 'Estimated daily turnover ₹0.4 crore → fails, excluded from ranking entirely.',
  },
  vol_accumulation_days: {
    purpose: 'Measures the net balance of institutional buying vs. selling days.',
    rationale: 'More accumulation than distribution days is direct tape evidence of institutional interest.',
    passExample: 'Net +6 accumulation days over the trailing 25 sessions → passes.',
    failExample: 'Net -3 (more distribution than accumulation) → fails.',
  },
  vol_breakout_confirm: {
    purpose: 'Confirms current volume is elevated enough to validate a breakout.',
    rationale: 'A breakout on light volume frequently fails; institutional-size buying shows up as volume expansion.',
    passExample: 'Relative volume 1.8x the 50-day average → passes.',
    failExample: 'Relative volume 0.9x average → fails (breakout unconfirmed).',
  },
  bo_pivot_breakout: {
    purpose: 'Measures how close the stock is to (or past) its breakout pivot.',
    rationale: 'Buying at the pivot, not deep into an extended move, is central to Minervini’s entry timing.',
    passExample: 'Close at 95% of the 20-day range → passes (at/near the highs).',
    failExample: 'Close at 45% of the 20-day range → fails (still mid-range).',
  },
  bo_followthrough: {
    purpose: 'Confirms short-term averages are aligning with the breakout, not diverging from it.',
    rationale: 'A breakout without short-term average follow-through often stalls.',
    passExample: 'SMA5 clearly above SMA10, tracking the breakout → passes.',
    failExample: 'SMA5 below SMA10 despite the breakout → fails.',
  },
  bo_false_breakout: {
    purpose: 'Flags breakouts that have already reversed back below the breakout day’s midpoint.',
    rationale: 'A same-day or next-day reversal below the midpoint is a classic false-breakout signature.',
    passExample: 'Close holds above the breakout day’s midpoint → passes.',
    failExample: 'Close slips back below the midpoint → fails.',
  },
  mq_trend_persistence: {
    purpose: 'Measures what fraction of the recent quarter the stock has spent above its 50-day average.',
    rationale: 'A persistent trend is more reliable than one that repeatedly whipsaws above and below its average.',
    passExample: 'Above SMA50 on 48 of the last 63 sessions (76%) → passes.',
    failExample: 'Above SMA50 on only 28 of 63 sessions (44%) → fails.',
  },
  mq_acceleration: {
    purpose: 'Compares recent (20-day) returns to the longer (63-day) trend to detect acceleration or deceleration.',
    rationale: 'A trend that is decelerating, even if technically intact, is a weaker momentum candidate than one still accelerating.',
    passExample: '20-day return 12% vs. 63-day return 18% (pace maintained) → strong contribution.',
    failExample: '20-day return 1% vs. 63-day return 60% (the move has already happened, now stalling) → minimal contribution.',
  },
  risk_extension: {
    purpose: 'Measures how far price has run above its 50-day average.',
    rationale: 'A stock extended too far above its average offers a poor risk/reward entry even if the trend is genuine.',
    passExample: 'Price 8% above SMA50 → passes (within range).',
    failExample: 'Price 35% above SMA50 → fails (over-extended).',
  },
  risk_atr: {
    purpose: 'Measures average daily volatility as a percentage of price (ADR%).',
    rationale: 'Excessive volatility makes position sizing and stop placement unreliable.',
    passExample: 'ADR% of 3.5% → passes (acceptable).',
    failExample: 'ADR% of 11% → fails (too volatile to size safely).',
  },
  risk_rr: {
    purpose: 'Estimates a reward-to-risk ratio from current structure.',
    rationale: 'A favourable reward-to-risk ratio is what makes a losing trade acceptable within a disciplined system.',
    passExample: 'Estimated ratio 2.8:1 → passes.',
    failExample: 'Estimated ratio 0.9:1 → fails (risk exceeds reward).',
  },
};

function ParamChips({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params);
  if (entries.length === 0) return <span className="text-slate-600">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([k, v]) => (
        <span
          key={k}
          className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded font-mono"
        >
          {k}={String(v)}
        </span>
      ))}
    </div>
  );
}

function EngineRuleTable({ engine }: { engine: EngineConfigDTO }) {
  if (engine.rules.length === 0) return null;
  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 capitalize">
          {engine.id.replace(/_/g, ' ')}
        </h3>
        {engine.gate && <Badge color="rose">Hard Gate Engine</Badge>}
        <span className="text-xs text-slate-500">weight {engine.weight}</span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {engine.rules.map((rule: RuleConfigDTO) => {
          const meta = RULE_META[rule.id];
          return (
            <div
              key={rule.id}
              className="rounded-xl border border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/40 p-4"
            >
              <div className="flex items-center justify-between mb-2 gap-2">
                <span className="font-mono text-sm text-slate-900 dark:text-slate-100 truncate">{rule.id}</span>
                <div className="flex items-center gap-2 shrink-0">
                  {rule.gate && <Badge color="rose">Gate</Badge>}
                  <span className="text-xs text-slate-500">weight {rule.weight}</span>
                </div>
              </div>
              <div className="mb-2">
                <span className="text-xs text-slate-500 mr-2">Live threshold/params:</span>
                <ParamChips params={rule.params} />
              </div>
              {meta ? (
                <div className="text-xs text-slate-600 dark:text-slate-400 space-y-1">
                  <p>
                    <span className="text-slate-500">Purpose: </span>
                    {meta.purpose}
                  </p>
                  <p>
                    <span className="text-slate-500">Rationale: </span>
                    {meta.rationale}
                  </p>
                  <p>
                    <span className="text-emerald-600 dark:text-emerald-400">Pass example: </span>
                    {meta.passExample}
                  </p>
                  <p>
                    <span className="text-rose-600 dark:text-rose-400">Fail example: </span>
                    {meta.failExample}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">Documentation pending for this rule.</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function RuleGuidePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['strategy-detail', 'minervini_trend_template'],
    queryFn: () => getStrategyDetail('minervini_trend_template'),
  });

  return (
    <div>
      <PageHeader
        title="Rule Guide"
        subtitle="Every rule the engine evaluates today, with its live threshold — pulled directly from the active strategy configuration"
      />
      <Prose>
        <p>
          This page cannot drift out of sync with the running engine: every threshold and weight
          below is fetched live from the active strategy configuration, not hardcoded into this
          page. If a threshold changes in the strategy config, it changes here too.
        </p>
      </Prose>

      {isLoading && <LoadingSpinner text="Loading live rule configuration…" />}
      {error && <ErrorMessage message="Could not load the active strategy configuration." />}

      {data && (
        <div className="mt-6">
          <SectionHeading>
            {data.name} <span className="text-slate-500 text-sm font-normal">v{data.version}</span>
          </SectionHeading>
          {data.config.engines
            .filter((e) => e.enabled)
            .map((engine) => (
              <EngineRuleTable key={engine.id} engine={engine} />
            ))}
        </div>
      )}
    </div>
  );
}
