import { PageHeader } from '@/components/shared/Card';
import { MethodologyNote, Prose, SectionHeading } from '@/components/learn/MethodologyNote';

export default function MomentumInvestingPage() {
  return (
    <div>
      <PageHeader title="Momentum Investing" subtitle="What it is, and why it keeps working" />

      <SectionHeading>What is momentum investing?</SectionHeading>
      <Prose>
        <p>
          Momentum investing buys stocks that are already rising in price and in relative strength
          versus the broader market, on the premise that a stock exhibiting strong, well-formed
          price momentum is statistically more likely to continue outperforming over the near term
          than a stock chosen at random or one that is falling. It is the opposite of
          &ldquo;buy low&rdquo; value investing: momentum investors buy strength and sell weakness,
          not the other way around.
        </p>
        <p>
          Concretely, this means favouring stocks that are: trading above their long-term moving
          averages, outperforming the index over multiple lookback windows, showing evidence of
          institutional buying (not just retail speculation), and structurally sound &mdash; i.e.
          building an orderly base rather than moving erratically.
        </p>
      </Prose>

      <SectionHeading>Why momentum works</SectionHeading>
      <Prose>
        <p>
          Momentum as a market anomaly is one of the most extensively documented in academic
          finance (Jegadeesh &amp; Titman, 1993, and a large body of subsequent research across
          multiple decades and markets, including India). Several structural explanations are
          commonly cited:
        </p>
        <ul className="list-disc list-inside space-y-1.5 ml-2">
          <li>
            <span className="text-slate-900 dark:text-slate-200 font-medium">Under-reaction to information.</span>{' '}
            Markets digest new information (earnings growth, sector tailwinds, management changes)
            gradually rather than instantly, so a trend that has started tends to persist as the
            market catches up to the new reality.
          </li>
          <li>
            <span className="text-slate-900 dark:text-slate-200 font-medium">Institutional accumulation takes time.</span>{' '}
            Large funds cannot build or exit a position in a single session without moving the
            price against themselves. Their buying (or selling) programs unfold over weeks to
            months, which shows up as a sustained trend rather than a single spike.
          </li>
          <li>
            <span className="text-slate-900 dark:text-slate-200 font-medium">Herding and confirmation.</span> As a
            trend becomes visible, it attracts further buying interest, reinforcing itself until
            the fundamental or technical picture changes.
          </li>
        </ul>
        <p>
          None of this means momentum works unconditionally or forever &mdash; trends end, and
          risk management (position sizing, stop-losses, and disciplined exits) is what separates
          professional momentum investing from simply chasing whatever went up yesterday.
        </p>
      </Prose>

      <SectionHeading>Momentum is time-dependent</SectionHeading>
      <Prose>
        <p>
          &ldquo;Momentum&rdquo; is not one single, universal concept &mdash; a stock with
          excellent 3-month momentum may have poor 2-year momentum, and vice versa. The lookback
          window you screen over determines what kind of momentum you find:
        </p>
      </Prose>
      <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700/60 mt-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 dark:bg-slate-800/90 border-b border-slate-200 dark:border-slate-700/60 text-slate-500 dark:text-slate-500 text-xs uppercase tracking-wider">
              <th scope="col" className="text-left py-3 px-3">Horizon</th>
              <th scope="col" className="text-left py-3 px-3">Captures</th>
              <th scope="col" className="text-left py-3 px-3">Typical use</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-700 dark:text-slate-300">
            <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
              <td className="py-3 px-3 font-medium text-slate-900 dark:text-slate-200">3 Months</td>
              <td className="py-3 px-3">Short-term breakouts, earnings-driven moves</td>
              <td className="py-3 px-3">Active swing trading</td>
            </tr>
            <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
              <td className="py-3 px-3 font-medium text-slate-900 dark:text-slate-200">6 Months</td>
              <td className="py-3 px-3">Established Stage 2 uptrends</td>
              <td className="py-3 px-3">Core momentum screening (default)</td>
            </tr>
            <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
              <td className="py-3 px-3 font-medium text-slate-900 dark:text-slate-200">1 Year</td>
              <td className="py-3 px-3">Full base-to-breakout cycles</td>
              <td className="py-3 px-3">Position trading</td>
            </tr>
            <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
              <td className="py-3 px-3 font-medium text-slate-900 dark:text-slate-200">2&ndash;5 Years</td>
              <td className="py-3 px-3">Multi-year secular leaders</td>
              <td className="py-3 px-3">Long-horizon research, thematic conviction</td>
            </tr>
          </tbody>
        </table>
      </div>
      <MethodologyNote kind="implementation">
        The dashboard&apos;s strategy selector runs the same deterministic methodology across each of
        these lookback windows as an independent strategy &mdash; each reuses the identical scoring
        engine with horizon-appropriate indicator windows, so results stay directly comparable
        across horizons. Only horizons with a completed screening run appear in the selector.
      </MethodologyNote>

      <SectionHeading>Momentum is not the same as volatility or speculation</SectionHeading>
      <Prose>
        <p>
          A common misconception is that momentum investing means chasing whatever is moving the
          fastest. In the Minervini tradition that Momentum25 implements, momentum specifically
          means <span className="text-slate-900 dark:text-slate-200">structured</span> strength: a stock in a
          confirmed uptrend, with a sound moving-average structure, adequate liquidity, and
          measured relative outperformance &mdash; not an erratic low-liquidity spike. The
          methodology explicitly filters out exactly the kind of high-volatility, low-structure
          moves that an inexperienced momentum trader might mistake for opportunity.
        </p>
      </Prose>
    </div>
  );
}
