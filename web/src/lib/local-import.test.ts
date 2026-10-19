import { beforeEach, describe, expect, test, vi } from 'vitest';
import { fillMissingCharts, importLocalDrawings, legacyCharts } from './local-import';
import { DEFAULT_CHART, DEFAULT_WORKSPACE } from './workspace';

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
    expect(JSON.parse(init.body)).toEqual({ price_basis: 'traded', drawings: [{ ...line, width: 2, text: null, locked: false, hidden: false, dash: 'solid' }] });
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

describe('legacyCharts', () => {
  const prefs = (timeframe: string, activeMas: number[], activePanes: string[] = []) =>
    JSON.stringify({ timeframe, activeMas, activePanes, drawings: [] });
  const sma = { uid: 'sma-x1y2z3', id: 'sma', params: { period: 30 } };

  test('each chart takes the setting chosen on the most symbols; untouched symbols do not vote', () => {
    const charts = legacyCharts([
      ['chart-prefs:A', prefs('MAX', [200, 20], ['rsi'])],
      ['chart-prefs:B', prefs('MAX', [20, 200], ['rsi'])],
      ['chart-prefs:C', prefs('6M', [50])],
      ['chart-prefs:D', prefs('1Y', [50, 200])],
      ['chart-prefs:E', prefs('1Y', [50, 200])],
      ['chart-prefs:F', prefs('1Y', [50, 200])],
      ['theme', 'dark'],
    ]);
    expect(Object.keys(charts).sort()).toEqual(['analysis', 'elliott-wave', 'main', 'stock']);
    expect(charts.stock).toEqual({ ...DEFAULT_CHART, range: 'MAX', mas: [20, 200], panes: ['rsi'] });
    expect(charts.main.symbol).toBeNull();
  });

  test('a tie is broken the same way every time', () => {
    const a = legacyCharts([['chart-prefs:A', prefs('MAX', [20])], ['chart-prefs:B', prefs('6M', [10])]]);
    const b = legacyCharts([['chart-prefs:B', prefs('6M', [10])], ['chart-prefs:A', prefs('MAX', [20])]]);
    expect(a).toEqual(b);
  });

  test('analysis indicators and preset go to the analysis chart only, with ids the server accepts', () => {
    const charts = legacyCharts([
      ['chart-overlays:A', JSON.stringify({ indicators: [sma, { id: 'gone' }], presetId: 'nope', showSignals: false, presetEdited: true })],
    ]);
    expect(Object.keys(charts)).toEqual(['analysis']);
    expect(charts.analysis.indicators).toEqual([{ id: 'sma', params: expect.objectContaining({ period: 30 }), uid: 'sma-1', hidden: false, color: null }]);
    expect(charts.analysis).toMatchObject({ show_signals: false, preset_edited: true, range: '1Y' });
  });

  test('nothing but defaults and broken values gives no charts', () => {
    expect(legacyCharts([['chart-prefs:A', prefs('1Y', [50, 200])], ['chart-prefs:B', '{not json'], ['chart-overlays:C', '[]']])).toEqual({});
  });

  test('out-of-range moving averages are dropped to fit the server schema', () => {
    const charts = legacyCharts([['chart-prefs:A', prefs('1Y', [5000, 1, 2, 3, 4, 5, 6, 7, 8, 9])]]);
    expect(charts.stock.mas).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  });
});

describe('fillMissingCharts', () => {
  const ws = { ...DEFAULT_WORKSPACE, charts: { stock: { ...DEFAULT_CHART, range: '6M' as const } } };

  test('adds only charts the server does not have; the server copy wins', () => {
    const next = fillMissingCharts(ws, { stock: { ...DEFAULT_CHART, range: 'MAX' }, main: { ...DEFAULT_CHART, range: 'MAX' } });
    expect(next.charts.stock.range).toBe('6M');
    expect(next.charts.main.range).toBe('MAX');
  });

  test('returns the same workspace when nothing is missing, so nothing is saved', () => {
    expect(fillMissingCharts(ws, { stock: DEFAULT_CHART })).toBe(ws);
  });
});
