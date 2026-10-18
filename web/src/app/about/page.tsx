import { Card, PageHeader } from '@/components/shared/Card';

const linkClass = 'text-indigo-600 dark:text-indigo-400 underline hover:text-indigo-800 dark:hover:text-indigo-300';

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <PageHeader title="About Wickstreet" subtitle="Open-source, self-hosted market workspace for NSE daily charts" />
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <Card title="What it is">
          <div className="p-4 space-y-2 text-sm text-slate-600 dark:text-slate-300">
            <p>Wickstreet runs on your own machine. It fetches its own NSE end-of-day data. The project hosts no data and runs no shared service.</p>
            <p>Momentum25 is its analysis engine and built-in screener strategy.</p>
            <p>Wickstreet is not affiliated with or endorsed by TradingView, Inc.</p>
          </div>
        </Card>
        <Card title="Chart library">
          <div className="p-4 space-y-3 text-sm text-slate-600 dark:text-slate-300">
            <p>
              Charts are drawn with{' '}
              <a className={linkClass} href="https://www.tradingview.com/lightweight-charts/" target="_blank" rel="noreferrer">
                TradingView Lightweight Charts™
              </a>
              , licensed under the Apache License, Version 2.0.
            </p>
            <pre data-testid="lightweight-charts-notice" className="whitespace-pre-wrap rounded-md bg-slate-100 dark:bg-slate-900 p-3 text-xs">
              {'TradingView Lightweight Charts™\nCopyright (c) 2025 TradingView, Inc. https://www.tradingview.com/'}
            </pre>
            <p>
              <a className={linkClass} href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
                https://www.tradingview.com/
              </a>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
