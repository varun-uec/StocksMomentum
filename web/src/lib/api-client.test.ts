import { afterEach, describe, expect, it, vi } from 'vitest';
import { getAllRankings, getRun } from '@/lib/api-client';

afterEach(() => vi.unstubAllGlobals());

describe('getAllRankings', () => {
  it('reads every page of a run, in order, at the API page cap', async () => {
    const total = 450;
    const urls: string[] = [];
    vi.stubGlobal('fetch', async (url: string) => {
      urls.push(url);
      const params = new URL(url, 'http://x').searchParams;
      const [limit, offset] = [Number(params.get('limit')), Number(params.get('offset'))];
      const items = Array.from({ length: Math.max(0, Math.min(limit, total - offset)) }, (_, i) => ({ symbol: `S${offset + i}` }));
      return new Response(JSON.stringify({ run: null, items, total, limit, offset }), { status: 200 });
    });
    const all = await getAllRankings(7);
    expect(urls.map((u) => new URL(u, 'http://x').searchParams.get('offset'))).toEqual(['0', '200', '400']);
    expect(urls.every((u) => u.includes('/rankings/runs/7?limit=200'))).toBe(true);
    expect(all.items.map((i) => i.symbol)).toEqual(Array.from({ length: total }, (_, i) => `S${i}`));
    expect(all.total).toBe(total);
  });
});

describe('rate limiting', () => {
  it('waits for Retry-After and retries a read, then returns the data', async () => {
    vi.useFakeTimers();
    let calls = 0;
    vi.stubGlobal('fetch', async () => {
      calls += 1;
      if (calls < 3) return new Response('{}', { status: 429, headers: { 'Retry-After': '1' } });
      return new Response(JSON.stringify({ id: 5, status: 'completed' }), { status: 200 });
    });
    const pending = getRun(5);
    await vi.advanceTimersByTimeAsync(2500);
    expect((await pending).id).toBe(5);
    expect(calls).toBe(3);
    vi.useRealTimers();
  });

  it('gives up after two retries with the 429 error', async () => {
    vi.useFakeTimers();
    let calls = 0;
    vi.stubGlobal('fetch', async () => {
      calls += 1;
      return new Response('slow down', { status: 429, headers: { 'Retry-After': '1' } });
    });
    const pending = getRun(5).catch((e: Error) => e.message);
    await vi.advanceTimersByTimeAsync(5000);
    expect(await pending).toContain('API 429');
    expect(calls).toBe(3);
    vi.useRealTimers();
  });
});
