import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from 'recharts';

interface Props {
  closes: { date: string; close: number }[];
  tooltipBg: string;
  tooltipBorder: string;
}

/** The last year of closes as a line. Kept apart so the charting library loads only when it is drawn. */
export default function YearClosesChart({ closes, tooltipBg, tooltipBorder }: Props) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={closes}>
        <YAxis hide domain={['auto', 'auto']} />
        <Tooltip
          formatter={(value) => (typeof value === 'number' ? value.toFixed(2) : String(value))}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
          contentStyle={{ backgroundColor: tooltipBg, borderColor: tooltipBorder, fontSize: 11 }}
        />
        <Line type="monotone" dataKey="close" dot={false} strokeWidth={1.5} stroke="#6366f1" isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
