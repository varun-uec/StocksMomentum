import type { AlertDTO } from '@/lib/api-client';
import type { AdjustmentStepDTO } from '@/lib/types';

export interface AlertEditorBasis { symbol: string; version: string }

/** A dirty value keeps the data version in which the owner entered it. */
export function alertBasisIsCurrent(basis: AlertEditorBasis | null, symbol: string, version?: string): boolean {
  return !!basis && basis.symbol === symbol && basis.version === version;
}

/** Multiply decimal strings and round half-even to the API's four-place limit. */
function multiplyThreshold(value: string, factor: string): string {
  const parts = (text: string) => {
    const [coefficient, exponent = '0'] = text.toLowerCase().split('e');
    const [whole, fraction = ''] = coefficient.split('.');
    return { units: BigInt(whole + fraction), scale: fraction.length - Number(exponent) };
  };
  const a = parts(value);
  const b = parts(factor);
  const product = a.units * b.units;
  const places = a.scale + b.scale;
  let rounded: bigint;
  if (places <= 4) rounded = product * 10n ** BigInt(4 - places);
  else {
    const divisor = 10n ** BigInt(places - 4);
    const magnitude = product < 0n ? -product : product;
    let quotient = magnitude / divisor;
    const remainder = magnitude % divisor;
    if (remainder * 2n > divisor || (remainder * 2n === divisor && quotient % 2n !== 0n)) quotient += 1n;
    rounded = product < 0n ? -quotient : quotient;
  }
  const digits = (rounded < 0n ? -rounded : rounded).toString().padStart(5, '0');
  const fraction = digits.slice(-4).replace(/0+$/, '');
  return `${rounded < 0n ? '-' : ''}${digits.slice(0, -4)}${fraction ? `.${fraction}` : ''}`;
}

/** Seed an explicit new arming decision in the current chart's price basis. */
export function alertEditThreshold(alert: Pick<AlertDTO, 'threshold' | 'source' | 'armed_after' | 'drawing'>, adjustments: AdjustmentStepDTO[]): string {
  // Detaching a captured drawing requires a new explicit numeric level.
  if (alert.drawing) return '';
  const step = adjustments.find((s) => alert.armed_after <= s.until) ?? adjustments.at(-1);
  const factor = ['rsi14', 'adx14'].includes(alert.source) ? '1' : step?.factor ?? '1';
  return multiplyThreshold(alert.threshold, factor);
}
