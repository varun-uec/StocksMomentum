import { Outlet, ScrollRestoration } from 'react-router';
import { Providers } from './providers';
import { NavBar } from '@/components/shared/NavBar';
import { SiteFooter } from '@/components/shared/SiteFooter';
import { ConflictBanner } from '@/components/workspace/SaveState';
import { ThemeProvider } from './theme-provider';
import { StrategyProvider } from './strategy-context';

/** Shell shared by every route. The theme class is set earlier, by `public/theme-init.js`. */
export default function RootLayout() {
  return (
    <ThemeProvider>
      <Providers>
        <StrategyProvider>
          <NavBar />
          <ConflictBanner />
          <div className="pb-[calc(4.5rem+env(safe-area-inset-bottom))] md:pb-0">
            <Outlet />
            <SiteFooter />
          </div>
          <ScrollRestoration />
        </StrategyProvider>
      </Providers>
    </ThemeProvider>
  );
}
