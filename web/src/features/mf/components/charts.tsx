/**
 * Chart kit for MF research (ui-ux doc 02, chart grammar). Every colour is a
 * theme variable; every chart can show its data as a table; Recharts' keyboard
 * layer moves the tooltip with the arrow keys once the chart has focus.
 * The charts draw service results. They compute no financial measure.
 */
import { useEffect, useId, useMemo, useState, type ReactNode } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
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
import { logTicks, niceTicks, timeLabel, timeTicks, toTime } from '../axis';
import { date, schemeName } from '../format';
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
  id,
}: {
  id?: string;
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
    <section id={id} aria-labelledby={headingId} className={cx('min-w-0 scroll-mt-24 rounded-card border border-mf-line bg-mf-surface p-5 shadow-card', className)}>
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

const rowValues = (row: unknown): [string, unknown][] => Object.entries(Array.isArray(row) ? row.slice(1) : (row as object));

/**
 * About `max` rows for drawing or a table, without losing what matters. The rows
 * split into buckets; each bucket keeps its first row and the rows that hold each
 * value's lowest and highest point, so a deepest fall or a peak survives on its
 * own date (independent audit A-02). The first and last rows are always kept.
 */
export function thin<T>(rows: T[], max = 400): T[] {
  if (rows.length <= max) return rows;
  const size = Math.ceil((rows.length * 3) / max);
  const keep = new Set<number>([0, rows.length - 1]);
  for (let start = 0; start < rows.length; start += size) {
    keep.add(start);
    const lo = new Map<string, [number, number]>();
    const hi = new Map<string, [number, number]>();
    for (let i = start; i < Math.min(start + size, rows.length); i++)
      for (const [k, v] of rowValues(rows[i])) {
        if (typeof v !== 'number' || !Number.isFinite(v)) continue;
        if (!(v >= (lo.get(k)?.[1] ?? Infinity))) lo.set(k, [i, v]);
        if (!(v <= (hi.get(k)?.[1] ?? -Infinity))) hi.set(k, [i, v]);
      }
    for (const [i] of [...lo.values(), ...hi.values()]) keep.add(i);
  }
  return [...keep].sort((a, b) => a - b).map((i) => rows[i]);
}

type Bound = number | 'auto' | 'dataMin' | 'dataMax';

/** Round gridlines over the values; a fixed bound in `domain` is kept as given. */
export function valueAxis(values: number[], domain?: [Bound, Bound], count = 5): { ticks: number[]; domain: [number, number] } {
  const finite = values.filter(Number.isFinite);
  const lo = typeof domain?.[0] === 'number' ? domain[0] : finite.length ? Math.min(...finite) : 0;
  const hi = typeof domain?.[1] === 'number' ? domain[1] : finite.length ? Math.max(...finite) : 1;
  const ticks = niceTicks(lo, hi, count);
  return { ticks, domain: [ticks[0] ?? lo, ticks[ticks.length - 1] ?? hi] };
}

/**
 * A time series chart. Dates plot as time, so bands and markers land on their
 * exact dates and ticks fall on month or year starts. `zoom` adds a brush.
 */
export function TimeChart({
  series,
  format,
  tick,
  height = 260,
  area = false,
  zero = false,
  label,
  bands,
  markers,
  dots,
  yDomain,
  zoom = false,
  log = false,
}: {
  series: Series[];
  /** Tooltip values. */
  format: (v: number) => string;
  /** Axis labels; defaults to `format`. Pass `pctTick` for percentages. */
  tick?: (v: number) => string;
  height?: number;
  area?: boolean;
  zero?: boolean;
  label: string;
  bands?: { start: string; end: string; color: string; label?: string }[];
  markers?: { date: string; label: string; color?: string }[];
  /** A point worth naming on the line, such as the deepest fall; drawn at its own date and value. */
  dots?: { date: string; value: number; label: string; color?: string }[];
  yDomain?: [Bound, Bound];
  zoom?: boolean;
  /** A log value axis: equal heights mean equal percentage moves. Positive series only. */
  log?: boolean;
}) {
  // Every row at full resolution; a zoom thins only the rows in view, so it shows detail
  // the full view had to merge. Thin after merging, so every series keeps the same dates.
  const full = useMemo(() => mergeSeries(series).map((r) => ({ ...r, t: toTime(String(r.date)) }) as Record<string, number | string>), [series]);
  const [range, setRange] = useState<[number, number] | null>(null);
  useEffect(() => setRange(null), [full]);
  const [from, to] = range && range[1] < full.length ? range : [0, full.length - 1];
  const visible = useMemo(() => thin(full.slice(from, to + 1), 700), [full, from, to]);
  const data = visible;
  const shown = visible.flatMap((r) => series.map((s) => r[s.id]).filter((v): v is number => typeof v === 'number'));
  const positive = shown.length > 0 && Math.min(...shown) > 0;
  const y =
    log && positive
      ? { ticks: logTicks(Math.min(...shown) * 0.95, Math.max(...shown) * 1.05), domain: [Math.min(...shown) * 0.95, Math.max(...shown) * 1.05] as [number, number] }
      : valueAxis(shown.concat(zero ? [0] : []), yDomain);
  const x = timeTicks(Number(visible[0]?.t ?? 0), Number(visible[visible.length - 1]?.t ?? 0));
  const gradient = useId().replace(/:/g, '');
  const Chart = area ? AreaChart : LineChart;
  const axisText = tick ?? format;
  return (
    // A zoomable chart holds the range handles, so it is a figure, not an image.
    <div role={zoom ? 'figure' : 'img'} aria-label={label}>
      <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <Chart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={series[0]?.color ?? seriesColor(0)} stopOpacity={0.24} />
              <stop offset="100%" stopColor={series[0]?.color ?? seriesColor(0)} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} />
          {bands?.map((b) => (
            <ReferenceArea key={b.start} x1={toTime(b.start)} x2={toTime(b.end)} fill={b.color} fillOpacity={0.18} strokeOpacity={0} ifOverflow="hidden" className="mf-band" />
          ))}
          <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} ticks={x.ticks} {...axis} tickFormatter={(t: number) => timeLabel(t, x.years)} allowDataOverflow />
          <YAxis {...axis} width={58} ticks={y.ticks} domain={y.domain} tickFormatter={axisText} allowDataOverflow scale={log && positive ? 'log' : 'auto'} />
          {zero && <ReferenceLine y={0} stroke={token('muted')} strokeOpacity={0.5} />}
          {markers?.map((m) => (
            <ReferenceLine key={m.date + m.label} x={toTime(m.date)} stroke={m.color ?? token('inkSoft')} strokeDasharray="3 3" ifOverflow="hidden" label={{ value: m.label, position: 'insideTopLeft', fontSize: 11, fill: m.color ?? token('inkSoft') }} />
          ))}
          {dots?.map((d) => (
            <ReferenceDot key={d.date + d.label} x={toTime(d.date)} y={d.value} r={5} fill={d.color ?? token('ink')} stroke={token('surface')} strokeWidth={2} ifOverflow="hidden" label={{ value: d.label, position: 'right', offset: 10, fontSize: 11, fontWeight: 600, fill: d.color ?? token('ink') }} />
          ))}
          <Tooltip
            {...tooltipStyle}
            labelFormatter={(_, payload) => date(String(payload?.[0]?.payload?.date ?? ''))}
            formatter={(v, name) => [format(Number(v)), series.find((s) => s.id === name)?.label ?? name]}
          />
          {series.map((s, i) =>
            area && i === 0 ? (
              <Area key={s.id} type="monotone" dataKey={s.id} stroke={s.color ?? seriesColor(i)} strokeWidth={2} fill={`url(#${gradient})`} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} connectNulls />
            ) : (
              <Line key={s.id} type="monotone" dataKey={s.id} stroke={s.color ?? seriesColor(i)} strokeWidth={i === 0 ? 2.2 : 1.6} strokeDasharray={s.dashed ? '5 4' : undefined} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} connectNulls />
            ),
          )}
        </Chart>
      </ResponsiveContainer>
      </div>
      {zoom && full.length > 20 && <RangeBrush rows={full} first={series[0]?.id} from={from} to={to} onChange={setRange} label={label} />}
    </div>
  );
}

