import { Outlet, ScrollRestoration } from 'react-router';
import { Providers } from './providers';
import { WorkstationShell } from '@/components/shell/WorkstationShell';
import { ThemeProvider } from './theme-provider';
import { StrategyProvider } from './strategy-context';

/** Shell shared by every route. The theme class is set earlier, by `public/theme-init.js`. */
export default function RootLayout() {
  return (
    <ThemeProvider>
      <Providers>
        <StrategyProvider>
          <WorkstationShell>
            <Outlet />
          </WorkstationShell>
          <ScrollRestoration />
        </StrategyProvider>
      </Providers>
    </ThemeProvider>
  );
}
