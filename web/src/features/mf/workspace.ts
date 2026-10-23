/**
 * The personal workspace: saved records on the server (`/workspace/records`, W1)
 * and the compare tray, which holds only public fund codes for this tab.
 *
 * Every save sends the version it read. A 412 means another window saved first:
 * set edits (add or remove a code) re-apply on the fresh record, and any other
 * edit surfaces as a conflict instead of overwriting.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useSyncExternalStore } from 'react';
import { MfApiError, request } from './api';

export type RecordKind = 'watchlist' | 'screen' | 'note' | 'brief' | 'scenario';

export interface ResearchRecord<B = Record<string, unknown>> {
  id: string;
  kind: RecordKind;
  name: string;
  body: B;
  schema_version: number;
  version: number;
  created_at: string;
  updated_at: string;
  archived: boolean;
}

export interface WatchlistBody {
  codes: string[];
}
export interface NoteBody {
  text: string;
  code?: string;
  fund?: string;
}

interface Draft<B> {
  name: string;
  body: B;
  archived?: boolean;
}

export const workspaceApi = {
  list: (kind?: RecordKind, archived = false) =>
    request<ResearchRecord[]>(`/workspace/records?${new URLSearchParams({ ...(kind ? { kind } : {}), archived: String(archived) })}`),
  get: <B = Record<string, unknown>>(id: string) => request<ResearchRecord<B>>(`/workspace/records/${id}`),
  create: <B>(kind: RecordKind, draft: Draft<B>) =>
    request<ResearchRecord<B>>('/workspace/records', { method: 'POST', body: JSON.stringify({ kind, ...draft }) }),
  save: <B>(record: ResearchRecord<B>, draft: Draft<B>) =>
    request<ResearchRecord<B>>(`/workspace/records/${record.id}`, {
      method: 'PUT',
      headers: { 'If-Match': `"${record.version}"` },
      body: JSON.stringify({ archived: record.archived, ...draft }),
    }),
};

export const isConflict = (error: unknown) => error instanceof MfApiError && error.status === 412;

/** Add or remove one code; order is kept and a code appears once. */
export function toggleCode(codes: string[], code: string, on: boolean): string[] {
  if (on) return codes.includes(code) ? codes : [...codes, code];
  return codes.filter((c) => c !== code);
}

const recordsKey = (kind?: RecordKind, archived = false) => ['mf', 'workspace', kind ?? 'all', archived];

export function useRecords<B = Record<string, unknown>>(kind?: RecordKind, archived = false) {
  return useQuery({
    queryKey: recordsKey(kind, archived),
    queryFn: () => workspaceApi.list(kind, archived) as Promise<ResearchRecord<B>[]>,
    staleTime: 10_000,
  });
}

/** Create, save and archive records; every change refreshes the lists. */
export function useRecordMutations<B>(kind: RecordKind) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ['mf', 'workspace'] });
  const create = useMutation({ mutationFn: (draft: Draft<B>) => workspaceApi.create(kind, draft), onSuccess: refresh });
  const save = useMutation({
    mutationFn: ({ record, draft }: { record: ResearchRecord<B>; draft: Draft<B> }) => workspaceApi.save(record, draft),
    onSettled: refresh,
  });
  return { create, save };
}

const DEFAULT_WATCHLIST = 'My watchlist';

/**
 * The first watchlist, created on the first add. A toggle that loses a race
 * re-reads the record and re-applies itself once.
 */
export function useWatchlist() {
  const client = useQueryClient();
  const lists = useRecords<WatchlistBody>('watchlist');
  const list = lists.data?.[0];
  const codes = list?.body.codes ?? [];

  const mutation = useMutation({
    mutationFn: async ({ code, on }: { code: string; on: boolean }) => {
      const apply = (record: ResearchRecord<WatchlistBody>) =>
        workspaceApi.save(record, { name: record.name, body: { codes: toggleCode(record.body.codes ?? [], code, on) } });
      if (!list) return workspaceApi.create<WatchlistBody>('watchlist', { name: DEFAULT_WATCHLIST, body: { codes: on ? [code] : [] } });
      try {
        return await apply(list);
      } catch (error) {
        if (!isConflict(error)) throw error;
        return apply(await workspaceApi.get<WatchlistBody>(list.id));
      }
    },
    onSettled: () => client.invalidateQueries({ queryKey: ['mf', 'workspace'] }),
  });

  return {
    list,
    codes,
    loading: lists.isLoading,
    error: lists.error ?? mutation.error,
    pending: mutation.isPending,
    isWatched: (code: string) => codes.includes(code),
    toggle: (code: string) => mutation.mutate({ code, on: !codes.includes(code) }),
  };
}

// ── Compare tray: up to five public fund codes for this tab (sessionStorage) ──

export const COMPARE_LIMIT = 5;
export interface TrayFund {
  code: string;
  name: string;
}

const TRAY_KEY = 'mf-compare-tray';
const listeners = new Set<() => void>();
let tray: TrayFund[] = readTray();

function readTray(): TrayFund[] {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(TRAY_KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter((f) => typeof f?.code === 'string').slice(0, COMPARE_LIMIT) : [];
  } catch {
    return [];
  }
}

function writeTray(next: TrayFund[]) {
  tray = next;
  try {
    sessionStorage.setItem(TRAY_KEY, JSON.stringify(next));
  } catch {
    // Storage can be blocked; the tray still works for this page.
  }
  listeners.forEach((listener) => listener());
}

/** Add a fund unless it is there or the tray is full; returns false when full. */
export function addToTray(fund: TrayFund): boolean {
  if (tray.some((f) => f.code === fund.code)) return true;
  if (tray.length >= COMPARE_LIMIT) return false;
  writeTray([...tray, fund]);
  return true;
}

export const removeFromTray = (code: string) => writeTray(tray.filter((f) => f.code !== code));
export const clearTray = () => writeTray([]);
export const setTray = (funds: TrayFund[]) => writeTray(funds.slice(0, COMPARE_LIMIT));

export function useCompareTray() {
  const funds = useSyncExternalStore(
    (onChange) => {
      listeners.add(onChange);
      return () => listeners.delete(onChange);
    },
    () => tray,
  );
  const has = useCallback((code: string) => funds.some((f) => f.code === code), [funds]);
  return { funds, has, full: funds.length >= COMPARE_LIMIT };
}
