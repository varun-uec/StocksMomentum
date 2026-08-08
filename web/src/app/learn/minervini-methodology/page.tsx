import { PageHeader } from '@/components/shared/Card';
import { MethodologyNote, Prose, SectionHeading } from '@/components/learn/MethodologyNote';

export default function MinerviniMethodologyPage() {
  return (
    <div>
      <PageHeader
        title="Mark Minervini's Methodology"
        subtitle="The published framework Momentum25's screening engine implements"
      />

      <SectionHeading>Stage Analysis</SectionHeading>
      <Prose>
        <p>
          Minervini&rsquo;s framework (building on Stan Weinstein&rsquo;s earlier stage theory)
          divides a stock&rsquo;s life cycle into four stages:
        </p>
        <ul className="list-disc list-inside space-y-1.5 ml-2">
          <li>
            <span className="text-slate-900 dark:text-slate-200 font-medium">Stage 1 &mdash; Basing / Accumulation.</span>{' '}
            The stock has stopped declining and is trading sideways, typically below or around a
            flattening long-term moving average. Smart money is quietly accumulating; there is no
            trend to trade yet.
          </li>
          <li>
            <span className="text-slate-900 dark:text-slate-200 font-medium">Stage 2 &mdash; Advancing / Markup.</span>{' '}
            The stock breaks out of its base on rising volume, moving averages turn up and stack
            in bullish order, and the stock begins sustained outperformance. This is the only
            stage Minervini-style momentum investing seeks to buy into.
          </li>
          <li>
            <span className="text-slate-900 dark:text-slate-200 font-medium">Stage 3 &mdash; Topping / Distribution.</span>{' '}
            The advance loses momentum, price action becomes choppy and directionless near highs,
            and institutional selling begins to offset buying.
          </li>
          <li>
            <span className="text-slate-900 dark:text-slate-200 font-medium">Stage 4 &mdash; Declining / Markdown.</span>{' '}
            Moving averages turn down and stack in bearish order; the stock is in a downtrend.
          </li>
        </ul>
        <p>
          The entire purpose of the Trend Template below is to identify, as objectively as
          possible, whether a stock is currently in Stage 2 &mdash; and to exclude Stage 1, 3, and
          4 stocks even if they look statistically cheap or otherwise interesting.
        </p>
      </Prose>

      <SectionHeading>The Trend Template</SectionHeading>
      <Prose>
        <p>
          Minervini&rsquo;s Trend Template is an 8-point checklist used to confirm Stage 2. A
          stock must satisfy all 8 conditions simultaneously &mdash; there is no partial credit in
          the published methodology, and Momentum25 enforces this as a hard, all-or-nothing gate
          rather than a soft score.
        </p>
      </Prose>
      <MethodologyNote kind="published">
        The 8 conditions (price above the 150- and 200-day moving averages, 150-day average above
        the 200-day average, the 200-day average trending up for at least one month, 50-day
        average above both longer averages, price above the 50-day average, price at least 30%
        above its 52-week low, price within 25% of its 52-week high, and a Relative Strength
        rating of 70 or higher) are exactly as published by Minervini in <span className="italic">Trade
        Like a Stock Market Wizard</span>.
      </MethodologyNote>
      <MethodologyNote kind="implementation">
        Momentum25 implements each of these 8 conditions as an independent, named rule
        (<code className="text-xs bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">tt_*</code>) so every pass/fail
        can be explained individually rather than only as an opaque overall pass/fail. See the{' '}
        <span className="italic">Rule Guide</span> for the exact live thresholds in force today.
      </MethodologyNote>

      <SectionHeading>Relative Strength (RS)</SectionHeading>
      <Prose>
        <p>
          Relative Strength measures how a stock has performed versus the broader market (or its
          peers) over a defined lookback period, expressed as a percentile rank from 1 to 99 across
          the screened universe. An RS rating of 90 means the stock outperformed 90% of the
          universe. Minervini requires RS &ge; 70 as a floor for Stage 2 qualification, and looks
          for market leaders in the 80&ndash;99 range.
        </p>
      </Prose>
      <MethodologyNote kind="implementation">
        Momentum25 computes RS as a percentile rank of a blended multi-period return (the strategy
        config currently weights the 63-, 126-, 189- and 252-trading-day returns) rather than
        IBD&rsquo;s proprietary formula, which is not public. The blend and its weights are a
        documented approximation of the published concept, not the exact IBD calculation.
      </MethodologyNote>

      <SectionHeading>Institutional Accumulation</SectionHeading>
      <Prose>
        <p>
          Sustainable Stage 2 advances are driven by institutional buying, not retail speculation.
          Minervini looks for evidence of this in the tape: more up-volume days than down-volume
          days on above-average volume (accumulation), rising volume on breakouts, and the absence
          of heavy volume on declines (distribution).
        </p>
      </Prose>
      <MethodologyNote kind="implementation">
        Momentum25&rsquo;s Volume &amp; Accumulation engine counts net accumulation days (close
        &gt; open on above-average volume) minus distribution days (close &lt; open on
        above-average volume) over a trailing 25-session window, and separately confirms breakout
        volume via relative volume versus the 50-day average. A minimum average daily turnover
        floor (&#8377;1 crore) is also enforced as a hard liquidity gate, independent of the
        accumulation signal, so illiquid stocks cannot qualify regardless of how their volume
        pattern looks.
      </MethodologyNote>

      <SectionHeading>Constructive Bases</SectionHeading>
      <Prose>
        <p>
          Before breaking out, a genuine Stage 2 stock typically forms a recognizable
          &ldquo;base&rdquo; &mdash; a period of consolidation that resembles a Cup-with-Handle,
          a Volatility Contraction Pattern (VCP), a flat base, an ascending base, or a High Tight
          Flag. These patterns matter because they reflect an orderly transfer of shares from weak
          to strong hands rather than random noise.
        </p>
      </Prose>
      <MethodologyNote kind="implementation">
        Momentum25&rsquo;s Pattern Recognition engine runs deterministic detectors for all five of
        the patterns above against each stock&rsquo;s price history, scoring detected patterns by
        quality (tightness of the base, volume contraction, depth) rather than merely flagging
        their presence. A stock is not required to show a detected pattern to qualify (base
        formation is additive to the score, not gated), since not every genuine Stage 2 leader
        forms a textbook-clean base.
      </MethodologyNote>

      <SectionHeading>Breakout Philosophy</SectionHeading>
      <Prose>
        <p>
          Minervini buys breakouts at the &ldquo;pivot point&rdquo; &mdash; the exact price level
          where a stock clears the resistance defined by its base, ideally on volume at least 40
          &ndash;50% above average, confirming that the move has real conviction rather than being
          a low-volume false start.
        </p>
      </Prose>
      <MethodologyNote kind="implementation">
        Momentum25&rsquo;s Breakout engine evaluates how close the current close is to the top of
        its recent 20-day trading range (a proxy for pivot proximity), whether the 5- and 10-day
        moving averages confirm the move, and whether relative volume clears a 1.4x threshold
        (matching the ~40% volume-surge principle above). It also explicitly checks for false
        breakouts &mdash; a close back below the breakout day&rsquo;s midpoint.
      </MethodologyNote>

      <SectionHeading>Buy Zones</SectionHeading>
      <Prose>
        <p>
          Minervini defines a &ldquo;buy zone&rdquo; as roughly the pivot price up to 5% above it
          &mdash; buying meaningfully above this range increases risk because the stop-loss
          distance widens without a corresponding increase in the odds of success.
        </p>
      </Prose>
      <MethodologyNote kind="approximation">
        Momentum25 does not currently compute or display an explicit buy-zone price band on the
        dashboard. The Risk engine&rsquo;s extension check (how far price has run above its 50-day
        average) is a related but coarser signal, and the Buy Setup Score is designed to be
        highest near a fresh, volume-confirmed breakout. A dedicated buy-zone price range is a
        documented gap, not an implemented feature &mdash; see Remaining Limitations in the
        engineering review.
      </MethodologyNote>

      <SectionHeading>Risk Management</SectionHeading>
      <Prose>
        <p>
          Minervini is emphatic that risk management, not stock selection, is what separates
          professional momentum trading from speculation: cut losses quickly (typically 7&ndash;8%
          maximum), size positions so no single loss is catastrophic, and never average down into
          a losing position.
        </p>
      </Prose>
      <MethodologyNote kind="implementation">
        Momentum25&rsquo;s Risk engine evaluates extension above the 50-day average (flagging
        stocks that have already run too far to offer a favourable entry), average daily
        volatility via ADR%, and a minimum 2:1 reward-to-risk ratio estimate. Momentum25 is a
        research and screening tool: it does not place trades, size positions, or manage
        stop-losses &mdash; those remain the user&rsquo;s responsibility.
      </MethodologyNote>
    </div>
  );
}
