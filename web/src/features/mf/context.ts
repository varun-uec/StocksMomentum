/**
 * Research context that travels between screens (audit U-01, U-08): the funds
 * this visitor opened last. Studio, Lab and Compare start from them, or from a
 * named example set, so no tool opens empty. It is a per-browser convenience in
 * localStorage; an unavailable store falls back to the examples.
 */
import { useSyncExternalStore } from 'react';

const KEY = 'mf-recent';
const MAX = 5;

/** Example funds when the visitor has opened none: three flexi caps with long NAV histories. */
export const EXAMPLES = [
  { code: '122639', name: 'Parag Parikh Flexi Cap Fund' },
  { code: '118955', name: 'HDFC Flexi Cap Fund' },
  { code: '120166', name: 'Kotak Flexi Cap Fund' },
] as const;

const listeners = new Set<() => void>();
let cache: string | null = null;

function read(): string {
  try {
    cache = localStorage.getItem(KEY) ?? '';
  } catch {
    cache ??= '';
  }
  return cache;
}

function parse(text: string): string[] {
  return text.split(',').filter((c) => /^\d{1,9}$/.test(c));
}

/** Put a fund first in the recent list. */
export function rememberFund(code: string) {
  const next = [code, ...parse(read()).filter((c) => c !== code)].slice(0, MAX).join(',');
  if (next === cache) return;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    // A blocked store keeps the list for this visit only.
  }
  cache = next;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The recent funds, newest first. */
export function useRecentFunds(): string[] {
  const text = useSyncExternalStore(subscribe, () => cache ?? read());
  return parse(text);
}

/** `n` funds to start a tool with: recent ones first, then examples; `example` says if any came from the examples. */
export function startingFunds(recent: string[], n: number): { codes: string[]; example: boolean } {
  const codes = [...new Set([...recent, ...EXAMPLES.map((e) => e.code)])].slice(0, n);
  return { codes, example: codes.some((c) => !recent.includes(c)) };
}
