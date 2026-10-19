import type { AlertDTO } from '@/lib/api-client';
import type { AdjustmentStepDTO } from '@/lib/types';
import { factorAt } from '@/lib/traded-prices';

/** Plot the same economic levels the authoritative EOD evaluator checks. */
export function alertPriceLevels(alerts: AlertDTO[], symbol: string, adjustments: AdjustmentStepDTO[]) {
  return alerts.filter((a) => a.symbol === symbol && a.status === 'active' && a.source === 'close').flatMap((a) => {
    if (!a.drawing) return [{ price: Number(a.threshold) * factorAt(adjustments, a.armed_after), title: `EOD #${a.id} ${a.condition.replaceAll('_', ' ')}` }];
    const bounds = a.drawing.points.map((p) => Number(p.price) * factorAt(adjustments, p.date)).sort((x, y) => x - y);
    return bounds.map((price, i) => ({ price, title: `EOD #${a.id} ${bounds.length > 1 ? (i ? 'zone high' : 'zone low') : a.condition.replaceAll('_', ' ')}` }));
  });
}
