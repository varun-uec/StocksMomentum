import type { AlertDTO } from '@/lib/api-client';
import type { AdjustmentStepDTO } from '@/lib/types';
import { SLOPED_KINDS } from '@/components/stock/chart-drawings';
import { factorAt } from '@/lib/traded-prices';

/**
 * Plot the same economic levels the authoritative EOD evaluator checks. A sloped
 * line alert has no single level; the drawing itself shows its line.
 */
export function alertPriceLevels(alerts: AlertDTO[], symbol: string, adjustments: AdjustmentStepDTO[]) {
  return alerts.filter((a) => a.symbol === symbol && a.status === 'active' && a.source === 'close' && !SLOPED_KINDS.has(a.drawing?.kind ?? '')).flatMap((a) => {
    if (!a.drawing) return [{ price: Number(a.threshold) * factorAt(adjustments, a.armed_after), title: `EOD #${a.id} ${a.condition.replaceAll('_', ' ')}` }];
    const bounds = a.drawing.points.map((p) => Number(p.price) * factorAt(adjustments, p.date)).sort((x, y) => x - y);
    return bounds.map((price, i) => ({ price, title: `EOD #${a.id} ${bounds.length > 1 ? (i ? 'zone high' : 'zone low') : a.condition.replaceAll('_', ' ')}` }));
  });
}
