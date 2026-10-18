/**
 * Three-way merges for saved documents (ADR-013 §5).
 *
 * When a save returns 412, another window saved first. `base` is the version
 * this window last saw from the server, `mine` is this window's current state,
 * and `theirs` is what the server holds now. Each merge keeps both windows'
 * edits where they touch different things.
 */

/** The value with object keys sorted, so key order never decides equality. */
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((k) => [k, canonical((value as Record<string, unknown>)[k])]));
  }
  return value;
}

/** Structural equality for plain JSON values, whatever the key order (the server's may differ). */
export function sameJson(a: unknown, b: unknown): boolean {
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}

export interface FieldMerge<T> {
  /** The merge, with this window's value of each conflicting field. */
  mine: T;
  /** The same merge, with the server's value of each conflicting field. */
  theirs: T;
  /** Fields both windows changed differently. Empty means the merge is clean. */
  conflicts: string[];
}

/**
 * Field-level merge of two flat records (presentation settings).
 *
 * Per field: if only one side changed it, that side wins. If both changed it
 * the same way, fine. If both changed it differently, it is a conflict and the
 * caller asks the user. With no base (both sides created the record), every
 * differing field conflicts.
 *
 * `latestWins` names fields that record where the owner is, not what they
 * built, such as the open symbol. For those the newest navigation is the
 * right value, so this window's value wins without a conflict.
 */
export function mergeFields<T extends Record<string, unknown>>(
  base: T | undefined,
  mine: T,
  theirs: T | undefined,
  latestWins: readonly string[] = [],
): FieldMerge<T> {
  if (!theirs) return { mine, theirs: mine, conflicts: [] };
  const b: Record<string, unknown> = base ?? {};
  const resolvedMine: Record<string, unknown> = {};
  const resolvedTheirs: Record<string, unknown> = {};
  const conflicts: string[] = [];
  for (const key of new Set([...Object.keys(theirs), ...Object.keys(mine)])) {
    const [bi, mi, ti] = [b[key], mine[key], theirs[key]];
    let pick: { mine: unknown; theirs: unknown };
    if (sameJson(mi, bi)) pick = { mine: ti, theirs: ti };
    else if (sameJson(ti, bi) || sameJson(mi, ti) || latestWins.includes(key)) pick = { mine: mi, theirs: mi };
    else {
      conflicts.push(key);
      pick = { mine: mi, theirs: ti };
    }
    if (pick.mine !== undefined) resolvedMine[key] = pick.mine;
    if (pick.theirs !== undefined) resolvedTheirs[key] = pick.theirs;
  }
  return { mine: resolvedMine as T, theirs: resolvedTheirs as T, conflicts };
}

export interface ItemMerge<T> {
  /** The merge, with this window's version of each conflicting item. */
  mine: T[];
  /** The same merge, with the server's version of each conflicting item. */
  theirs: T[];
  /** Ids both windows changed differently. Empty means the merge is clean. */
  conflicts: string[];
}

/**
 * Merge two edited lists of items with stable ids (drawings).
 *
 * Per id: if only one side changed it (added, edited or deleted), that side
 * wins. If both changed it the same way, fine. If both changed it differently,
 * it is a conflict and the caller asks the user. Order follows the server's
 * list, then items only this window added.
 */
export function mergeById<T extends { id: string }>(base: T[], mine: T[], theirs: T[]): ItemMerge<T> {
  const byId = (items: T[]) => new Map(items.map((item) => [item.id, item]));
  const b = byId(base);
  const m = byId(mine);
  const t = byId(theirs);
  const order = [...theirs.map((x) => x.id), ...mine.map((x) => x.id).filter((id) => !t.has(id))];

  const resolvedMine: T[] = [];
  const resolvedTheirs: T[] = [];
  const conflicts: string[] = [];
  for (const id of new Set(order)) {
    const [bi, mi, ti] = [b.get(id), m.get(id), t.get(id)];
    let pick: { mine?: T; theirs?: T };
    if (sameJson(mi, bi)) pick = { mine: ti, theirs: ti };
    else if (sameJson(ti, bi) || sameJson(mi, ti)) pick = { mine: mi, theirs: mi };
    else {
      conflicts.push(id);
      pick = { mine: mi, theirs: ti };
    }
    if (pick.mine) resolvedMine.push(pick.mine);
    if (pick.theirs) resolvedTheirs.push(pick.theirs);
  }
  return { mine: resolvedMine, theirs: resolvedTheirs, conflicts };
}
