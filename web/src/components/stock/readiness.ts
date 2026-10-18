import type { StockExplanation } from '@/lib/types';

// Setup quality, not a call to act: the platform publishes no buy/sell verdict.
export const QUALIFIED_LABEL = 'Qualified — all gates passed';

export function investmentReadiness(explanation: StockExplanation): { label: string; color: 'emerald' | 'amber' | 'rose' } {
  if (!explanation.overall_passed) {
    return { label: 'Not Qualified', color: 'rose' };
  }
  const buySetup = parseFloat(explanation.buy_setup_score);
  if (buySetup >= 60) {
    return { label: QUALIFIED_LABEL, color: 'emerald' };
  }
  return { label: 'Qualified — breakout not confirmed', color: 'amber' };
}
