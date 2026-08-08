/**
 * Centralized design tokens for Momentum25.
 *
 * These values are intentionally kept as simple data so they can be reused
 * for Tailwind classes, inline chart styles, and runtime theme-aware logic.
 */

export const colors = {
  // Primary brand
  indigo: {
    50: '#eef2ff',
    100: '#e0e7ff',
    200: '#c7d2fe',
    300: '#a5b4fc',
    400: '#818cf8',
    500: '#6366f1',
    600: '#4f46e5',
    700: '#4338ca',
    800: '#3730a3',
    900: '#312e81',
    950: '#1e1b4b',
  },
  // Semantic accents
  emerald: {
    50: '#ecfdf5',
    100: '#d1fae5',
    200: '#a7f3d0',
    300: '#6ee7b7',
    400: '#34d399',
    500: '#10b981',
    600: '#059669',
    700: '#047857',
    800: '#065f46',
    900: '#064e3b',
    950: '#022c22',
  },
  amber: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    300: '#fcd34d',
    400: '#fbbf24',
    500: '#f59e0b',
    600: '#d97706',
    700: '#b45309',
    800: '#92400e',
    900: '#78350f',
    950: '#451a03',
  },
  rose: {
    50: '#fff1f2',
    100: '#ffe4e6',
    200: '#fecdd3',
    300: '#fda4af',
    400: '#fb7185',
    500: '#f43f5e',
    600: '#e11d48',
    700: '#be123c',
    800: '#9f1239',
    900: '#881337',
    950: '#4c0519',
  },
  cyan: {
    400: '#22d3ee',
    500: '#06b6d4',
  },
  violet: {
    400: '#a78bfa',
    500: '#8b5cf6',
  },
  // Slate scale for UI chrome
  slate: {
    50: '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1e293b',
    900: '#0f172a',
    950: '#020617',
  },
} as const;

export const chartPalette = {
  primary: colors.indigo[500],
  secondary: colors.violet[500],
  success: colors.emerald[500],
  warning: colors.amber[500],
  danger: colors.rose[500],
  info: colors.cyan[500],
  accent1: colors.cyan[400],
  accent2: colors.violet[400],
  accent3: colors.amber[400],
  accent4: colors.emerald[400],
  accent5: colors.rose[400],
  accent6: colors.indigo[400],
  accent7: '#fb923c',
  accent8: '#e879f9',
} as const;

export const chartColorList = [
  chartPalette.accent1,
  chartPalette.accent2,
  chartPalette.accent3,
  chartPalette.accent4,
  chartPalette.accent5,
  chartPalette.accent6,
  chartPalette.accent7,
  chartPalette.accent8,
];

export const spacing = {
  page: 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8',
  section: 'space-y-6',
  cardGrid: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4',
} as const;

export const typography = {
  pageTitle: 'text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100',
  pageSubtitle: 'text-sm text-slate-500 dark:text-slate-400',
  sectionTitle: 'text-lg font-semibold text-slate-900 dark:text-slate-100',
  cardTitle: 'text-sm font-semibold text-slate-800 dark:text-slate-200',
  body: 'text-sm text-slate-700 dark:text-slate-300 leading-relaxed',
  caption: 'text-xs text-slate-500 dark:text-slate-400',
  metricValue: 'text-2xl font-bold tabular-nums tracking-tight',
} as const;

export const focusRing =
  'focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900';

export const transitions = {
  colors: 'transition-colors duration-150',
  all: 'transition-all duration-200',
} as const;
