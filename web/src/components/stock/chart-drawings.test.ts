import { describe, expect, test } from 'vitest';
import {
  applyDrawingChanges,
  channelOffset,
  DRAWING_KINDS,
  DRAWING_LABELS,
  DRAWING_REQUIRED_POINTS,
  diffDrawings,
  fibExtensionLevels,
  inTriangle,
  pitchforkLines,
  hitTest,
  hitTestAll,
  moveDrawing,
  type ChartDrawing,
} from './chart-drawings';

const trend = { kind: 'trendline' as const, points: [{ x: 0, y: 0 }, { x: 100, y: 100 }] };

describe('hitTest', () => {
  test('an anchor wins over the line it sits on', () => {
    expect(hitTest('trendline', trend.points, { x: 2, y: 1 })).toBe(0);
    expect(hitTest('trendline', trend.points, { x: 99, y: 101 })).toBe(1);
  });

  test('a trendline is hit near the segment only, not its extension', () => {
    expect(hitTest('trendline', trend.points, { x: 50, y: 53 })).toBe('body');
    expect(hitTest('trendline', trend.points, { x: 50, y: 60 })).toBeNull();
    expect(hitTest('trendline', trend.points, { x: 150, y: 150 })).toBeNull();
  });

  test('a horizontal ray is hit to the right of its anchor only', () => {
    const ray = [{ x: 50, y: 40 }];
    expect(hitTest('horizontal', ray, { x: 400, y: 43 })).toBe('body');
    expect(hitTest('horizontal', ray, { x: 10, y: 40 })).toBeNull();
  });

  test('a rectangle is hit anywhere inside it', () => {
    const rect = [{ x: 10, y: 10 }, { x: 60, y: 90 }];
    expect(hitTest('rectangle', rect, { x: 30, y: 50 })).toBe('body');
    expect(hitTest('rectangle', rect, { x: 80, y: 50 })).toBeNull();
  });

  test('a Fibonacci tool is hit on a level line, not between levels', () => {
    const fib = [{ x: 0, y: 0 }, { x: 100, y: 100 }];
    expect(hitTest('fib', fib, { x: 50, y: 50 })).toBe('body'); // the 0.5 level
    expect(hitTest('fib', fib, { x: 50, y: 70 })).toBeNull();
  });

  test('off-screen anchors cannot be hit', () => {
    expect(hitTest('trendline', [null, { x: 100, y: 100 }], { x: 50, y: 50 })).toBeNull();
  });
});

test('hitTestAll picks the topmost (last drawn) drawing', () => {
  const both = [
    { id: 'under', ...trend },
    { id: 'over', ...trend },
  ];
  expect(hitTestAll(both, { x: 50, y: 50 })).toEqual({ id: 'over', part: 'body' });
  expect(hitTestAll(both, { x: 500, y: 0 })).toBeNull();
});

describe('moveDrawing', () => {
  const dates = ['2026-08-03', '2026-08-04', '2026-08-05', '2026-08-06', '2026-08-07'];
  const drawing: ChartDrawing = {
    id: 'd',
    kind: 'trendline',
    color: '#6366f1',
    points: [
      { date: '2026-08-04', price: 10 },
      { date: '2026-08-06', price: 20 },
    ],
  };

  test('moving the body shifts every anchor by bars and sets new prices', () => {
    expect(moveDrawing(drawing, 'body', 1, [11, 21], dates).points).toEqual([
      { date: '2026-08-05', price: 11 },
      { date: '2026-08-07', price: 21 },
    ]);
  });

  test('moving an anchor moves that anchor only', () => {
    expect(moveDrawing(drawing, 1, -2, [99, 25], dates).points).toEqual([
      { date: '2026-08-04', price: 10 },
      { date: '2026-08-04', price: 25 },
    ]);
  });

  test('a move past the loaded range clamps to the first or last bar', () => {
    expect(moveDrawing(drawing, 'body', 10, [10, 20], dates).points.map((p) => p.date)).toEqual([
      '2026-08-07',
      '2026-08-07',
    ]);
  });

  test('the original drawing is not mutated', () => {
    moveDrawing(drawing, 'body', 1, [0, 0], dates);
    expect(drawing.points[0]).toEqual({ date: '2026-08-04', price: 10 });
  });
});

