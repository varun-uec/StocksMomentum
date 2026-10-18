/**
 * One-time import of drawings saved in this browser before M11 (ADR-013 §5).
 *
 * Phase 9.5 kept drawings in `localStorage` under `chart-prefs:<symbol>`. Each
 * symbol's drawings are sent with `If-None-Match: *`, so the import only
 * creates documents that do not exist yet: a second browser, or a second run,
 * changes nothing (the server copy wins). A marker records each finished key.
 * The original keys stay in place as the backup.
 */

import { LEGACY_KEY_PREFIX, parseLegacyPreferences } from '@/lib/chart-preferences';
import { reloadIfPristine } from '@/lib/server-document';
import { drawingsSpec } from '@/lib/workspace';

const MARKER_PREFIX = 'wickstreet:imported:';

function legacyKeys(): string[] {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key?.startsWith(LEGACY_KEY_PREFIX) && !localStorage.getItem(MARKER_PREFIX + key)) keys.push(key);
  }
  return keys;
}

/** Import every not-yet-imported symbol. Safe to call on every start. */
export async function importLocalDrawings(http: typeof fetch = (...a) => fetch(...a)): Promise<number> {
  let keys: string[];
  try {
    keys = legacyKeys();
  } catch {
    return 0; // storage unavailable: nothing to import
  }
  let imported = 0;
  for (const key of keys) {
    const symbol = key.slice(LEGACY_KEY_PREFIX.length);
    const { drawings } = parseLegacyPreferences(localStorage.getItem(key));
    if (drawings.length > 0) {
      const res = await http(drawingsSpec(symbol).path, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'If-None-Match': '*' },
        body: JSON.stringify({ drawings }),
      }).catch(() => null);
      // 201 imported; 412 the server already had them (server wins). Anything else: retry next start.
      if (!res || (res.status !== 201 && res.status !== 412)) continue;
      if (res.status === 201) {
        imported += 1;
        reloadIfPristine(drawingsSpec(symbol).path);
      }
    }
    localStorage.setItem(MARKER_PREFIX + key, new Date().toISOString());
  }
  return imported;
}
