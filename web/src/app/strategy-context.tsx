'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

const STORAGE_KEY = 'momentum25.selectedStrategy';
const DEFAULT_STRATEGY = 'minervini_trend_template';

interface StrategyContextValue {
  strategyName: string;
  setStrategyName: (name: string) => void;
}

const StrategyContext = createContext<StrategyContextValue | null>(null);

/**
 * The single selected strategy, shared by the dashboard, watchlist, and stock
 * detail so that "which strategy" is one decision the user makes once, not a
 * hardcoded string repeated (and easily left disconnected) on every page.
 */
export function StrategyProvider({ children }: { children: ReactNode }) {
  const [strategyName, setStrategyNameState] = useState(DEFAULT_STRATEGY);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) setStrategyNameState(stored);
  }, []);

  const setStrategyName = (name: string) => {
    setStrategyNameState(name);
    window.localStorage.setItem(STORAGE_KEY, name);
  };

  return (
    <StrategyContext.Provider value={{ strategyName, setStrategyName }}>
      {children}
    </StrategyContext.Provider>
  );
}

export function useStrategy(): StrategyContextValue {
  const ctx = useContext(StrategyContext);
  if (!ctx) throw new Error('useStrategy must be used within a StrategyProvider');
  return ctx;
}

export { DEFAULT_STRATEGY };
