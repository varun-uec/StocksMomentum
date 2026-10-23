/**
 * Chart kit for MF research (ui-ux doc 02, chart grammar). Every colour is a
 * theme variable; every chart can show its data as a table; Recharts' keyboard
 * layer moves the tooltip with the arrow keys once the chart has focus.
 * The charts draw service results. They compute no financial measure.
 */
import { useId, useMemo, useState, type ReactNode } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import type { Point } from '../api';
import { date, shortDate } from '../format';
import { heat, seriesColor, token } from '../theme/themes';
import { cx } from './ui';

export interface Series {
  id: string;
  label: string;
  points: Point[];
  color?: string;
  dashed?: boolean;
}

const tooltipStyle = {
  contentStyle: {
    background: token('surface'),
    border: `1px solid ${token('line')}`,
    borderRadius: 10,
    boxShadow: 'var(--mf-shadow-raised)',
    fontSize: 12,
    color: token('ink'),
  },
  labelStyle: { color: token('muted'), marginBottom: 4 },
  itemStyle: { padding: 0 },
  cursor: { stroke: token('lineStrong') },
};

const axis = { tickLine: false, axisLine: false, fontSize: 11 } as const;

/** Chart title, controls, legend, the plot, a footnote and a data-table toggle. */
export function ChartFrame({
  title,
  subtitle,
  controls,
  legend,
  children,
  footnote,
  table,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  controls?: ReactNode;
  legend?: ReactNode;
  children: ReactNode;
  footnote?: ReactNode;
  table?: { columns: string[]; rows: (string | number)[][] };
  className?: string;
}) {
  const [showTable, setShowTable] = useState(false);
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={cx('min-w-0 rounded-card border border-mf-line bg-mf-surface p-5 shadow-card', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={headingId} className="text-[15px] font-semibold text-mf-ink">
            {title}
          </h2>
          {subtitle && <p className="mt-0.5 text-xs text-mf-muted">{subtitle}</p>}
        </div>
        {controls && <div className="flex flex-wrap items-center gap-2">{controls}</div>}
      </div>
      {legend && <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-mf-ink-soft">{legend}</div>}
      <div className="mt-3">{showTable && table ? <DataTable caption={title} {...table} /> : children}</div>
      {(footnote || table) && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-mf-muted">
          <div className="min-w-0">{footnote}</div>
          {table && (
            <button type="button" onClick={() => setShowTable((s) => !s)} aria-pressed={showTable} className="font-medium text-mf-brand underline-offset-2 hover:underline">
              {showTable ? 'Show chart' : 'Show data table'}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function DataTable({ caption, columns, rows }: { caption: ReactNode; columns: string[]; rows: (string | number)[][] }) {
  return (
    <div className="mf-scroll max-h-72 overflow-auto rounded-[10px] border border-mf-line" tabIndex={0} role="region" aria-label="Chart data">
      <table className="w-full text-left text-xs tabular">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 bg-mf-sunken text-mf-muted">
          <tr>
            {columns.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-mf-line">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-1.5 text-mf-ink-soft">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LegendDot({ color, label, dashed }: { color: string; label: ReactNode; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width="16" height="8" aria-hidden="true">
        <line x1="0" y1="4" x2="16" y2="4" stroke={color} strokeWidth="2.5" strokeDasharray={dashed ? '4 3' : undefined} />
      </svg>
      {label}
    </span>
  );
}

/** Join series on date into rows Recharts can plot; a missing date stays a gap. */
export function mergeSeries(series: Series[]): Record<string, number | string>[] {
  const rows = new Map<string, Record<string, number | string>>();
  for (const s of series)
    for (const [d, v] of s.points) {
      const row = rows.get(d) ?? { date: d };
      row[s.id] = v;
      rows.set(d, row);
    }
  return [...rows.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

/** Keep every n-th row so a long table stays readable; the last row is always kept. */
export function thin<T>(rows: T[], max = 400): T[] {
  if (rows.length <= max) return rows;
  const step = Math.ceil(rows.length / max);
  return rows.filter((_, i) => i % step === 0 || i === rows.length - 1);
}

export function TimeChart({
  series,
  format,
  height = 260,
  area = false,
  zero = false,
  label,
  bands,
  yDomain,
}: {
  series: Series[];
  format: (v: number) => string;
  height?: number;
  area?: boolean;
  zero?: boolean;
  label: string;
  bands?: { start: string; end: string; color: string }[];
  yDomain?: [number | 'auto' | 'dataMin' | 'dataMax', number | 'auto' | 'dataMin' | 'dataMax'];
}) {
  // Thin after merging, so every series keeps the same dates; a date one series lacks is joined across.
  const data = useMemo(() => thin(mergeSeries(series), 700), [series]);
  const gradient = useId().replace(/:/g, '');
  const Chart = area ? AreaChart : LineChart;
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <Chart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={series[0]?.color ?? seriesColor(0)} stopOpacity={0.22} />
              <stop offset="100%" stopColor={series[0]?.color ?? seriesColor(0)} stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} />
          {bands?.map((b) => <ReferenceArea key={b.start} x1={b.start} x2={b.end} fill={b.color} fillOpacity={0.16} strokeOpacity={0} ifOverflow="hidden" />)}
          <XAxis dataKey="date" {...axis} tickFormatter={shortDate} minTickGap={48} />
          <YAxis {...axis} width={56} tickFormatter={format} domain={yDomain ?? ['auto', 'auto']} />
          {zero && <ReferenceLine y={0} stroke={token('muted')} strokeOpacity={0.5} />}
          <Tooltip {...tooltipStyle} labelFormatter={(d) => date(String(d))} formatter={(v, name) => [format(Number(v)), series.find((s) => s.id === name)?.label ?? name]} />
          {series.map((s, i) =>
            area && i === 0 ? (
              <Area key={s.id} type="monotone" dataKey={s.id} stroke={s.color ?? seriesColor(i)} strokeWidth={2} fill={`url(#${gradient})`} dot={false} isAnimationActive={false} connectNulls />
            ) : (
              <Line key={s.id} type="monotone" dataKey={s.id} stroke={s.color ?? seriesColor(i)} strokeWidth={i === 0 ? 2.2 : 1.6} strokeDasharray={s.dashed ? '5 4' : undefined} dot={false} isAnimationActive={false} connectNulls />
            ),
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}

/** Counts of values in equal-width buckets, with vertical markers (median, this fund). */
export function Histogram({
  values,
  bins = 24,
  format,
  markers = [],
  label,
  height = 220,
}: {
  values: number[];
  bins?: number;
  format: (v: number) => string;
  markers?: { value: number; label: string; color?: string }[];
  label: string;
  height?: number;
}) {
  const data = useMemo(() => bucket(values, bins), [values, bins]);
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 18, right: 8, bottom: 0, left: 0 }} barCategoryGap={1}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="mid" type="number" domain={['dataMin', 'dataMax']} {...axis} tickFormatter={format} />
          <YAxis {...axis} width={40} allowDecimals={false} />
          <Tooltip {...tooltipStyle} labelFormatter={(_, p) => (p?.[0] ? `${format(p[0].payload.from)} to ${format(p[0].payload.to)}` : '')} formatter={(v) => [v, 'Periods']} />
          <Bar dataKey="count" isAnimationActive={false} radius={[3, 3, 0, 0]}>
            {data.map((d) => (
              <Cell key={d.mid} fill={d.mid < 0 ? token('loss', 0.55) : token('brand', 0.55)} />
            ))}
          </Bar>
          {markers.map((m) => (
            <ReferenceLine key={m.label} x={m.value} stroke={m.color ?? token('ink')} strokeDasharray="4 3" label={{ value: m.label, position: 'top', fontSize: 11, fill: m.color ?? token('ink') }} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function bucket(values: number[], bins: number) {
  if (!values.length) return [];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const width = (hi - lo) / bins || 1;
  const counts = Array.from({ length: bins }, (_, i) => ({ from: lo + i * width, to: lo + (i + 1) * width, mid: lo + (i + 0.5) * width, count: 0 }));
  for (const v of values) counts[Math.min(bins - 1, Math.floor((v - lo) / width))].count += 1;
  return counts;
}

/** Signed bars per period (calendar or financial year); partial periods are hatched. */
export function PeriodBars({
  rows,
  format,
  label,
  height = 220,
}: {
  rows: { period: string; value: number | null; partial?: boolean; compare?: number | null }[];
  format: (v: number) => string;
  label: string;
  height?: number;
}) {
  const hatch = useId().replace(/:/g, '');
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <pattern id={hatch} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill={token('brand', 0.25)} />
              <line x1="0" y1="0" x2="0" y2="6" stroke={token('brand')} strokeWidth="2" />
            </pattern>
          </defs>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="period" {...axis} interval="preserveStartEnd" />
          <YAxis {...axis} width={52} tickFormatter={format} />
          <ReferenceLine y={0} stroke={token('muted')} strokeOpacity={0.6} />
          <Tooltip
            {...tooltipStyle}
            formatter={(v, name, item) => [`${format(Number(v))}${item?.payload?.partial ? ' (part year)' : ''}`, name === 'value' ? 'Return' : 'Comparison']}
          />
          <Bar dataKey="value" isAnimationActive={false} radius={[3, 3, 0, 0]} maxBarSize={36}>
            {rows.map((r) => (
              <Cell key={r.period} fill={r.partial ? `url(#${hatch})` : (r.value ?? 0) < 0 ? token('loss') : token('brand')} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Axis domain from the data with a margin, so a cluster is not pinned to a zero corner. */
const PAD: [(min: number) => number, (max: number) => number] = [(min) => min - Math.abs(min) * 0.1 - 0.005, (max) => max + Math.abs(max) * 0.1 + 0.005];

/** A scatter of peers; highlighted points are larger and labelled in the tooltip. */
export function PeerScatter({
  points,
  xLabel,
  yLabel,
  format,
  onSelect,
  label,
  height = 320,
}: {
  points: { id: string; name: string; x: number; y: number; highlight?: boolean; frontier?: boolean }[];
  xLabel: string;
  yLabel: string;
  format: (v: number) => string;
  onSelect?: (id: string) => void;
  label: string;
  height?: number;
}) {
  const groups = [
    { key: 'peer', data: points.filter((p) => !p.highlight && !p.frontier), color: token('muted', 0.45), size: 40 },
    { key: 'frontier', data: points.filter((p) => p.frontier && !p.highlight), color: token('brandAlt'), size: 70 },
    { key: 'this', data: points.filter((p) => p.highlight), color: token('chart2'), size: 140 },
  ];
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 18, left: 4 }}>
          <CartesianGrid />
          <XAxis type="number" dataKey="x" name={xLabel} {...axis} domain={PAD} tickFormatter={format} label={{ value: xLabel, position: 'insideBottom', offset: -10, fontSize: 11, fill: token('muted') }} />
          <YAxis type="number" dataKey="y" name={yLabel} {...axis} domain={PAD} width={52} tickFormatter={format} />
          <ZAxis range={[40, 140]} />
          <Tooltip
            {...tooltipStyle}
            content={({ payload }) => {
              const p = payload?.[0]?.payload as (typeof points)[number] | undefined;
              if (!p) return null;
              return (
                <div style={tooltipStyle.contentStyle} className="max-w-64 p-2.5">
                  <p className="font-medium">{p.name}</p>
                  <p className="mt-1 text-mf-muted">
                    {yLabel} {format(p.y)} · {xLabel} {format(p.x)}
                  </p>
                  {p.frontier && <p className="mt-1 text-mf-brand">On the historical frontier</p>}
                </div>
              );
            }}
          />
          {groups.map((g) => (
            <Scatter key={g.key} data={g.data} fill={g.color} isAnimationActive={false} onClick={(d) => onSelect?.((d as unknown as { id: string }).id)} cursor={onSelect ? 'pointer' : undefined} shape="circle" />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Monthly returns as a year × month grid; an HTML table, so it reads cell by cell. */
export function MonthHeatmap({ rows, format }: { rows: { year: number; month: number; return: number | null }[]; format: (v: number) => string }) {
  const years = [...new Set(rows.map((r) => r.year))].sort((a, b) => b - a);
  const cell = new Map(rows.map((r) => [`${r.year}-${r.month}`, r.return]));
  const max = Math.max(0.01, ...rows.map((r) => Math.abs(r.return ?? 0)));
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return (
    <div className="mf-scroll overflow-x-auto" tabIndex={0} role="region" aria-label="Monthly returns grid">
      <table className="w-full min-w-[640px] border-separate border-spacing-[3px] text-[11px] tabular">
        <thead>
          <tr>
            <th scope="col" className="w-12 text-left font-medium text-mf-muted">
              Year
            </th>
            {months.map((m) => (
              <th key={m} scope="col" className="font-medium text-mf-muted">
                {m}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map((y) => (
            <tr key={y}>
              <th scope="row" className="text-left font-medium text-mf-ink-soft">
                {y}
              </th>
              {months.map((m, i) => {
                const v = cell.get(`${y}-${i + 1}`);
                const strength = v === undefined || v === null ? 0 : Math.min(1, Math.abs(v) / max);
                return (
                  <td
                    key={m}
                    title={v === undefined || v === null ? undefined : `${m} ${y}: ${format(v)}`}
                    className="h-7 rounded-[4px] text-center text-mf-ink"
                    style={{ background: v === undefined || v === null ? token('sunken') : heat(v < 0 ? 'loss' : 'brand', strength) }}
                  >
                    {v === undefined || v === null ? '' : format(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A tiny trend line for cards and table rows. */
export function Sparkline({ points, color, height = 36, label }: { points: Point[]; color?: string; height?: number; label: string }) {
  const data = useMemo(() => thin(points, 80).map(([d, v]) => ({ d, v })), [points]);
  const up = data.length > 1 && data[data.length - 1].v >= data[0].v;
  const stroke = color ?? (up ? token('brand') : token('loss'));
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <YAxis hide domain={['dataMin', 'dataMax']} />
          <Area type="monotone" dataKey="v" stroke={stroke} strokeWidth={1.6} fill={stroke} fillOpacity={0.08} dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
