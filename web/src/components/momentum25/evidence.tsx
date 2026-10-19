/**
 * "Show on chart" evidence layers and the legend chip (plan 2026-10-19,
 * workflow 2 and clarification C). A layer is page state for one chart: it is
 * drawn as its own series and never written to a document, so a reload or a
 * change of the chart's symbol clears it.
 */

import { useQuery } from '@tanstack/react-query';
import { getStockExplanation } from '@/lib/api-client';
import { focusRing } from '@/lib/theme';
import type { EvidenceLayer } from '@/components/stock/PriceChart';

/** The criteria whose evidence is a moving average the chart can draw. */
const RULE_SMAS: Record<string, number[]> = {
  tt_close_above_sma150_200: [150, 200],
  tt_sma150_above_sma200: [150, 200],
  tt_sma200_uptrend: [200],
  tt_sma_stack: [50, 150, 200],
  tt_close_above_sma50: [50],
};

export function evidenceLayer(ruleId: string): EvidenceLayer | null {
  const periods = RULE_SMAS[ruleId];
  return periods ? { id: ruleId, label: `SMA ${periods.join(' / ')}`, periods } : null;
}

/** What the page lends the Assessment: the active chart's layers and a toggle. */
export interface EvidenceControl {
  /** Layer ids shown on the active chart. */
  shown: string[];
  toggle: (layer: EvidenceLayer) => void;
  /** Other charts that show layers for this symbol, e.g. ['c2']. */
  elsewhere: string[];
}

/** "#3 · Qualified" when the symbol is in the run in view; nothing otherwise. Click opens the Assessment. */
export function LegendChip({ symbol, strategy, runId, onOpen }: { symbol: string; strategy: string; runId: number | undefined; onOpen: () => void }) {
  const { data } = useQuery({
    queryKey: ['stock-explanation', symbol, strategy, runId],
    queryFn: () => getStockExplanation(symbol, runId, strategy),
    enabled: runId !== undefined,
    retry: false,
  });
  if (!data) return null;
  const text = data.overall_passed && data.rank ? `#${data.rank} · Qualified` : 'Not qualified';
  return (
    <button type="button" onClick={onOpen} title="Open the Momentum25 assessment" className={`pointer-events-auto ml-2 px-1.5 rounded border border-[var(--ws-line)] text-[11px] font-medium hover:bg-[var(--ws-muted)] ${focusRing}`}>
      {text}
    </button>
  );
}
