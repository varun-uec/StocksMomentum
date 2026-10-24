import type { RouteObject } from 'react-router';
import { createElement } from 'react';
import { page } from '@/lib/lazy-page';
import { RouteErrorBoundary } from '@/lib/RouteErrorBoundary';

/** Wickstreet 2.0 mutual funds: its own shell, so no stock chrome or stock queries mount. */
export const mfRoute: RouteObject = {
  path: 'mf',
  ...page(() => import('./routes/layout')),
  errorElement: createElement(RouteErrorBoundary),
  // The shell loads lazily; nothing renders until it arrives.
  HydrateFallback: () => null,
  children: [
    { index: true, ...page(() => import('./routes/discover')) },
    { path: 'screen', ...page(() => import('./routes/screen')) },
    { path: 'funds/:code', ...page(() => import('./routes/fund')) },
    { path: 'studio', ...page(() => import('./routes/studio')) },
    { path: 'compare', ...page(() => import('./routes/compare')) },
    { path: 'simulate', ...page(() => import('./routes/simulate')) },
    { path: 'workspace', ...page(() => import('./routes/workspace')) },
    { path: 'portfolio', ...page(() => import('./routes/portfolio')) },
    { path: 'ask', ...page(() => import('./routes/ask')) },
    { path: '*', ...page(() => import('./routes/not-found')) },
  ],
};
