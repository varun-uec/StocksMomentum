import '@fontsource-variable/inter';
import './app/globals.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider, type RouteObject } from 'react-router';
import RootLayout from './app/layout';
import { mfRoute } from './features/mf/route';
import { page } from './lib/lazy-page';
import { RouteErrorBoundary } from './lib/RouteErrorBoundary';
import { importLocalDrawings, importLocalPresentation } from './lib/local-import';

const routes: RouteObject[] = [
  mfRoute,
  {
    element: <RootLayout />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, ...page(() => import('./app/page')) },
      { path: 'chart', ...page(() => import('./app/chart/page')) },
      { path: 'chart/:symbol', ...page(() => import('./app/chart/page')) },
      { path: 'stock/:symbol', ...page(() => import('./app/stock/[symbol]/page')) },
      { path: 'stock/:symbol/analysis', ...page(() => import('./app/stock/[symbol]/analysis/page')) },
      { path: 'stock/:symbol/elliott-wave', ...page(() => import('./app/stock/[symbol]/elliott-wave/page')) },
      { path: 'watchlist', ...page(() => import('./app/watchlist/page')) },
      { path: 'market', ...page(() => import('./app/market/page')) },
      {
        // The Research workspace: one tab row over the research routes; their URLs are unchanged.
        ...page(() => import('./app/research/layout')),
        children: [
          { path: 'strategies', ...page(() => import('./app/strategies/page')) },
          { path: 'studio', ...page(() => import('./app/studio/page')) },
          { path: 'validation', ...page(() => import('./app/validation/page')) },
          { path: 'backtest', ...page(() => import('./app/backtest/page')) },
          { path: 'historical', ...page(() => import('./app/historical/page')) },
          { path: 'experiment', ...page(() => import('./app/experiment/page')) },
          { path: 'analytics', ...page(() => import('./app/analytics/page')) },
        ],
      },
      { path: 'data', ...page(() => import('./app/data/page')) },
      { path: 'about', ...page(() => import('./app/about/page')) },
      {
        path: 'learn',
        ...page(() => import('./app/learn/layout')),
        children: [
          { index: true, ...page(() => import('./app/learn/page')) },
          { path: 'momentum-investing', ...page(() => import('./app/learn/momentum-investing/page')) },
          { path: 'minervini-methodology', ...page(() => import('./app/learn/minervini-methodology/page')) },
          { path: 'momentum25-methodology', ...page(() => import('./app/learn/momentum25-methodology/page')) },
          { path: 'scoring-guide', ...page(() => import('./app/learn/scoring-guide/page')) },
          { path: 'rule-guide', ...page(() => import('./app/learn/rule-guide/page')) },
          { path: 'faq', ...page(() => import('./app/learn/faq/page')) },
        ],
      },
      // Engineering diagnostic for the multi-chart smoke check (ADR-013 S7). Not in the navigation.
      { path: 'lab/chart-grid', ...page(() => import('./app/lab/chart-grid/page')) },
      { path: '*', ...page(() => import('./app/not-found')) },
    ],
  },
];

void importLocalDrawings();

// Settings go first, so no screen saves its defaults before the import fills them in.
// With nothing to import, this finishes without a request.
void importLocalPresentation().finally(() =>
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <RouterProvider router={createBrowserRouter(routes)} />
    </StrictMode>,
  ),
);
