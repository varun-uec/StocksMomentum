'use client';

import { type ReactNode } from 'react';

interface CardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  badge?: { text: string; color: string };
}

export function Card({ title, subtitle, children, className = '', badge }: CardProps) {
  return (
    <div
      className={`rounded-xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/50 shadow-sm ${className}`}
    >
      {(title || badge) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700/40 gap-4">
          <div className="min-w-0">
            {title && <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{title}</h3>}
            {subtitle && <p className="text-xs text-slate-500 mt-0.5 truncate">{subtitle}</p>}
          </div>
          {badge && (
            <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${badge.color}`}>
              {badge.text}
            </span>
          )}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

export function MetricCard({
  label,
  value,
  change,
  changeLabel,
  color = 'text-slate-800 dark:text-slate-200',
}: {
  label: string;
  value: string;
  change?: string;
  changeLabel?: string;
  color?: string;
}) {
  const isPositive = change && parseFloat(change) > 0;
  const isNegative = change && parseFloat(change) < 0;

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700/40 bg-slate-50 dark:bg-slate-800/30 px-4 py-3 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`text-xl font-bold tabular-nums mt-1 ${color}`}>{value}</div>
      {(change || changeLabel) && (
        <div className="flex items-center gap-1.5 mt-1">
          {change && (
            <span
              className={`text-xs font-medium tabular-nums ${
                isPositive
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : isNegative
                    ? 'text-rose-600 dark:text-rose-400'
                    : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              {isPositive ? '+' : ''}
              {change}
            </span>
          )}
          {changeLabel && <span className="text-xs text-slate-500">{changeLabel}</span>}
        </div>
      )}
    </div>
  );
}

export function Badge({ children, color = 'slate' }: { children: ReactNode; color?: string }) {
  const colorMap: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300',
    emerald: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300',
    rose: 'bg-rose-100 text-rose-700 dark:bg-rose-900/50 dark:text-rose-300',
    amber: 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300',
    blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300',
    indigo: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colorMap[color] || colorMap.slate}`}>
      {children}
    </span>
  );
}

export function StatusDot({ passed }: { passed: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        passed ? 'bg-emerald-500 dark:bg-emerald-400' : 'bg-slate-300 dark:bg-slate-600'
      }`}
    />
  );
}

export function LoadingSpinner({ text = 'Loading…' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <div className="w-6 h-6 border-2 border-slate-200 dark:border-slate-700 border-t-indigo-500 rounded-full animate-spin" />
      <div className="text-slate-500 text-sm">{text}</div>
    </div>
  );
}

export function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-16 px-4">
      <div className="flex items-start gap-3 max-w-xl rounded-xl border border-rose-200 dark:border-rose-800/50 bg-rose-50 dark:bg-rose-950/30 p-4">
        <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-rose-500 shrink-0 mt-0.5">
          <path
            fillRule="evenodd"
            clipRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
          />
        </svg>
        <p className="text-rose-700 dark:text-rose-300 text-sm">{message}</p>
      </div>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-8 h-8 text-slate-300 dark:text-slate-600 mb-3">
        <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
      </svg>
      <p className="text-slate-500 dark:text-slate-400 text-sm max-w-md">{message}</p>
    </div>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <header className="border-b border-slate-200 dark:border-slate-800 px-4 sm:px-6 lg:px-8 py-4">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{title}</h1>
          {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
        {children && <div className="flex items-center gap-3">{children}</div>}
      </div>
    </header>
  );
}