/**
 * The zoom control: two native range inputs over an overview line. Each handle is
 * a labelled slider whose value reads as a date, so it works with keys, touch and
 * screen readers (audit A-12). Arrows move a day; Page Up/Down move further.
 */
function RangeBrush({ rows, first, from, to, onChange, label }: { rows: Record<string, number | string>[]; first?: string; from: number; to: number; onChange: (r: [number, number] | null) => void; label: string }) {
  const last = rows.length - 1;
  const overview = useMemo(() => {
    const pts = thin(rows.map((r) => [Number(r.t), r[first ?? ''] as number] as [number, number]).filter(([, v]) => typeof v === 'number'), 160);
    const vs = pts.map(([, v]) => v);
    const [lo, hi] = [Math.min(...vs), Math.max(...vs)];
    const [t0, t1] = [Number(rows[0].t), Number(rows[last].t)];
    return pts.map(([t, v]) => `${(((t - t0) / (t1 - t0 || 1)) * 100).toFixed(2)},${(26 - ((v - lo) / (hi - lo || 1)) * 22).toFixed(2)}`).join(' ');
  }, [rows, first, last]);
  const day = (i: number) => date(String(rows[i]?.date ?? ''));
  const at = (i: number) => `${(i / last) * 100}%`;
  const zoomed = from > 0 || to < last;
  return (
    <div className="mt-2">
      <div className="relative h-8 rounded-[6px] border border-mf-line bg-mf-sunken/60">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
          <polyline points={overview} fill="none" stroke={token('muted')} strokeWidth="1" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="absolute inset-y-0 rounded-[4px] bg-mf-brand/15 ring-1 ring-mf-brand/40" style={{ left: at(from), right: `calc(100% - ${at(to)})` }} aria-hidden="true" />
        <input type="range" className="mf-range" min={0} max={last} value={from} aria-label={`${label}: start date`} aria-valuetext={day(from)} onChange={(e) => onChange([Math.min(Number(e.target.value), to - 1), to])} />
        <input type="range" className="mf-range" min={0} max={last} value={to} aria-label={`${label}: end date`} aria-valuetext={day(to)} onChange={(e) => onChange([from, Math.max(Number(e.target.value), from + 1)])} />
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-mf-muted tabular">
        <span>{day(from)}</span>
        {zoomed && (
          <button type="button" className="mf-tap rounded px-2 font-medium text-mf-brand-strong hover:underline" onClick={() => onChange(null)}>
            Show all dates
          </button>
        )}
        <span>{day(to)}</span>
      </div>
    </div>
  );
}

