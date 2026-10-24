import { isRouteErrorResponse, Link, useRouteError } from 'react-router';

function messageOf(error: unknown) {
  if (isRouteErrorResponse(error)) return `${error.status} ${error.statusText}`;
  if (error instanceof Error) return error.message;
  return String(error);
}

/** A failed lazy route should offer a useful recovery path instead of Router's raw exception screen. */
export function RouteErrorBoundary() {
  const error = useRouteError();
  const message = messageOf(error);
  const staleModule = /dynamically imported module|importing a module script failed|failed to fetch|chunkloaderror/i.test(message);

  return (
    <main className="grid min-h-[70vh] place-items-center bg-mf-canvas px-5 py-12 text-mf-ink">
      <section role="alert" className="w-full max-w-xl rounded-[20px] border border-mf-line bg-mf-surface p-6 shadow-card sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-mf-brand">Wickstreet</p>
        <h1 className="mt-3 font-display text-2xl">{staleModule ? 'Wickstreet was updated' : 'This page could not be loaded'}</h1>
        <p className="mt-2 text-sm leading-relaxed text-mf-ink-soft">
          {staleModule
            ? 'This tab is asking for an older page file that is no longer on the local server. Reload to get the current application files.'
            : 'The page hit an unexpected error. Reload to try again, or return to a Wickstreet home page.'}
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button type="button" autoFocus onClick={() => window.location.reload()} className="min-h-11 rounded-[10px] bg-mf-brand px-4 text-sm font-semibold text-white hover:opacity-90">
            Reload Wickstreet
          </button>
          <Link to="/mf" className="inline-flex min-h-11 items-center rounded-[10px] border border-mf-line px-4 text-sm font-medium hover:bg-mf-sunken">
            Mutual-fund Discover
          </Link>
          <Link to="/" className="inline-flex min-h-11 items-center rounded-[10px] border border-mf-line px-4 text-sm font-medium hover:bg-mf-sunken">
            Momentum25 Stocks
          </Link>
        </div>
        <details className="mt-5 text-xs text-mf-muted">
          <summary className="cursor-pointer">Technical details</summary>
          <pre className="mt-2 overflow-auto whitespace-pre-wrap rounded-[8px] bg-mf-sunken p-3 font-mono">{message}</pre>
        </details>
      </section>
    </main>
  );
}
