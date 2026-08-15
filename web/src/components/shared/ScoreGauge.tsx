'use client';

import { RadialBarChart, RadialBar, PolarAngleAxis } from 'recharts';
import { useTheme } from '@/app/theme-provider';
import { chartPalette } from '@/lib/theme';

interface ScoreGaugeProps {
  label: string;
  value: number; // 0-100
  size?: number;
}

function gaugeColor(value: number): string {
  if (value >= 65) return chartPalette.success;
  if (value >= 45) return chartPalette.warning;
  return chartPalette.danger;
}

/** A compact semi-circle 0-100 gauge, used so a score can be read in under a second. */
export function ScoreGauge({ label, value, size = 120 }: ScoreGaugeProps) {
  const { resolvedTheme } = useTheme();
  const trackColor = resolvedTheme === 'dark' ? '#334155' : '#e2e8f0';
  const color = gaugeColor(value);
  const clamped = Math.max(0, Math.min(100, value));
  const data = [{ value: clamped, fill: color }];

  return (
    <div className="flex flex-col items-center">
      <div
        role="meter"
        aria-valuenow={Math.round(clamped)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${clamped.toFixed(0)} out of 100`}
        style={{ width: size, height: size * 0.62 }}
        className="relative"
      >
        <RadialBarChart
          width={size}
          height={size}
          cx={size / 2}
          cy={size / 2}
          innerRadius={size * 0.32}
          outerRadius={size * 0.46}
          barSize={size * 0.14}
          data={data}
          startAngle={180}
          endAngle={0}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar background={{ fill: trackColor }} dataKey="value" cornerRadius={8} />
        </RadialBarChart>
        <div
          className="absolute inset-x-0 flex items-center justify-center text-lg font-bold tabular-nums text-slate-800 dark:text-slate-100"
          style={{ top: size * 0.28 }}
        >
          {clamped.toFixed(0)}
        </div>
      </div>
      <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider -mt-1">{label}</div>
    </div>
  );
}
