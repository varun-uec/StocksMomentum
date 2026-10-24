import '@fontsource-variable/inter';
import './app/globals.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { mfRoute } from './features/mf/route';

// The entry of /mf (mf.html): it loads none of the stock app's code, which the stock
// entry (main.tsx) must load up front (acceptance review R-02). A link out of /mf,
// such as the shell's link to the stock app, loads that page in full.
const leave = {
  path: '*',
  loader: ({ request }: { request: Request }) => {
    window.location.assign(request.url);
    return null;
  },
};

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={createBrowserRouter([mfRoute, leave])} />
  </StrictMode>,
);
