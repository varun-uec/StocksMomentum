/** React Query hooks over `mfApi`. A snapshot changes once a day, so reads stay fresh for 5 minutes. */
import { keepPreviousData, useQuery, useQueryClient, type Query } from '@tanstack/react-query';
import { useCallback, useMemo, useSyncExternalStore } from 'react';
import { mfApi, type FieldDef, type PeerGroup, type ScreenRequest } from './api';

const FRESH = 5 * 60_000;

export function useFields() {
  const query = useQuery({ queryKey: ['mf', 'fields'], queryFn: ({ signal }) => mfApi.fields(signal), staleTime: FRESH });
  const byId = useMemo(() => new Map<string, FieldDef>((query.data?.fields ?? []).map((f) => [f.id, f])), [query.data]);
  return { ...query, byId };
}

export const usePresets = () =>
  useQuery({ queryKey: ['mf', 'presets'], queryFn: ({ signal }) => mfApi.presets(signal), staleTime: Infinity });

export const useScreen = (body: ScreenRequest | null) =>
  useQuery({
    queryKey: ['mf', 'screen', body],
    queryFn: ({ signal }) => mfApi.screen(body!, signal),
    enabled: !!body,
    staleTime: FRESH,
    placeholderData: keepPreviousData,
  });

export const useFundSearch = (q: string) =>
  useQuery({
    queryKey: ['mf', 'search', q],
    queryFn: ({ signal }) => mfApi.search(q, 8, signal),
    enabled: q.trim().length >= 2,
    staleTime: FRESH,
    placeholderData: keepPreviousData,
  });

/** One fund read, keyed by its endpoint name. */
function fundQuery<T>(name: string, code: string | undefined, fn: (code: string, signal: AbortSignal) => Promise<T>, enabled = true) {
  return {
    queryKey: ['mf', 'fund', code, name],
    queryFn: ({ signal }: { signal: AbortSignal }) => fn(code!, signal),
    enabled: !!code && enabled,
    staleTime: FRESH,
  };
}

export const useFund = (code?: string) => useQuery(fundQuery('detail', code, mfApi.fund));
export const useMetrics = (code?: string, dataRevision?: number) =>
  useQuery(fundQuery(`metrics${dataRevision === undefined ? '' : `-${dataRevision}`}`, code, (c, s) => mfApi.metrics(c, s, dataRevision)));
export const useScore = (code?: string) => useQuery(fundQuery('score', code, mfApi.score));
export const useConfidence = (code?: string, enabled = true) => useQuery(fundQuery('confidence', code, mfApi.confidence, enabled));
export const useNavs = (code?: string) => useQuery(fundQuery('navs', code, (c, s) => mfApi.navs(c, undefined, s)));
export const useAnnual = (code?: string, enabled = true) => useQuery(fundQuery('annual', code, mfApi.annual, enabled));
export const useRolling = (code: string | undefined, window: '1y' | '3y' | '5y', enabled = true) =>
  useQuery(fundQuery(`rolling-${window}`, code, (c, s) => mfApi.rolling(c, window, s), enabled));
export const useDrawdowns = (code?: string, enabled = true) => useQuery(fundQuery('drawdowns', code, (c, s) => mfApi.drawdowns(c, 5, s), enabled));
export const useUnderwater = (code?: string, enabled = true) => useQuery(fundQuery('underwater', code, mfApi.underwater, enabled));
export const useRankHistory = (code?: string, enabled = true) => useQuery(fundQuery('ranks', code, mfApi.rankHistory, enabled));
export const useDirectRegular = (code?: string, enabled = true) => useQuery(fundQuery('dr', code, mfApi.directRegular, enabled));
export const useNearDuplicates = (code?: string, enabled = true) => useQuery(fundQuery('dupes', code, mfApi.nearDuplicates, enabled));
export const useFundRegimes = (code?: string, enabled = true) => useQuery(fundQuery('regimes', code, mfApi.fundRegimes, enabled));
export const useProfile = (code?: string, enabled = true) => useQuery(fundQuery('profile', code, mfApi.profile, enabled));
export const useHoldings = (code?: string, asOf?: string) => useQuery(fundQuery(`holdings-${asOf ?? 'latest'}`, code, (c, s) => mfApi.holdings(c, asOf, s)));
export const useOverlap = (codes: string[], dataRevision?: number) =>
  useQuery({ queryKey: ['mf', 'overlap', codes, dataRevision], queryFn: ({ signal }) => mfApi.overlap(codes, signal, dataRevision), enabled: codes.length >= 2, staleTime: FRESH });
