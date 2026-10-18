import { Link } from 'react-router';

/** Credit for the chart library on every page, as its licence asks (ADR-012). */
export function SiteFooter() {
  return (
    <footer className="border-t border-slate-200 dark:border-slate-800 px-4 py-3 text-center text-xs text-slate-500 dark:text-slate-400">
      Charts by{' '}
      <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="underline hover:text-slate-700 dark:hover:text-slate-200">
        TradingView Lightweight Charts™
      </a>
      {' · '}
      <Link to="/about" className="underline hover:text-slate-700 dark:hover:text-slate-200">
        About Wickstreet
      </Link>
    </footer>
  );
}
