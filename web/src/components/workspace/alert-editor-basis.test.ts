import { expect, test } from 'vitest';
import { alertBasisIsCurrent, alertEditThreshold } from './alert-editor-basis';

const alert = { threshold: '0.1235', source: 'close' as const, armed_after: '2025-01-01', drawing: null };
const adjustments = [{ until: '2026-01-01', factor: '0.5' }];

test('a no-op edit after a split remains within the API precision and uses decimal half-even rounding', () => {
  expect(alertEditThreshold(alert, adjustments)).toBe('0.0618');
  expect(alertEditThreshold({ ...alert, threshold: '0.1233' }, adjustments)).toBe('0.0616');
  expect(alertEditThreshold({ ...alert, threshold: '-0.1235', source: 'macd_line' }, adjustments)).toBe('-0.0618');
  expect(alertEditThreshold({ ...alert, threshold: '100' }, [{ until: '2026-01-01', factor: '0.3333333333' }])).toBe('33.3333');
});

test('non-price studies retain their value and drawing detachment requires an explicit scalar level', () => {
  expect(alertEditThreshold({ ...alert, source: 'rsi14' }, adjustments)).toBe('0.1235');
  expect(alertEditThreshold({ ...alert, drawing: { id: 'ray', kind: 'horizontal', points: [{ date: '2025-01-01', price: '100' }], revision: 1 } }, adjustments)).toBe('');
});

test('a form basis cannot follow a refreshed hash or another symbol silently', () => {
  const captured = { symbol: 'ABC', version: '111111111111' };
  expect(alertBasisIsCurrent(captured, 'ABC', '111111111111')).toBe(true);
  expect(alertBasisIsCurrent(captured, 'ABC', '222222222222')).toBe(false);
  expect(alertBasisIsCurrent(captured, 'XYZ', '111111111111')).toBe(false);
  expect(alertBasisIsCurrent(captured, 'ABC', undefined)).toBe(false);
  expect(alertBasisIsCurrent(null, 'ABC', '111111111111')).toBe(false);
  expect(captured.version).toBe('111111111111');
});
