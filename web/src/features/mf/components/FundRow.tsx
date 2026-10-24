/** A fund in a short list: name, category, 3Y CAGR and 1Y return, with an optional action. */
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { categoryShort, pct, schemeName } from '../format';
import { useMetrics } from '../queries';
import { Delta, Skeleton } from './ui';

export function FundRow({ code, action }: { code: string; action?: ReactNode }) {
  const metrics = useMetrics(code);
  const m = metrics.data;
  if (!m) return <Skeleton className="my-2 h-10" />;
  return (
    <div className="flex items-center gap-3 py-2.5">
      <Link to={`/mf/funds/${code}`} className="group flex min-w-0 flex-1 items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm font-medium group-hover:text-mf-brand-strong">{schemeName(m.name)}</p>
          <p className="text-xs text-mf-muted">{categoryShort(String(m.values.category))}</p>
        </div>
        <div className="text-right text-xs">
          <p className="tabular text-sm font-medium">{pct(m.values.cagr_3y)}</p>
          <p className="text-mf-muted">3Y CAGR</p>
        </div>
        <div className="w-16 text-right text-xs">
          <Delta value={m.values.ret_1y} className="text-sm font-medium" />
          <p className="text-mf-muted">1Y</p>
        </div>
      </Link>
      {action}
    </div>
  );
}
