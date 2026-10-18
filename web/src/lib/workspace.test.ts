import { describe, expect, test } from 'vitest';
import { INDICATORS } from '@/lib/indicators/catalogue';
import { PRESETS } from '@/lib/strategies';
import { DRAWING_COLOR, DRAWING_KINDS, drawingId } from '@/components/stock/chart-drawings';
import { newUid } from '@/lib/overlay-preferences';
import { mergeWorkspaces, DEFAULT_CHART, type WorkspaceBody } from '@/lib/workspace';

// Copies of the server's patterns in backend/.../application/dto/user_documents.py.
// If this test fails, a value the web app saves would be rejected with 422.
const IDENTIFIER = /^[A-Za-z0-9_-]{1,64}$/;
const SHORT_NAME = /^[a-z0-9_]{1,32}$/;
const PARAM_NAME = /^[A-Za-z][A-Za-z0-9_]{0,31}$/;

describe('every value the web app saves fits the server schema', () => {
  test('catalogue indicator ids, instance ids and parameter keys', () => {
    for (const def of INDICATORS) {
      expect(def.id).toMatch(IDENTIFIER);
      expect(newUid(def.id)).toMatch(IDENTIFIER);
      expect(def.params.length).toBeLessThanOrEqual(16);
      for (const param of def.params) expect(param.key).toMatch(PARAM_NAME);
    }
  });

  test('signal preset ids', () => {
    for (const preset of PRESETS) expect(preset.id).toMatch(SHORT_NAME);
  });

  test('drawing ids, kinds and colour', () => {
    expect(drawingId()).toMatch(IDENTIFIER);
    for (const kind of DRAWING_KINDS) expect(kind).toMatch(SHORT_NAME);
    expect(DRAWING_COLOR).toMatch(/^#[0-9a-fA-F]{6}$/);
  });
});

describe('mergeWorkspaces', () => {
  const ws = (charts: WorkspaceBody['charts'], active: string | null = null): WorkspaceBody => ({ active_chart_id: active, right_panel: 'watchlist', charts });

  test('charts edited in different windows both survive', () => {
    const base = ws({ stock: DEFAULT_CHART });
    const mine = ws({ stock: { ...DEFAULT_CHART, range: 'MAX' } });
    const theirs = ws({ stock: DEFAULT_CHART, analysis: { ...DEFAULT_CHART, panes: ['rsi'] } });
    const r = mergeWorkspaces(base, mine, theirs);
    expect(r.conflicted).toBe(false);
    expect(r.mine.charts.stock.range).toBe('MAX');
    expect(r.mine.charts.analysis.panes).toEqual(['rsi']);
  });

  test('the same setting changed differently in two windows is a conflict', () => {
    const base = ws({ main: DEFAULT_CHART });
    const r = mergeWorkspaces(base, ws({ main: { ...DEFAULT_CHART, mas: [20, 50, 200] } }), ws({ main: { ...DEFAULT_CHART, mas: [200] } }));
    expect(r.conflicts).toEqual(['main.mas']);
    expect(r.mine.charts.main.mas).toEqual([20, 50, 200]);
    expect(r.theirs.charts.main.mas).toEqual([200]);
  });

  test('the open symbol and active chart follow the newest window, without a conflict', () => {
    const base = ws({ main: { ...DEFAULT_CHART, symbol: 'TCS' } }, 'stock');
    const mine = ws({ main: { ...DEFAULT_CHART, symbol: 'INFY' } }, 'main');
    const theirs = ws({ main: { ...DEFAULT_CHART, symbol: 'SBIN' } }, 'analysis');
    const r = mergeWorkspaces(base, mine, theirs);
    expect(r.conflicted).toBe(false);
    expect(r.mine.charts.main.symbol).toBe('INFY');
    expect(r.mine.active_chart_id).toBe('main');
  });

  test('two first saves of one chart: only changes from the defaults count', () => {
    const mine = ws({ main: { ...DEFAULT_CHART, symbol: 'TCS', mas: [20, 50, 200] } });
    const theirs = ws({ main: { ...DEFAULT_CHART, symbol: 'TCS' } });
    const r = mergeWorkspaces(null, mine, theirs);
    expect(r.conflicted).toBe(false);
    expect(r.mine.charts.main.mas).toEqual([20, 50, 200]);
    expect(mergeWorkspaces(null, mine, ws({ main: { ...DEFAULT_CHART, mas: [200] } })).conflicts).toEqual(['main.mas']);
  });

  test('the side panel is a setting: changed differently in two windows, it conflicts', () => {
    const base = ws({});
    const r = mergeWorkspaces(base, { ...base, right_panel: 'details' }, { ...base, right_panel: null });
    expect(r.conflicts).toEqual(['right_panel']);
    const clean = mergeWorkspaces(base, { ...base, right_panel: 'details' }, ws({ main: DEFAULT_CHART }));
    expect(clean.conflicted).toBe(false);
    expect(clean.mine.right_panel).toBe('details');
    expect(clean.mine.charts.main).toEqual(DEFAULT_CHART);
  });

  test('two first saves (no base) keep both sides charts', () => {
    const r = mergeWorkspaces(null, ws({ main: DEFAULT_CHART }, 'main'), ws({ stock: DEFAULT_CHART }, 'stock'));
    expect(Object.keys(r.mine.charts).sort()).toEqual(['main', 'stock']);
    expect(r.mine.active_chart_id).toBe('main');
    expect(r.conflicted).toBe(false);
  });
});
