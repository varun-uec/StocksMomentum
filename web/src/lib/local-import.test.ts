import { beforeEach, describe, expect, test, vi } from 'vitest';
import { importLocalDrawings } from './local-import';

class MemoryStorage {
  private items = new Map<string, string>();
  get length() {
    return this.items.size;
  }
  key(i: number) {
    return [...this.items.keys()][i] ?? null;
  }
  getItem(k: string) {
    return this.items.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.items.set(k, v);
  }
  removeItem(k: string) {
    this.items.delete(k);
  }
}

const legacy = (drawings: unknown[]) =>
  JSON.stringify({ timeframe: '1Y', activeMas: [50], activePanes: [], drawings });
const line = { id: 'a1', kind: 'trendline', color: '#6366f1', points: [{ date: '2026-08-03', price: 1 }, { date: '2026-08-04', price: 2 }] };

beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoryStorage());
});

describe('importLocalDrawings', () => {
  test('creates each symbol once, with If-None-Match: *, and keeps the original key', async () => {
    localStorage.setItem('chart-prefs:TCS', legacy([line]));
    const http = vi.fn().mockResolvedValue(new Response(null, { status: 201 }));
    expect(await importLocalDrawings(http)).toBe(1);
    const [url, init] = http.mock.calls[0];
    expect(url).toBe('/api/v1/drawings/TCS');
    expect(init.headers['If-None-Match']).toBe('*');
    expect(JSON.parse(init.body)).toEqual({ drawings: [line] });
    expect(localStorage.getItem('chart-prefs:TCS')).not.toBeNull();

    expect(await importLocalDrawings(http)).toBe(0);
    expect(http).toHaveBeenCalledTimes(1);
  });

  test('a server copy wins: 412 marks the key done without overwriting', async () => {
    localStorage.setItem('chart-prefs:INFY', legacy([line]));
    const http = vi.fn().mockResolvedValue(new Response(null, { status: 412 }));
    expect(await importLocalDrawings(http)).toBe(0);
    expect(await importLocalDrawings(http)).toBe(0);
    expect(http).toHaveBeenCalledTimes(1);
  });

  test('a failed request is retried on the next start', async () => {
    localStorage.setItem('chart-prefs:SBIN', legacy([line]));
    const failing = vi.fn().mockRejectedValue(new Error('offline'));
    expect(await importLocalDrawings(failing)).toBe(0);
    const ok = vi.fn().mockResolvedValue(new Response(null, { status: 201 }));
    expect(await importLocalDrawings(ok)).toBe(1);
  });

  test('symbols with no drawings are marked without a request; invalid drawings are dropped', async () => {
    localStorage.setItem('chart-prefs:ITC', legacy([]));
    localStorage.setItem('chart-prefs:LT', legacy([{ id: 1, kind: 'nope' }]));
    const http = vi.fn();
    expect(await importLocalDrawings(http)).toBe(0);
    expect(http).not.toHaveBeenCalled();
  });
});
