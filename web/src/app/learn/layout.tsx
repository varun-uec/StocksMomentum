'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, type ReactNode } from 'react';
import { focusRing } from '@/lib/theme';

const SECTIONS = [
  { href: '/learn', label: 'Overview' },
  { href: '/learn/momentum-investing', label: 'Momentum Investing' },
  { href: '/learn/minervini-methodology', label: 'Minervini Methodology' },
  { href: '/learn/momentum25-methodology', label: 'Momentum25 Methodology' },
  { href: '/learn/scoring-guide', label: 'Scoring Guide' },
  { href: '/learn/rule-guide', label: 'Rule Guide' },
  { href: '/learn/faq', label: 'FAQ' },
];

export default function LearnLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8 flex flex-col lg:flex-row gap-6 lg:gap-8">
        {/* Mobile section selector */}
        <div className="lg:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-expanded={mobileOpen}
            aria-label="Toggle learning sections"
            className={`w-full flex items-center justify-between px-4 py-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm font-medium text-slate-700 dark:text-slate-300 ${focusRing}`}
          >
            <span>{SECTIONS.find((s) => pathname === s.href)?.label ?? 'Learning Center'}</span>
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              className={`w-5 h-5 transition-transform ${mobileOpen ? 'rotate-180' : ''}`}
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.25a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.06z"
              />
            </svg>
          </button>
          {mobileOpen && (
            <nav className="mt-2 space-y-0.5 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
              {SECTIONS.map((s) => {
                const active = pathname === s.href;
                return (
                  <Link
                    key={s.href}
                    href={s.href}
                    onClick={() => setMobileOpen(false)}
                    aria-current={active ? 'page' : undefined}
                    className={`block px-4 py-2.5 text-sm transition-colors ${
                      active
                        ? 'bg-indigo-100 dark:bg-indigo-600/20 text-indigo-700 dark:text-indigo-300 font-medium'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    {s.label}
                  </Link>
                );
              })}
            </nav>
          )}
        </div>

        {/* Desktop sidebar */}
        <aside className="w-full lg:w-56 shrink-0 hidden lg:block">
          <div className="sticky top-20">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3">Learning Center</div>
            <nav className="space-y-0.5">
              {SECTIONS.map((s) => {
                const active = pathname === s.href;
                return (
                  <Link
                    key={s.href}
                    href={s.href}
                    aria-current={active ? 'page' : undefined}
                    className={`block px-3 py-2 rounded-md text-sm transition-colors ${focusRing} ${
                      active
                        ? 'bg-indigo-100 dark:bg-indigo-600/20 text-indigo-700 dark:text-indigo-300 font-medium'
                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    {s.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        </aside>

        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </main>
  );
}
