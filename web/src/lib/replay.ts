/**
 * Bar replay (plan B2): the chart as it stood on a past session. The server
 * cuts every price and indicator series at the replay date (`as_of`). These
 * helpers cover what the browser holds itself: drawings, benchmark closes and
 * the next session to step to.
 */

/** The run Momentum25 context uses in replay: the newest on or before the date; `null` if none, `undefined` while it loads. */
export interface ReplayState {
  date: string;
  runId: number | null | undefined;
}

interface Dated {
  id: string;
  points: { date: string }[];
}

const lastDate = (d: Dated) => d.points.reduce((max, p) => (p.date > max ? p.date : max), '');

/**
 * Drawings replay hides: saved before replay with an anchor after the replay
 * date, because their shape shows where price went. A drawing made during this
 * replay stays visible wherever its anchors are.
 */
export function hiddenInReplay(drawings: Dated[], date: string, madeInReplay: ReadonlySet<string>): Set<string> {
  return new Set(drawings.filter((d) => !madeInReplay.has(d.id) && lastDate(d) > date).map((d) => d.id));
}

/**
 * The chart's edit of the visible drawings, with the hidden ones put back in
 * their saved places. Hidden drawings are never dropped or changed by replay.
 */
export function withHidden<T extends { id: string }>(edited: T[], saved: T[], hidden: ReadonlySet<string>): T[] {
  const byId = new Map(edited.map((d) => [d.id, d]));
  const savedIds = new Set(saved.map((d) => d.id));
  return [
    ...saved.flatMap((d) => (hidden.has(d.id) ? [d] : byId.has(d.id) ? [byId.get(d.id)!] : [])),
    ...edited.filter((d) => !savedIds.has(d.id)),
  ];
}

/** Rows dated on or before the replay date; all rows outside replay. */
export function upTo<T extends { date: string }>(rows: T[], date: string | undefined): T[] {
  return date ? rows.filter((r) => r.date <= date) : rows;
}

/** The first session after `date`, or null at the end of the stored data. */
export function nextSession(sessions: string[], date: string): string | null {
  return sessions.find((d) => d > date) ?? null;
}

/** The session on or before `date` (a weekend snaps back to Friday), else the first session. */
export function sessionOnOrBefore(sessions: string[], date: string): string | undefined {
  return sessions.filter((d) => d <= date).at(-1) ?? sessions[0];
}
