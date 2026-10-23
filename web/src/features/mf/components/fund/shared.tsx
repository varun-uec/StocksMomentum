/** Widgets every fund tab shares: metric tiles, the growth journey and the rolling-return distribution. */
import { useMemo, useState } from 'react';
import type { FieldDef, Metrics } from '../../api';
import { pctTick } from '../../axis';
import { date, formatField, inr, inrTick, missingLabel, pct } from '../../format';
import { useNavs, useRegimes, useRolling } from '../../queries';
import { availableWindows, navPoints, rebase, sinceYears, WINDOWS, type WindowKey } from '../../series';
import { seriesColor, token } from '../../theme/themes';
import { ChartFrame, Histogram, LegendDot, TimeChart, thin } from '../charts';
import { ErrorState, Segmented, Skeleton, Stat, cx } from '../ui';

export interface FundTabProps {
  code: string;
  metrics: Metrics;
  fields: Map<string, FieldDef>;
}

/** One registry value as a tile, with its category median or rank underneath when given. */
export function MetricTile({
  metrics,
  fields,
  id,
  label,
  median,
  rank,
  plain,
}: {
  metrics: Metrics;
  fields: Map<string, FieldDef>;
  id: string;
  label?: string;
  median?: string;
  rank?: string;
  plain?: string;
}) {
  const field = fields.get(id);
  const value = metrics.values[id];
  const state = metrics.states[id];
  const missing = value === null || value === undefined;
  let sub: string | undefined = plain;
  if (missing) sub = missingLabel(state);
  else if (median && metrics.values[median] != null) sub = `category median ${formatField(fields.get(median), metrics.values[median], fields)}`;
  else if (rank && metrics.values[rank] != null) sub = `rank ${metrics.values[rank]} of ${metrics.values[rank.replace(/_rank$/, '_count')] ?? '—'} in category`;
  const negative = typeof value === 'number' && value < 0 && field?.unit === 'fraction';
  return (
    <Stat
      label={label ?? field?.label ?? id}
      value={missing ? '—' : formatField(field, value, fields)}
      sub={sub}
      valueClass={cx(negative && 'text-mf-loss')}
      help={field && <>{field.description}{metrics.anchors[id] ? ` Start anchor: ${metrics.anchors[id]}.` : ''}</>}
    />
  );
}

/**
 * Growth of ₹10,000: the fund's NAV rebased at the window start. Equity and hybrid
 * funds also show the NAV-built large-cap proxy, labelled as a proxy.
 */
export function GrowthChart({ code, metrics, height = 280, title = 'Growth of ₹10,000' }: { code: string; metrics: Metrics; height?: number; title?: string }) {
  const navs = useNavs(code);
  const assetClass = String(metrics.values.asset_class ?? '');
  const withProxy = assetClass === 'Equity' || assetClass === 'Hybrid';
  const regimes = useRegimes();
  const [falls, setFalls] = useState(true);
  const [log, setLog] = useState(false);
  const points = useMemo(() => navPoints(navs.data?.navs ?? []), [navs.data]);
  const windows = availableWindows(points);
  const [window, setWindow] = useState<WindowKey>('Max');
  const active = windows.includes(window) ? window : 'Max';
  const fund = useMemo(() => {
    const cut = sinceYears(points, WINDOWS[active]);
    return rebase(cut, 10_000);
  }, [points, active]);
  const start = fund[0]?.[0];
  const proxy = useMemo(() => (withProxy && start ? rebase(regimes.data?.proxy.levels ?? [], 10_000, start) : []), [withProxy, start, regimes.data]);
  const end = fund[fund.length - 1]?.[1];
  const proxyEnd = proxy[proxy.length - 1]?.[1];
  const series = [{ id: 'fund', label: 'This fund', points: fund, color: seriesColor(0) }, ...(proxy.length ? [{ id: 'proxy', label: 'Large-cap proxy', points: proxy, color: token('chart2'), dashed: true }] : [])];
  // Market-proxy falls in the window, drawn behind the line (audit U-03).
  const bands = falls && start ? (regimes.data?.windows ?? []).filter((w) => w.kind !== 'recovery' && w.end >= start).map((w) => ({ start: w.start < start ? start : w.start, end: w.end, color: token(w.kind === 'crash' ? 'loss' : 'warning') })) : [];
  return (
    <ChartFrame
      title={title}
      subtitle={start ? `From ${date(start)}, NAV rebased; dividends inside the NAV, before tax` : undefined}
      controls={
        <>
          <label className="inline-flex min-h-8 items-center gap-1.5 text-xs text-mf-ink-soft">
            <input type="checkbox" checked={falls} onChange={(e) => setFalls(e.target.checked)} />
            Market falls
          </label>
          <label className="inline-flex min-h-8 items-center gap-1.5 text-xs text-mf-ink-soft">
            <input type="checkbox" checked={log} onChange={(e) => setLog(e.target.checked)} />
            Log scale
          </label>
          <Segmented label="Window" value={active} onChange={setWindow} options={(Object.keys(WINDOWS) as WindowKey[]).map((k) => ({ value: k, label: k, disabled: !windows.includes(k) }))} />
        </>
      }
      legend={
        fund.length > 1 && (
          <>
            <LegendDot color={seriesColor(0)} label={<>This fund <b className="tabular">{inr(end)}</b></>} />
            {proxyEnd !== undefined && <LegendDot color={token('chart2')} dashed label={<>Large-cap proxy <b className="tabular">{inr(proxyEnd)}</b></>} />}
            {bands.length > 0 && (
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3 w-4 rounded-[3px]" style={{ background: token('warning', 0.3) }} aria-hidden="true" />
                Proxy fall
              </span>
            )}
          </>
        )
      }
      footnote={`${withProxy ? 'Proxy: median daily return of large-cap direct growth funds, built from NAVs. Not an official index or the scheme benchmark.' : 'No market proxy line for this asset class.'} Drag the handles under the chart to zoom.`}
      table={{ columns: ['Date', 'This fund', ...(proxy.length ? ['Proxy'] : [])], rows: thin(fund, 120).map(([d, v]) => [d, Math.round(v), ...(proxy.length ? [Math.round(proxy.find(([pd]) => pd >= d)?.[1] ?? NaN)] : [])]) }}
    >
      {navs.isError ? (
        <ErrorState error={navs.error} onRetry={() => navs.refetch()} compact />
      ) : navs.isLoading ? (
        <Skeleton className="h-[280px]" />
      ) : fund.length < 2 ? (
        <p className="py-12 text-center text-sm text-mf-muted">Not enough NAV history to draw a journey.</p>
      ) : (
        <TimeChart label={`${title} chart`} area zoom log={log} height={height} series={series} bands={bands} format={(v) => inr(v)} tick={inrTick} />
      )}
    </ChartFrame>
  );
}

