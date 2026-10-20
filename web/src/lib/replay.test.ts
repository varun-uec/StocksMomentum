import { describe, expect, it } from 'vitest';
import { hiddenInReplay, nextSession, sessionOnOrBefore, upTo, withHidden } from '@/lib/replay';

const drawing = (id: string, ...dates: string[]) => ({ id, points: dates.map((date) => ({ date, price: 1 })) });

describe('bar replay', () => {
  const saved = [drawing('a', '2026-01-02', '2026-01-05'), drawing('b', '2026-01-02', '2026-02-01'), drawing('c', '2026-03-01')];

  it('hides saved drawings with any anchor after the replay date, but never one made during replay', () => {
    expect([...hiddenInReplay(saved, '2026-01-31', new Set())]).toEqual(['b', 'c']);
    expect([...hiddenInReplay(saved, '2026-02-01', new Set())]).toEqual(['c']);
    expect([...hiddenInReplay(saved, '2026-01-31', new Set(['c']))]).toEqual(['b']);
  });

  it('puts hidden drawings back in their saved places after an edit, and keeps new ones', () => {
    const hidden = new Set(['b']);
    const moved = { ...saved[0], points: [{ date: '2026-01-03', price: 2 }] };
    const made = drawing('d', '2026-01-10');
    expect(withHidden([moved, saved[2], made], saved, hidden)).toEqual([moved, saved[1], saved[2], made]);
    // Removing every visible drawing removes only those.
    expect(withHidden([], saved, hidden)).toEqual([saved[1]]);
  });

  it('cuts rows at the replay date and leaves them whole outside replay', () => {
    const rows = [{ date: '2026-01-01' }, { date: '2026-01-02' }, { date: '2026-01-03' }];
    expect(upTo(rows, '2026-01-02')).toEqual(rows.slice(0, 2));
    expect(upTo(rows, undefined)).toBe(rows);
  });

  it('steps to the next stored session and snaps a chosen date back to one', () => {
    const sessions = ['2026-01-02', '2026-01-05', '2026-01-06'];
    expect(nextSession(sessions, '2026-01-02')).toBe('2026-01-05');
    expect(nextSession(sessions, '2026-01-03')).toBe('2026-01-05');
    expect(nextSession(sessions, '2026-01-06')).toBeNull();
    expect(sessionOnOrBefore(sessions, '2026-01-04')).toBe('2026-01-02');
    expect(sessionOnOrBefore(sessions, '2025-12-01')).toBe('2026-01-02');
  });
});
