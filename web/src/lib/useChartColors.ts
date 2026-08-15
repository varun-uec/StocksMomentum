'use client';

import { useTheme } from '@/app/theme-provider';

/** Chart colors that follow the resolved theme (recharts styling is inline, not Tailwind). */
export function useChartColors() {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  return {
    grid: isDark ? '#1e293b' : '#e2e8f0',
    tick: isDark ? '#94a3b8' : '#64748b',
    tooltipBg: isDark ? '#1e293b' : '#ffffff',
    tooltipBorder: isDark ? '#334155' : '#e2e8f0',
  };
}
