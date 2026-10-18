/**
 * Three-way merges for saved documents (ADR-013 §5).
 *
 * When a save returns 412, another window saved first. `base` is the version
 * this window last saw from the server, `mine` is this window's current state,
 * and `theirs` is what the server holds now. Each merge keeps both windows'
 * edits where they touch different things.
 */

/** Structural equality for plain JSON values. */
export function sameJson(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/**
 * Field-level merge of two flat records. A field this window changed keeps its
 * value; any other field takes theirs. Never conflicts: used for presentation
 * settings, where the last writer per field is the expected outcome.
 */
export function mergeFields<T extends Record<string, unknown>>(base: T | undefined, mine: T, theirs: T | undefined): T {
  if (!theirs) return mine;
  if (!base) return mine;
  const out: Record<string, unknown> = { ...theirs };
  for (const key of Object.keys(mine)) {
    if (!sameJson(mine[key], base[key])) out[key] = mine[key];
  }
  return out as T;
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
