/**
 * The Recharts drawing of the chart kit in `charts.tsx`. It loads after the page's
 * first render, so text and figures do not wait for about 400 kB of chart code
 * (acceptance review R-02); each chart there keeps its box meanwhile. Recharts'
 * keyboard layer moves the tooltip with the arrow keys once the chart has focus.
 */
import { useId, useMemo } from 'react';
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
import { logTicks, niceTicks, timeLabel, timeTicks, toTime } from '../axis';
import { date } from '../format';
import { seriesColor, token } from '../theme/themes';
import {
  bucket,
  shortName,
  thin,
  valueAxis,
  type HistogramProps,
  type PairBarsProps,
  type PeerScatterProps,
  type PeriodBarsProps,
  type SparklineProps,
  type TimeChartProps,
} from './charts';

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

/** The plot of a `TimeChart`: `data` holds the merged rows in view, each with its time `t`. */
export function TimePlot({
  data,
  series,
  format,
  tick,
  area = false,
  zero = false,
  bands,
  markers,
  dots,
  yDomain,
  log = false,
}: Omit<TimeChartProps, 'height' | 'label' | 'zoom'> & { data: Record<string, number | string>[] }) {
  const shown = data.flatMap((r) => series.map((s) => r[s.id]).filter((v): v is number => typeof v === 'number'));
  const positive = shown.length > 0 && Math.min(...shown) > 0;
  const y =
    log && positive
      ? { ticks: logTicks(Math.min(...shown) * 0.95, Math.max(...shown) * 1.05), domain: [Math.min(...shown) * 0.95, Math.max(...shown) * 1.05] as [number, number] }
      : valueAxis(shown.concat(zero ? [0] : []), yDomain);
  const x = timeTicks(Number(data[0]?.t ?? 0), Number(data[data.length - 1]?.t ?? 0));
  const gradient = useId().replace(/:/g, '');
  const Chart = area ? AreaChart : LineChart;
  const axisText = tick ?? format;
  return (
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
  );
}

export function HistogramPlot({ values, format, markers = [] }: HistogramProps) {
  const { data, ticks } = useMemo(() => {
    const t = niceTicks(Math.min(...values), Math.max(...values), 6);
    const step = (t[1] ?? 1) - (t[0] ?? 0);
    // Buckets split each gridline step, so bucket edges and labels line up.
    const width = step / (values.length > 400 ? 5 : values.length > 60 ? 2 : 1);
    return { data: bucket(values, t[0] ?? 0, width, Math.round(((t[t.length - 1] ?? 1) - (t[0] ?? 0)) / width)), ticks: t };
  }, [values]);
  const counts = valueAxis([0, ...data.map((d) => d.count)], [0, 'auto'], 4);
  return (
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
  );
}

export function PeriodBarsPlot({ rows, format, tick }: PeriodBarsProps) {
  const hatch = useId().replace(/:/g, '');
  const y = valueAxis(rows.map((r) => r.value ?? 0).concat(0));
  return (
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
  );
}

export function PairBarsPlot({ rows, names, format, tick }: PairBarsProps) {
  const y = valueAxis(rows.flatMap((r) => [r.a ?? 0, r.b ?? 0]).concat(0));
  return (
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
  );
}

export function PeerScatterPlot({ points, xLabel, yLabel, format, tick = format, onSelect }: PeerScatterProps) {
  const xs = valueAxis(points.map((p) => p.x), undefined, 6);
  const ys = valueAxis(points.map((p) => p.y), undefined, 6);
  const groups = [
    { key: 'peer', data: points.filter((p) => !p.highlight && !p.frontier).map((p) => ({ ...p, z: 1 })), color: token('muted', 0.45), line: false },
    { key: 'frontier', data: points.filter((p) => p.frontier).map((p) => ({ ...p, z: 2 })).sort((a, b) => a.x - b.x), color: token('brandAlt'), line: true },
    { key: 'this', data: points.filter((p) => p.highlight).map((p) => ({ ...p, z: 3, short: shortName(p.name) })), color: token('chart2'), line: false },
  ];
  return (
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
  );
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

export function SparklinePlot({ points, color }: SparklineProps) {
  const data = useMemo(() => thin(points, 80).map(([d, v]) => ({ d, v })), [points]);
  const up = data.length > 1 && data[data.length - 1].v >= data[0].v;
  const stroke = color ?? (up ? token('brand') : token('loss'));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
        <YAxis hide domain={['dataMin', 'dataMax']} />
        <Area type="monotone" dataKey="v" stroke={stroke} strokeWidth={1.6} fill={stroke} fillOpacity={0.08} dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
