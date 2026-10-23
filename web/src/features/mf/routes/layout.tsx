import { Outlet, ScrollRestoration } from 'react-router';
import { Providers } from '@/app/providers';
import { ThemeProvider } from '@/app/theme-provider';
import { MfShell } from '../components/MfShell';
import '../mf.css';

/** Root of every /mf route: the app theme and query providers, then the MF shell. */
export default function MfLayout() {
  return (
    <ThemeProvider>
      <Providers>
        <MfShell>
          <Outlet />
        </MfShell>
        <ScrollRestoration />
      </Providers>
    </ThemeProvider>
  );
}