describe('the M13 tools', () => {
  const ab = [{ x: 0, y: 0 }, { x: 100, y: 0 }];

  test('a ray reaches past its second anchor but not behind its first', () => {
    expect(hitTest('ray', ab, { x: 400, y: 3 })).toBe('body');
    expect(hitTest('ray', ab, { x: -50, y: 0 })).toBeNull();
  });

  test('an extended line reaches both ways', () => {
    expect(hitTest('extended', ab, { x: -400, y: 2 })).toBe('body');
    expect(hitTest('extended', ab, { x: 400, y: -2 })).toBe('body');
    expect(hitTest('extended', ab, { x: 50, y: 20 })).toBeNull();
  });

  test('horizontal, vertical and cross lines span the whole pane', () => {
    const at = [{ x: 50, y: 40 }];
    expect(hitTest('hline', at, { x: -900, y: 42 })).toBe('body');
    expect(hitTest('vline', at, { x: 52, y: 900 })).toBe('body');
    expect(hitTest('crossline', at, { x: 52, y: -900 })).toBe('body');
    expect(hitTest('crossline', at, { x: 900, y: 38 })).toBe('body');
    expect(hitTest('crossline', at, { x: 200, y: 200 })).toBeNull();
  });

  test('a channel is hit on either of its parallel lines', () => {
    const pts = [{ x: 0, y: 0 }, { x: 100, y: 100 }, { x: 50, y: 10 }]; // c sits 40 px above the a-b line
    expect(channelOffset(pts[0], pts[1], pts[2])).toEqual({ a: { x: 0, y: -40 }, b: { x: 100, y: 60 } });
    expect(hitTest('channel', pts, { x: 25, y: 26 })).toBe('body');
    expect(hitTest('channel', pts, { x: 75, y: 36 })).toBe('body');
    expect(hitTest('channel', pts, { x: 75, y: 55 })).toBeNull(); // between the lines, not on one
  });

  test('a price range is hit inside its box; a text note inside its label', () => {
    expect(hitTest('price_range', [{ x: 10, y: 10 }, { x: 60, y: 90 }], { x: 30, y: 50 })).toBe('body');
    expect(hitTest('text', [{ x: 100, y: 100 }], { x: 130, y: 95 }, 'Breakout')).toBe('body');
    expect(hitTest('text', [{ x: 100, y: 100 }], { x: 130, y: 120 }, 'Breakout')).toBeNull();
  });
});

describe('undo and redo', () => {
  const d = (id: string, price = 1): ChartDrawing => ({ id, kind: 'horizontal', color: '#6366f1', points: [{ date: '2026-08-03', price }] });

  test('a change records only the drawings it touched, and undoes and redoes exactly', () => {
    const before = [d('a'), d('b')];
    const after = [d('a', 5), d('b'), d('c')];
    const changes = diffDrawings(before, after);
    expect(changes.map((c) => c.id)).toEqual(['a', 'c']);
    expect(applyDrawingChanges(after, changes, 'before')).toEqual(before);
    expect(applyDrawingChanges(before, changes, 'after')).toEqual(after);
  });

  test('undo leaves alone what another window changed meanwhile', () => {
    const changes = diffDrawings([d('a')], [d('a', 5)]); // this window moved a
    const now = [d('a', 5), d('theirs', 9)]; // another window added a drawing since
    expect(applyDrawingChanges(now, changes, 'before')).toEqual([d('a'), d('theirs', 9)]);
  });

  test('undoing a delete brings the drawing back', () => {
    const changes = diffDrawings([d('a'), d('b')], [d('b')]);
    expect(applyDrawingChanges([d('b')], changes, 'before').map((x) => x.id).sort()).toEqual(['a', 'b']);
  });
});

