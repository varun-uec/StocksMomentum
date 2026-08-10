/**
 * The indicator catalogue.
 *
 * One entry per indicator: its id, label, parameters, and how it is drawn —
 * either as price-pane lines (`overlay`) or as a sub-pane (`pane` + `compute`).
 * The picker, the legend and the stored-preference validator all render from
 * this array, so adding an indicator is one entry and nothing else.
 *
 * `source` records where the numbers come from. `backend` panes read the
 * per-bar series the API already returns; `browser` entries are arithmetic on
 * the displayed bars. Nothing is invented and nothing is fetched here.
 */

import { PANE_DEFS, type PaneDef } from '@/components/stock/PriceChart';
import * as osc from '@/lib/indicators/oscillators';
import * as ov from '@/lib/indicators/overlays';
import type { Bar, OverlaySeries, Params } from '@/lib/indicators/overlays';

export type { Bar, OverlaySeries, Params };

export interface IndicatorParamDef {
  key: string;
  label: string;
  type: 'number' | 'date' | 'select';
  default: number | string;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: string; label: string }[];
}

/** Extra inputs a compute function may need beyond the symbol's own bars. */
export interface IndicatorContext {
  benchmark: Bar[];
}

export interface IndicatorDef {
  id: string;
  label: string;
  group: string;
  kind: 'overlay' | 'pane';
  source: 'backend' | 'browser';
  params: IndicatorParamDef[];
  note?: string;
  /** Price-pane lines. */
  overlay?: (bars: Bar[], params: Params) => OverlaySeries[];
  /** Sub-pane shape; series keys must match what `compute` returns. */
  pane?: PaneDef;
  /** Absent for backend-fed panes: the API already supplies those fields. */
  compute?: (bars: Bar[], params: Params, ctx: IndicatorContext) => osc.PaneValues;
  /** True when several instances with different parameters make sense. */
  repeatable?: boolean;
}

const p = (
  key: string,
  label: string,
  def: number,
  min = 1,
  max = 500,
  step = 1
): IndicatorParamDef => ({ key, label, type: 'number', default: def, min, max, step });

const GUIDE = (value: number) => ({ value });

const backendPane = (id: string, label: string, note: string): IndicatorDef => {
  const def = PANE_DEFS.find((d) => d.id === id);
  if (!def) throw new Error(`No PaneDef registered for '${id}'`);
  return { id, label, group: 'Backend panes', kind: 'pane', source: 'backend', params: [], note, pane: def };
};

