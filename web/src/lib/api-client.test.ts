import { afterEach, describe, expect, it, vi } from 'vitest';
import { getAllRankings } from '@/lib/api-client';

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
