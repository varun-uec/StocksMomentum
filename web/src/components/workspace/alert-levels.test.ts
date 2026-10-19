import { expect, test } from 'vitest';
import type { AlertDTO } from '@/lib/api-client';
import { alertPriceLevels } from './alert-levels';
const alert: AlertDTO = { id: 1, symbol: 'ABC', source: 'close', interval: '1D', condition: 'crosses_above', threshold: '100', armed_after: '2025-01-01', status: 'active', triggered_on: null, trigger_value: null, data_version: null, seen: true, created_at: null, revision: 1, drawing: null };
const adjustments = [{ until: '2025-06-30', factor: '0.5' }, { until: '2026-12-31', factor: '1' }];
test('price levels follow a subsequent bonus in the same basis as the evaluator', () => {
  expect(alertPriceLevels([alert], 'ABC', adjustments)).toEqual([{ price: 50, title: 'EOD #1 crosses above' }]);
});
test('mixed-date zone anchors are adjusted individually before ordering low and high', () => {
  const zone: AlertDTO = { ...alert, condition: 'leaves_zone', drawing: { id: 'zone', kind: 'rectangle', revision: 3, points: [{ date: '2025-07-01', price: '75' }, { date: '2025-01-01', price: '100' }] } };
  expect(alertPriceLevels([zone], 'ABC', adjustments)).toEqual([{ price: 50, title: 'EOD #1 zone low' }, { price: 75, title: 'EOD #1 zone high' }]);
});
test('triggered, indicator and other-symbol alerts never become armed price lines', () => {
  expect(alertPriceLevels([{ ...alert, status: 'triggered' }, { ...alert, source: 'rsi14' }, { ...alert, symbol: 'XYZ' }], 'ABC', adjustments)).toEqual([]);
});