/** How much the entry date mattered: every rolling-window return, with the median and spread. */
export function RollingDistribution({ code, metrics, fields, initial = '3y' }: FundTabProps & { initial?: '1y' | '3y' | '5y' }) {
  const [window, setWindow] = useState<'1y' | '3y' | '5y'>(initial);
  const rolling = useRolling(code, window);
  const values = useMemo(() => (rolling.data?.points ?? []).map(([, v]) => v), [rolling.data]);
  const v = (k: string) => metrics.values[`rolling_${window}_${k}`] as number | null | undefined;
  const label = window.toUpperCase();
  return (
    <ChartFrame
      title={`Rolling ${label} returns`}
      subtitle={`Annualised return of every ${label} holding period that started on a trading day`}
      controls={<Segmented label="Holding period" value={window} onChange={setWindow} options={[{ value: '1y', label: '1Y' }, { value: '3y', label: '3Y' }, { value: '5y', label: '5Y' }]} />}
      legend={
        <>
          <span>
            Median <b className="tabular">{pct(v('median'))}</b>
          </span>
          <span>
            10th–90th percentile <b className="tabular">{pct(v('p10'))} to {pct(v('p90'))}</b>
          </span>
          <span>
            Positive <b className="tabular">{pct(v('positive_share'), 0)}</b>
          </span>
          <span>
            Worst <b className={cx('tabular', (v('min') ?? 0) < 0 && 'text-mf-loss')}>{pct(v('min'))}</b>
          </span>
        </>
      }
      footnote={`${values.length.toLocaleString('en-IN')} overlapping periods; neighbouring periods share most of their days, so they are not independent samples.`}
      table={{
        columns: ['Statistic', 'Value'],
        rows: ['min', 'p10', 'p25', 'median', 'mean', 'p75', 'p90', 'max', 'positive_share'].map((k) => [fields.get(`rolling_${window}_${k}`)?.label ?? k, pct(v(k))]),
      }}
    >
      {rolling.isError ? (
        <ErrorState error={rolling.error} onRetry={() => rolling.refetch()} compact />
      ) : rolling.isLoading ? (
        <Skeleton className="h-[220px]" />
      ) : values.length < 10 ? (
        <p className="py-12 text-center text-sm text-mf-muted">The history is too short for {label} rolling returns.</p>
      ) : (
        <Histogram
          label={`Distribution of rolling ${label} returns`}
          values={values}
          format={pctTick}
          markers={[
            ...(v('median') != null ? [{ value: v('median')!, label: 'Median', color: token('brandStrong') }] : []),
            { value: 0, label: '0%', color: token('muted') },
          ]}
        />
      )}
    </ChartFrame>
  );
}