export const useBenchmark = (code?: string, enabled = true) => useQuery(fundQuery('benchmark', code, mfApi.benchmark, enabled));

export const useRegimes = (enabled = true) =>
  useQuery({ queryKey: ['mf', 'regimes'], queryFn: ({ signal }) => mfApi.regimes(signal), staleTime: FRESH, enabled });
export const useRiskFree = () =>
  useQuery({ queryKey: ['mf', 'risk-free'], queryFn: ({ signal }) => mfApi.riskFree(signal), staleTime: FRESH });

export const useCompare = (codes: string[], dataRevision?: number) =>
  useQuery({
    queryKey: ['mf', 'compare', codes, dataRevision],
    queryFn: ({ signal }) => mfApi.compare(codes, undefined, signal, dataRevision),
    enabled: codes.length >= 2,
    staleTime: FRESH,
    placeholderData: keepPreviousData,
  });

export const useFrontier = (group: PeerGroup | null) =>
  useQuery({ queryKey: ['mf', 'frontier', group], queryFn: ({ signal }) => mfApi.frontier(group!, signal), enabled: !!group, staleTime: FRESH });
export const useTransitions = (group: PeerGroup | null) =>
  useQuery({ queryKey: ['mf', 'transitions', group], queryFn: ({ signal }) => mfApi.transitions(group!, signal), enabled: !!group, staleTime: FRESH });

/** Month-end NAVs over 3 years for a set of funds, in one request (at most 50 codes). */
export const useSparklines = (codes: string[]) => {
  const key = [...new Set(codes)].slice(0, 50).sort();
  return useQuery({
    queryKey: ['mf', 'sparklines', key],
    queryFn: ({ signal }) => mfApi.sparklines(key, signal),
    enabled: key.length > 0,
    staleTime: FRESH,
    placeholderData: keepPreviousData,
  });
};

/** The snapshot revision a read came from; a paged screen reports its first page. */
function revisionOf(query: Query): number | undefined {
  const data = query.state.data as { data_revision?: unknown; pages?: { data_revision?: unknown }[] } | undefined;
  const revision = data?.data_revision ?? data?.pages?.[0]?.data_revision;
  return typeof revision === 'number' ? revision : undefined;
}

/**
 * The snapshot revisions behind the reads on screen. More than one means a daily
 * publication landed between reads, so sections would mix data (independent audit
 * A-15). A read pinned on purpose (a scenario replay names `data_revision`) is left out.
 */
export function useScreenRevisions(): { revisions: number[]; refresh: () => void } {
  const client = useQueryClient();
  const cache = client.getQueryCache();
  const key = useSyncExternalStore(
    useCallback((onChange) => cache.subscribe(onChange), [cache]),
    () => {
      const seen = new Set<number>();
      for (const q of cache.findAll({ queryKey: ['mf'], type: 'active' })) {
        const revision = revisionOf(q);
        if (revision !== undefined && !q.queryHash.includes('data_revision')) seen.add(revision);
      }
      return [...seen].sort((a, b) => a - b).join(',');
    },
  );
  const refresh = useCallback(() => void client.invalidateQueries({ queryKey: ['mf'], type: 'active' }), [client]);
  return { revisions: key ? key.split(',').map(Number) : [], refresh };
}
