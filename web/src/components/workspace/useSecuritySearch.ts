import { useEffect, useState } from 'react';
import { searchSecurities } from '@/lib/api-client';
import type { SecuritySearchResult } from '@/lib/types';

/**
 * Symbol suggestions for a typed query. Debounced, so a fast typist issues one
 * request per pause, not per keystroke; the abort controller drops responses
 * for queries the user has moved past, which would otherwise land out of order
 * and show stale suggestions.
 */
export function useSecuritySearch(rawQuery: string, limit = 8) {
  const query = rawQuery.trim();
  const [results, setResults] = useState<SecuritySearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (query.length < 1) {
      setResults([]);
      setSearching(false);
      return;
    }
    const controller = new AbortController();
    setSearching(true);
    const timer = setTimeout(() => {
      searchSecurities(query, limit, controller.signal)
        .then(setResults)
        .catch(() => {
          /* aborted or offline — leave the last suggestions in place */
        })
        .finally(() => setSearching(false));
    }, 150);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, limit]);

  return { query, results, searching };
}