describe('phase B3 tools', () => {
  test('every kind has a label and a point count, and labels are unique', () => {
    for (const kind of DRAWING_KINDS) {
      expect(DRAWING_LABELS[kind]).toBeTruthy();
      expect(DRAWING_REQUIRED_POINTS[kind]).toBeGreaterThan(0);
    }
    expect(new Set(Object.values(DRAWING_LABELS)).size).toBe(DRAWING_KINDS.length);
  });

  test('an arrow is hit on its shaft', () => {
    expect(hitTest('arrow', trend.points, { x: 50, y: 52 })).toBe('body');
    expect(hitTest('arrow', trend.points, { x: 50, y: 70 })).toBeNull();
  });

  test('an ellipse is hit inside its box ellipse, not in the box corners', () => {
    const box = [{ x: 0, y: 0 }, { x: 100, y: 50 }];
    expect(hitTest('ellipse', box, { x: 50, y: 25 })).toBe('body');
    expect(hitTest('ellipse', box, { x: 99, y: 25 })).toBe('body');
    expect(hitTest('ellipse', box, { x: 95, y: 3 })).toBeNull();
  });

  test('a triangle is hit inside or on an edge, in either winding', () => {
    const [a, b, c] = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 50, y: 80 }];
    expect(inTriangle({ x: 50, y: 30 }, a, b, c)).toBe(true);
    expect(inTriangle({ x: 50, y: 30 }, a, c, b)).toBe(true);
    expect(inTriangle({ x: 95, y: 70 }, a, b, c)).toBe(false);
    expect(hitTest('triangle', [a, b, c], { x: 50, y: 30 })).toBe('body');
    expect(hitTest('triangle', [a, b, c], { x: 0, y: 60 })).toBeNull();
    // Two anchors are not a triangle yet.
    expect(hitTest('triangle', [a, b], { x: 50, y: 1 })).toBeNull();
  });

  test('extension levels project the a→b move from c, by the standard ratios', () => {
    const levels = fibExtensionLevels({ x: 0, y: 100 }, { x: 50, y: 0 }, { x: 80, y: 60 });
    expect(levels.map((l) => [l.ratio, l.y])).toEqual([[0, 60], [0.618, 60 - 61.8], [1, -40], [1.272, 60 - 127.2], [1.618, 60 - 161.8], [2.618, 60 - 261.8]]);
    expect([levels.from, levels.to]).toEqual([80, 130]);
    expect(hitTest('fib_extension', [{ x: 0, y: 100 }, { x: 50, y: 0 }, { x: 80, y: 60 }], { x: 100, y: -40 })).toBe('body');
    expect(hitTest('fib_extension', [{ x: 0, y: 100 }, { x: 50, y: 0 }, { x: 80, y: 60 }], { x: 100, y: 20 })).toBeNull();
  });

  test('a pitchfork median runs from the pivot through the midpoint of the other two; tines are parallel rays', () => {
    const [a, b, c] = [{ x: 0, y: 50 }, { x: 40, y: 20 }, { x: 40, y: 80 }];
    const [median, upper, lower] = pitchforkLines(a, b, c);
    expect(median).toEqual({ start: a, dir: { x: 40, y: 0 } });
    expect([upper.start, lower.start]).toEqual([b, c]);
    expect(upper.dir).toEqual(median.dir);
    expect(hitTest('pitchfork', [a, b, c], { x: 300, y: 50 })).toBe('body'); // far along the median
    expect(hitTest('pitchfork', [a, b, c], { x: 300, y: 21 })).toBe('body'); // the upper tine
    expect(hitTest('pitchfork', [a, b, c], { x: 300, y: 35 })).toBeNull();
  });

  test('a callout is hit on its text box or leader; a price label on its tag', () => {
    const callout = [{ x: 10, y: 100 }, { x: 60, y: 40 }];
    expect(hitTest('callout', callout, { x: 80, y: 35 }, 'Base')).toBe('body');
    expect(hitTest('callout', callout, { x: 35, y: 70 }, 'Base')).toBe('body');
    expect(hitTest('callout', callout, { x: 10, y: 40 }, 'Base')).toBeNull();
    expect(hitTest('price_label', [{ x: 100, y: 100 }], { x: 130, y: 100 })).toBe('body');
    expect(hitTest('price_label', [{ x: 100, y: 100 }], { x: 80, y: 100 })).toBeNull();
  });

  test('date ranges are hit anywhere inside their box', () => {
    const box = [{ x: 10, y: 10 }, { x: 60, y: 90 }];
    expect(hitTest('date_range', box, { x: 30, y: 50 })).toBe('body');
    expect(hitTest('date_price_range', box, { x: 80, y: 50 })).toBeNull();
  });
});
