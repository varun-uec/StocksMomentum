import { describe, expect, test, vi } from 'vitest';
import { barAtOrAfter, createCrosshairSync } from './crosshair-sync';

describe('createCrosshairSync', () => {
  test('a date reaches every other chart once, and an echo of it goes nowhere', () => {
    const bus = createCrosshairSync();
    const [a, b, c] = [{}, {}, {}];
    const toA = vi.fn();
    const toB = vi.fn((date: string | null) => bus.publish(b, date)); // b echoes what it is given
    const toC = vi.fn();
    bus.subscribe(a, toA);
    bus.subscribe(b, toB);
    const stop = bus.subscribe(c, toC);
    bus.publish(a, '2026-08-03');
    expect(toA).not.toHaveBeenCalled();
    expect(toB).toHaveBeenCalledTimes(1);
    expect(toC).toHaveBeenCalledTimes(1);
    stop();
    bus.publish(a, null);
    expect(toB).toHaveBeenLastCalledWith(null);
    expect(toC).toHaveBeenCalledTimes(1);
  });
});

describe('barAtOrAfter', () => {
  test('a daily date finds its weekly bar; a date past the last bar finds none', () => {
    const weeks = ['2026-07-03', '2026-07-10'];
    expect(barAtOrAfter(weeks, '2026-07-08')).toBe('2026-07-10');
    expect(barAtOrAfter(weeks, '2026-07-03')).toBe('2026-07-03');
    expect(barAtOrAfter(weeks, '2026-07-13')).toBeUndefined();
  });
});
