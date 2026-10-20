import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listStrategies } from '@/lib/api-client';

const STORAGE_KEY = 'momentum25.selectedStrategy';
const HASH_STORAGE_KEY = 'momentum25.selectedStrategyHash';
const DEFAULT_STRATEGY = 'minervini_trend_template';

interface StrategyContextValue {
  strategyName: string;
  strategyHash: string | undefined;
  setStrategyName: (name: string, configHash?: string) => void;
}

const StrategyContext = createContext<StrategyContextValue | null>(null);

/**
 * The single selected strategy, shared by the dashboard, watchlist, and stock
 * detail so that "which strategy" is one decision the user makes once, not a
 * hardcoded string repeated (and easily left disconnected) on every page.
 */
export function StrategyProvider({ children }: { children: ReactNode }) {
  const [strategyName, setStrategyNameState] = useState(DEFAULT_STRATEGY);
  const [strategyHash, setStrategyHashState] = useState<string | undefined>();

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) setStrategyNameState(stored);
    setStrategyHashState(window.localStorage.getItem(HASH_STORAGE_KEY) ?? undefined);
  }, []);

  const setStrategyName = useCallback((name: string, configHash?: string) => {
    setStrategyNameState(name);
    setStrategyHashState(configHash);
    window.localStorage.setItem(STORAGE_KEY, name);
    if (configHash) window.localStorage.setItem(HASH_STORAGE_KEY, configHash);
    else window.localStorage.removeItem(HASH_STORAGE_KEY);
  }, []);

  // A stored choice can name a strategy the workspace no longer offers (a research or an
  // archived one). Reset it here, on every route, so no screen asks for a run that cannot exist.
  // A valid name with no stored hash is left alone: setting the hash would change every
  // strategy-keyed query key a moment after the page loads.
  const { data: strategies } = useQuery({
    queryKey: ['strategies', 'workspace'],
    queryFn: () => listStrategies(false, true),
    staleTime: 30_000,
  });
  useEffect(() => {
    if (!strategies || strategies.length === 0) return;
    const byHash = strategyHash ? strategies.find((s) => s.config_hash === strategyHash) : undefined;
    const byName = strategies.find((s) => s.name === strategyName);
    if (byHash && byHash.name === strategyName) return;
    if (!strategyHash && byName) return;
    const selected = byName ?? strategies[0];
    setStrategyName(selected.name, selected.config_hash);
  }, [strategies, strategyName, strategyHash, setStrategyName]);

  return (
    <StrategyContext.Provider value={{ strategyName, strategyHash, setStrategyName }}>
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
