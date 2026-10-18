/**
 * Crosshair sync between the charts of one layout (M13). A chart publishes the
 * date under its crosshair; every other chart moves its crosshair there. The
 * bus drops a repeat of the last date, so a chart that echoes a position set
 * from code ends the round instead of starting a loop. No React state changes
 * on a mouse move.
 */

export type CrosshairListener = (date: string | null) => void;

export interface CrosshairSync {
  publish: (source: object, date: string | null) => void;
  subscribe: (source: object, listener: CrosshairListener) => () => void;
}

export function createCrosshairSync(): CrosshairSync {
  const listeners = new Map<object, CrosshairListener>();
  let last: string | null = null;
  return {
    publish: (source, date) => {
      if (date === last) return;
      last = date;
      listeners.forEach((listener, owner) => {
        if (owner !== source) listener(date);
      });
    },
    subscribe: (source, listener) => {
      listeners.set(source, listener);
      return () => listeners.delete(source);
    },
  };
}

/** The first date at or after `date`: its own bar, or the week or month bar that holds it. */
export function barAtOrAfter(dates: string[], date: string): string | undefined {
  return dates.find((d) => d >= date);
}
