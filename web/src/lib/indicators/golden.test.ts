/**
 * Golden check of the browser-side indicators against independent reference
 * values. The fixture comes from audit-evidence/audit-r3/ui/indicator_reference.py,
 * which uses no app code. Warm-up gaps must match too, not only the numbers.
 */
import assert from 'node:assert/strict';
import { test } from 'vitest';
import fixture from './golden-fixture.json';
import {
  atr, bollinger, donchian, ema, ichimoku, keltner, sma, wma, type Bar, type OverlaySeries,
} from './overlays';
import {
  atrPane, cci, chaikinMoneyFlow, directionalIndicators, displayMacd, moneyFlowIndex,
  obv, roc, rsi, stochastic, williamsR,
} from './oscillators';

const bars = fixture.bars as Bar[];
const want = fixture.expected as Record<string, (number | null)[]>;
const closes = bars.map((b) => b.close);

function same(name: string, got: (number | null)[], key: string): void {
  const ref = want[key];
  assert.equal(got.length, ref.length, `${name}: length`);
  ref.forEach((r, i) => {
    const g = got[i];
    if (r === null) return assert.equal(g, null, `${name}[${i}] should be warm-up null`);
    assert.notEqual(g, null, `${name}[${i}] is null, expected ${r}`);
    assert.ok(Math.abs(g! - r) <= 1e-9 * Math.max(1, Math.abs(r)), `${name}[${i}]: got ${g}, want ${r}`);
  });
}
const prices = (s: OverlaySeries, ): (number | null)[] => {
  const byDate = new Map(s.points.map((p) => [p.date, p.price]));
  return bars.map((b) => byDate.get(b.date) ?? null);
};

test('moving averages match reference', () => {
  same('sma20', sma(closes, 20), 'sma20');
  same('ema20', ema(closes, 20), 'ema20');
  same('wma20', wma(closes, 20), 'wma20');
});

test('overlays match reference', () => {
  const [bu, , bl] = bollinger(bars, {});
  same('bb upper', prices(bu), 'bb_upper');
  same('bb lower', prices(bl), 'bb_lower');
  same('keltner upper', prices(keltner(bars, {})[0]), 'keltner_upper');
  const [dh, , dl] = donchian(bars, {});
  same('donchian high', prices(dh), 'donchian_high20');
  same('donchian low', prices(dl), 'donchian_low20');
  const ich = ichimoku(bars, {});
  same('tenkan', prices(ich[0]), 'ichimoku_tenkan9');
  same('kijun', prices(ich[1]), 'ichimoku_kijun26');
});

test('oscillators match reference', () => {
  same('atr14', atr(bars, 14), 'atr14');
  same('atr%', atrPane(bars, {}).atr_pct, 'atr_pct14');
  same('rsi14', rsi(bars, 14), 'rsi14');
  const st = stochastic(bars, {});
  same('stoch k', st.stoch_k, 'stoch_k14');
  same('stoch d', st.stoch_d, 'stoch_d3');
  same('williams', williamsR(bars, {}).williams_r, 'williams14');
  same('cci', cci(bars, {}).cci, 'cci20');
  same('roc', roc(bars, {}).roc, 'roc12');
  same('obv', obv(bars).obv, 'obv');
  same('cmf', chaikinMoneyFlow(bars, {}).cmf, 'cmf20');
  same('mfi', moneyFlowIndex(bars, {}).mfi, 'mfi14');
  const di = directionalIndicators(bars, {});
  same('+di', di.plus_di, 'plus_di14');
  same('-di', di.minus_di, 'minus_di14');
  const m = displayMacd(bars, {});
  same('macd', m.display_macd, 'macd');
  same('macd signal', m.display_macd_signal, 'macd_signal');
  same('macd hist', m.display_macd_hist, 'macd_hist');
});