/** Counts of values in equal-width buckets, with vertical markers (median, this fund). */
export function Histogram({
  values,
  format,
  markers = [],
  label,
  height = 220,
}: {
  values: number[];
  /** Axis and bucket-edge labels. Pass `pctTick` for percentages. */
  format: (v: number) => string;
  markers?: { value: number; label: string; color?: string }[];
  label: string;
  height?: number;
}) {
  const { data, ticks } = useMemo(() => {
    const t = niceTicks(Math.min(...values), Math.max(...values), 6);
    const step = (t[1] ?? 1) - (t[0] ?? 0);
    // Buckets split each gridline step, so bucket edges and labels line up.
    const width = step / (values.length > 400 ? 5 : values.length > 60 ? 2 : 1);
    return { data: bucket(values, t[0] ?? 0, width, Math.round(((t[t.length - 1] ?? 1) - (t[0] ?? 0)) / width)), ticks: t };
  }, [values]);
  const counts = valueAxis([0, ...data.map((d) => d.count)], [0, 'auto'], 4);
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 18, right: 8, bottom: 0, left: 0 }} barCategoryGap={1}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="mid" type="number" domain={[ticks[0], ticks[ticks.length - 1]]} ticks={ticks} {...axis} tickFormatter={format} />
          <YAxis {...axis} width={40} allowDecimals={false} ticks={counts.ticks} domain={counts.domain} />
          <Tooltip {...tooltipStyle} labelFormatter={(_, p) => (p?.[0] ? `${format(p[0].payload.from)} to ${format(p[0].payload.to)}` : '')} formatter={(v) => [v, 'Periods']} />
          <Bar dataKey="count" isAnimationActive={false} radius={[3, 3, 0, 0]}>
            {data.map((d) => (
              <Cell key={d.mid} fill={d.mid < 0 ? token('loss', 0.6) : token('brand', 0.6)} />
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

/** `count` buckets of `width` from `from`; a value on the top edge joins the last bucket. */
export function bucket(values: number[], from: number, width: number, count: number) {
  if (!values.length || !(width > 0) || count < 1) return [];
  const counts = Array.from({ length: count }, (_, i) => ({ from: from + i * width, to: from + (i + 1) * width, mid: from + (i + 0.5) * width, count: 0 }));
  for (const v of values) counts[Math.max(0, Math.min(count - 1, Math.floor((v - from) / width + 1e-9)))].count += 1;
  return counts;
}

/** Signed bars per period (calendar or financial year); partial periods are hatched. */
export function PeriodBars({
  rows,
  format,
  tick,
  label,
  height = 220,
}: {
  rows: { period: string; value: number | null; partial?: boolean; compare?: number | null }[];
  format: (v: number) => string;
  tick?: (v: number) => string;
  label: string;
  height?: number;
}) {
  const hatch = useId().replace(/:/g, '');
  const y = valueAxis(rows.map((r) => r.value ?? 0).concat(0));
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
          <YAxis {...axis} width={52} ticks={y.ticks} domain={y.domain} tickFormatter={tick ?? format} />
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

/** Two values per row as side-by-side bars, e.g. the fund against the proxy in each market window. */
export function PairBars({
  rows,
  names,
  format,
  tick,
  label,
  height = 260,
}: {
  rows: { label: string; a: number | null; b: number | null; tone?: string }[];
  names: [string, string];
  format: (v: number) => string;
  tick?: (v: number) => string;
  label: string;
  height?: number;
}) {
  const y = valueAxis(rows.flatMap((r) => [r.a ?? 0, r.b ?? 0]).concat(0));
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: 0 }} barGap={2}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" {...axis} interval={0} tick={{ fontSize: 10 }} />
          <YAxis {...axis} width={52} ticks={y.ticks} domain={y.domain} tickFormatter={tick ?? format} />
          <ReferenceLine y={0} stroke={token('muted')} strokeOpacity={0.6} />
          <Tooltip {...tooltipStyle} formatter={(v, name) => [format(Number(v)), name === 'a' ? names[0] : names[1]]} />
          <Bar dataKey="b" fill={token('muted', 0.45)} isAnimationActive={false} radius={[3, 3, 0, 0]} maxBarSize={22} />
          <Bar dataKey="a" isAnimationActive={false} radius={[3, 3, 0, 0]} maxBarSize={22}>
            {rows.map((r) => (
              <Cell key={r.label} fill={(r.a ?? 0) < 0 ? token('loss') : token('brand')} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** A scatter of peers; the frontier is a line, highlighted points are larger and named. */
export function PeerScatter({
  points,
  xLabel,
  yLabel,
  format,
  tick = format,
  onSelect,
  label,
  height = 320,
}: {
  /** `color` gives a highlighted point the colour its series has elsewhere on the page. */
  points: { id: string; name: string; x: number; y: number; highlight?: boolean; frontier?: boolean; color?: string }[];
  xLabel: string;
  yLabel: string;
  format: (v: number) => string;
  tick?: (v: number) => string;
  onSelect?: (id: string) => void;
  label: string;
  height?: number;
}) {
  const xs = valueAxis(points.map((p) => p.x), undefined, 6);
  const ys = valueAxis(points.map((p) => p.y), undefined, 6);
  const groups = [
    { key: 'peer', data: points.filter((p) => !p.highlight && !p.frontier).map((p) => ({ ...p, z: 1 })), color: token('muted', 0.45), line: false },
    { key: 'frontier', data: points.filter((p) => p.frontier).map((p) => ({ ...p, z: 2 })).sort((a, b) => a.x - b.x), color: token('brandAlt'), line: true },
    { key: 'this', data: points.filter((p) => p.highlight).map((p) => ({ ...p, z: 3, short: shortName(p.name) })), color: token('chart2'), line: false },
  ];
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 16, right: 16, bottom: 18, left: 4 }}>
          <CartesianGrid />
          <XAxis type="number" dataKey="x" name={xLabel} {...axis} domain={xs.domain} ticks={xs.ticks} tickFormatter={tick} label={{ value: xLabel, position: 'insideBottom', offset: -10, fontSize: 11, fill: token('muted') }} />
          <YAxis type="number" dataKey="y" name={yLabel} {...axis} domain={ys.domain} ticks={ys.ticks} width={52} tickFormatter={tick} />
          <ZAxis dataKey="z" domain={[1, 3]} range={[40, 160]} />
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
            <Scatter
              key={g.key}
              data={g.data}
              fill={g.color}
              line={g.line ? { stroke: token('brandAlt'), strokeWidth: 1.5, strokeDasharray: '4 3' } : false}
              isAnimationActive={false}
              onClick={(d) => onSelect?.((d as unknown as { id: string }).id)}
              cursor={onSelect ? 'pointer' : undefined}
              shape="circle"
            >
              {g.key === 'this' && g.data.map((p) => <Cell key={p.id} fill={p.color ?? g.color} stroke={token('surface')} strokeWidth={1.5} />)}
              {g.key === 'this' && <LabelList dataKey="short" content={ScatterLabel} />}
            </Scatter>
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/** A fund name short enough for a chart label: no plan words, at most 22 characters. */
export function shortName(name: string): string {
  const short = schemeName(name).replace(/ Fund$/, '');
  return short.length > 22 ? `${short.slice(0, 21)}…` : short;
}

/**
 * One line of text beside a highlighted point. Recharts wraps a label to a width,
 * which stacked long names word by word (audit U-12); alternate points sit below
 * their mark, so neighbours rarely collide.
 */
function ScatterLabel(props: { x?: number | string; y?: number | string; value?: unknown; index?: number }) {
  const x = Number(props.x);
  const y = Number(props.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const below = (props.index ?? 0) % 2 === 1;
  return (
    <text x={x} y={below ? y + 22 : y - 12} textAnchor="middle" fontSize={11} fontWeight={600} fill={token('ink')} stroke={token('surface')} strokeWidth={3} paintOrder="stroke" style={{ whiteSpace: 'pre' }}>
      {String(props.value ?? '')}
    </text>
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
