export interface Horizon {
  strategyName: string;
  label: string;
}

/** Momentum Horizons: each maps to an independent strategy config (ADR-005). */
export const HORIZONS: Horizon[] = [
  { strategyName: 'minervini_trend_template_3m', label: '3 Months' },
  { strategyName: 'minervini_trend_template_6m', label: '6 Months' },
  { strategyName: 'minervini_trend_template', label: '1 Year' },
  { strategyName: 'minervini_trend_template_2y', label: '2 Years' },
  { strategyName: 'minervini_trend_template_3y', label: '3 Years' },
  { strategyName: 'minervini_trend_template_5y', label: '5 Years' },
];

export const DEFAULT_HORIZON = HORIZONS[2]; // 1 Year
