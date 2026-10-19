import { Link, useSearchParams } from 'react-router';
import { returnLabel, safeReturnPath } from '@/lib/return-path';
import { focusRing } from '@/lib/theme';

/** "Back to chart · TCS" when the view was opened with a same-origin `?from=` path; nothing otherwise. */
export function BackLink() {
  const [params] = useSearchParams();
  const path = safeReturnPath(params.get('from'));
  if (!path) return null;
  return (
    <Link to={path} className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium text-[var(--ws-accent)] hover:bg-[var(--ws-muted)] ${focusRing}`}>
      <span aria-hidden="true">←</span>
      {returnLabel(path)}
    </Link>
  );
}
