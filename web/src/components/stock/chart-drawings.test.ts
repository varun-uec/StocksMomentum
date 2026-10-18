import { describe, expect, test } from 'vitest';
import { hitTest, hitTestAll, moveDrawing, type ChartDrawing } from './chart-drawings';

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