export const INDICATORS: IndicatorDef[] = [
  // ── Price-pane overlays ──────────────────────────────────────────────
  {
    id: 'sma',
    label: 'SMA (custom period)',
    group: 'Moving averages',
    kind: 'overlay',
    source: 'browser',
    repeatable: true,
    note: 'Add a custom SMA — 50 and 200 are already on via Quick MAs above.',
    params: [p('period', 'Period', 20)],
    overlay: ov.smaOverlay,
  },
  {
    id: 'ema',
    label: 'EMA (custom period)',
    group: 'Moving averages',
    kind: 'overlay',
    source: 'browser',
    repeatable: true,
    params: [p('period', 'Period', 21)],
    overlay: ov.emaOverlay,
  },
  {
    id: 'wma',
    label: 'WMA',
    group: 'Moving averages',
    kind: 'overlay',
    source: 'browser',
    repeatable: true,
    params: [p('period', 'Period', 20)],
    overlay: ov.wmaOverlay,
  },
  {
    id: 'bollinger',
    label: 'Bollinger Bands',
    group: 'Bands and channels',
    kind: 'overlay',
    source: 'browser',
    params: [p('period', 'Period', 20), p('k', 'σ multiple', 2, 0, 10, 0.5)],
    overlay: ov.bollinger,
  },
  {
    id: 'keltner',
    label: 'Keltner Channels',
    group: 'Bands and channels',
    kind: 'overlay',
    source: 'browser',
    params: [p('emaPeriod', 'EMA period', 20), p('atrPeriod', 'ATR period', 10), p('mult', 'ATR multiple', 2, 0, 10, 0.5)],
    overlay: ov.keltner,
  },
  {
    id: 'donchian',
    label: 'Donchian Channels',
    group: 'Bands and channels',
    kind: 'overlay',
    source: 'browser',
    repeatable: true,
    params: [p('period', 'Period', 20)],
    overlay: ov.donchian,
  },
  {
    id: 'ichimoku',
    label: 'Ichimoku Cloud',
    group: 'Trend structure',
    kind: 'overlay',
    source: 'browser',
    note: 'Senkou spans are drawn unshifted: their forward projection needs dates the loaded series does not have.',
    params: [p('tenkan', 'Tenkan', 9), p('kijun', 'Kijun', 26), p('senkou', 'Senkou B', 52)],
    overlay: ov.ichimoku,
  },
  {
    id: 'supertrend',
    label: 'Supertrend',
    group: 'Trend structure',
    kind: 'overlay',
    source: 'browser',
    params: [p('atrPeriod', 'ATR period', 10), p('mult', 'ATR multiple', 3, 0, 10, 0.5)],
    overlay: ov.supertrend,
  },
  {
    id: 'psar',
    label: 'Parabolic SAR',
    group: 'Trend structure',
    kind: 'overlay',
    source: 'browser',
    params: [p('step', 'Step', 0.02, 0, 1, 0.01), p('max', 'Max step', 0.2, 0, 1, 0.01)],
    overlay: ov.parabolicSar,
  },
  {
    id: 'linreg',
    label: 'Linear regression channel',
    group: 'Trend structure',
    kind: 'overlay',
    source: 'browser',
    params: [p('lookback', 'Lookback', 100, 2, 2000), p('k', 'σ multiple', 2, 0, 10, 0.5)],
    overlay: ov.linearRegressionChannel,
  },
  {
    id: 'avwap',
    label: 'Anchored VWAP',
    group: 'VWAP',
    kind: 'overlay',
    source: 'browser',
    note: 'Daily bars, so this is a cumulative volume-weighted mean from the anchor date — not an intraday session VWAP.',
    params: [{ key: 'anchor', label: 'Anchor date', type: 'date', default: '' }],
    overlay: ov.anchoredVwap,
  },
  {
    id: 'avwap_bands',
    label: 'Anchored VWAP ±σ bands',
    group: 'VWAP',
    kind: 'overlay',
    source: 'browser',
    params: [
      { key: 'anchor', label: 'Anchor date', type: 'date', default: '' },
      p('k', 'σ multiple', 1, 0, 5, 0.5),
    ],
    overlay: ov.anchoredVwapBands,
  },
  {
    id: 'rvwap',
    label: 'Rolling VWAP',
    group: 'VWAP',
    kind: 'overlay',
    source: 'browser',
    params: [p('period', 'Sessions', 20)],
    overlay: ov.rollingVwap,
  },
  {
    id: 'pivots',
    label: 'Pivot points (classic)',
    group: 'Levels',
    kind: 'overlay',
    source: 'browser',
    params: [
      {
        key: 'scale',
        label: 'Period',
        type: 'select',
        default: 'weekly',
        options: [
          { value: 'weekly', label: 'Weekly' },
          { value: 'monthly', label: 'Monthly' },
        ],
      },
    ],
    overlay: ov.pivotPoints,
  },
  {
    id: 'hilo52w',
    label: '52-week high / low',
    group: 'Levels',
    kind: 'overlay',
    source: 'browser',
    params: [p('sessions', 'Sessions', 252, 2, 2000)],
    overlay: ov.highLow52w,
  },
  {
    id: 'swings',
    label: 'Prior swing high / low',
    group: 'Levels',
    kind: 'overlay',
    source: 'browser',
    note: 'Fractal pivots — the same swing definition the pattern and Elliott Wave endpoints label.',
    params: [p('strength', 'Bars each side', 5, 1, 50)],
    overlay: ov.priorSwingLevels,
  },

  // ── Sub-panes fed by the backend series ──────────────────────────────
  backendPane('rsi', 'RSI (14)', 'Backend indicator series.'),
  backendPane('macd', 'MACD (12,26,9)', 'Backend indicator series.'),
  backendPane('adx', 'ADX (14)', 'Backend indicator series.'),
  {
    id: 'atr',
    label: 'ATR (14)',
    group: 'Backend panes',
    kind: 'pane',
    source: 'backend',
    note: 'Backend indicator series.',
    params: [],
    pane: {
      id: 'atr',
      label: 'ATR (14)',
      series: [{ key: 'atr14', type: 'line', color: '#38bdf8' }],
    },
  },

  // ── Sub-panes computed in the browser ────────────────────────────────
  {
    id: 'volume',
    label: 'Volume + SMA',
    group: 'Volume',
    kind: 'pane',
    source: 'browser',
    params: [p('period', 'SMA period', 20)],
    pane: {
      id: 'volume',
      label: 'Volume + SMA',
      series: [
        {
          key: 'volume',
          type: 'histogram',
          sign: { key: 'volume_dir', positive: 'rgba(16,185,129,0.45)', negative: 'rgba(239,68,68,0.45)' },
        },
        { key: 'volume_sma', type: 'line', color: '#94a3b8', lastValueVisible: false },
      ],
      format: (v) => v.toLocaleString('en-IN'),
    },
    compute: osc.volumePane,
  },
  {
    id: 'stoch',
    label: 'Stochastic %K / %D',
    group: 'Oscillators',
    kind: 'pane',
    source: 'browser',
    params: [
      p('period', 'Period', 14),
      // 1 = fast %K, the backend's stoch_k14 convention. Raise it for slow stochastic.
      p('kSmooth', '%K smoothing (1 = fast)', 1),
      p('dSmooth', '%D smoothing', 3),
    ],
    pane: {
      id: 'stoch',
      label: 'Stochastic (14,1,3)',
      series: [
        { key: 'stoch_k', type: 'line', color: '#0ea5e9' },
        { key: 'stoch_d', type: 'line', color: '#f59e0b', lastValueVisible: false },
      ],
      guides: [GUIDE(20), GUIDE(80)],
    },
    compute: osc.stochastic,
  },
  {
    id: 'stochrsi',
    label: 'Stochastic RSI',
    group: 'Oscillators',
    kind: 'pane',
    source: 'browser',
    params: [p('period', 'Period', 14)],
    pane: {
      id: 'stochrsi',
      label: 'Stoch RSI (14)',
      series: [{ key: 'stochrsi', type: 'line', color: '#c084fc' }],
      guides: [GUIDE(20), GUIDE(80)],
    },
    compute: osc.stochRsi,
  },
  {
    id: 'williams',
    label: 'Williams %R',
    group: 'Oscillators',
    kind: 'pane',
    source: 'browser',
    params: [p('period', 'Period', 14)],
    pane: {
      id: 'williams',
      label: 'Williams %R (14)',
      series: [{ key: 'williams_r', type: 'line', color: '#fb7185' }],
      guides: [GUIDE(-20), GUIDE(-80)],
    },
    compute: osc.williamsR,
  },
  {
    id: 'cci',
    label: 'CCI',
    group: 'Oscillators',
    kind: 'pane',
    source: 'browser',
    params: [p('period', 'Period', 20)],
    pane: {
      id: 'cci',
      label: 'CCI (20)',
      series: [{ key: 'cci', type: 'line', color: '#34d399' }],
      guides: [GUIDE(100), GUIDE(-100)],
    },
    compute: osc.cci,
  },
  {
    id: 'roc',
    label: 'Rate of change',
    group: 'Oscillators',
    kind: 'pane',
    source: 'browser',
    params: [p('period', 'Period', 12)],
    pane: {
      id: 'roc',
      label: 'ROC (12)',
      series: [{ key: 'roc', type: 'line', color: '#facc15' }],
      guides: [GUIDE(0)],
    },
    compute: osc.roc,
  },
  {
    id: 'di',
    label: '±DI (14)',
    group: 'Oscillators',
    kind: 'pane',
    source: 'browser',
    note: 'Pairs with the backend ADX pane.',
    params: [p('period', 'Period', 14)],
    pane: {
      id: 'di',
      label: '±DI (14)',
      series: [
        { key: 'plus_di', type: 'line', color: '#10b981' },
        { key: 'minus_di', type: 'line', color: '#ef4444', lastValueVisible: false },
      ],
      guides: [GUIDE(25)],
    },
    compute: osc.directionalIndicators,
  },
  {
    id: 'atr_pct',
    label: 'ATR % of close',
    group: 'Oscillators',
    kind: 'pane',
    source: 'browser',
    params: [p('period', 'Period', 14)],
    pane: {
      id: 'atr_pct',
      label: 'ATR % (14)',
      series: [{ key: 'atr_pct', type: 'line', color: '#60a5fa' }],
    },
    compute: osc.atrPane,
  },
  {
    id: 'obv',
    label: 'On-balance volume',
    group: 'Volume',
    kind: 'pane',
    source: 'browser',
    params: [],
    pane: {
      id: 'obv',
      label: 'OBV',
      series: [{ key: 'obv', type: 'line', color: '#2dd4bf' }],
      format: (v) => v.toLocaleString('en-IN'),
    },
    compute: (bars) => osc.obv(bars),
  },
  {
    id: 'cmf',
    label: 'Chaikin Money Flow',
    group: 'Volume',
    kind: 'pane',
    source: 'browser',
    params: [p('period', 'Period', 20)],
    pane: {
      id: 'cmf',
      label: 'CMF (20)',
      series: [{ key: 'cmf', type: 'line', color: '#a3e635' }],
      guides: [GUIDE(0)],
      format: (v) => v.toFixed(3),
    },
    compute: osc.chaikinMoneyFlow,
  },
  {
    id: 'mfi',
    label: 'Money Flow Index',
    group: 'Volume',
    kind: 'pane',
    source: 'browser',
    params: [p('period', 'Period', 14)],
    pane: {
      id: 'mfi',
      label: 'MFI (14)',
      series: [{ key: 'mfi', type: 'line', color: '#f472b6' }],
      guides: [GUIDE(20), GUIDE(80)],
    },
    compute: osc.moneyFlowIndex,
  },
  {
    id: 'relstrength',
    label: 'Relative strength vs benchmark',
    group: 'Volume',
    kind: 'pane',
    source: 'browser',
    note: 'Close ratio against the benchmark index named by the live endpoint, rebased to 100 at the first shared bar.',
    params: [p('period', 'Mean period', 50)],
    pane: {
      id: 'relstrength',
      label: 'RS vs benchmark',
      series: [
        { key: 'rs_ratio', type: 'line', color: '#818cf8' },
        { key: 'rs_ratio_sma', type: 'line', color: '#94a3b8', lastValueVisible: false },
      ],
    },
    compute: (bars, params, ctx) => osc.relativeStrength(bars, ctx.benchmark, params),
  },
];

export const INDICATOR_BY_ID = new Map(INDICATORS.map((d) => [d.id, d]));

export function defaultParams(def: IndicatorDef): Params {
  return Object.fromEntries(def.params.map((param) => [param.key, param.default]));
}

/** Catalogue groups in display order, each with its indicators. */
export function indicatorGroups(): { group: string; items: IndicatorDef[] }[] {
  const order: string[] = [];
  const byGroup = new Map<string, IndicatorDef[]>();
  for (const def of INDICATORS) {
    if (!byGroup.has(def.group)) {
      byGroup.set(def.group, []);
      order.push(def.group);
    }
    byGroup.get(def.group)!.push(def);
  }
  return order.map((group) => ({ group, items: byGroup.get(group)! }));
}
