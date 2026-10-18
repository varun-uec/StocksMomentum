import { describe, expect, test } from 'vitest';
import { mergeById, mergeFields } from './merge';

const d = (id: string, price = 1) => ({ id, price });

describe('mergeById', () => {
  test('edits to different items both survive', () => {
    const base = [d('a'), d('b')];
    const mine = [d('a', 2), d('b')];
    const theirs = [d('a'), d('b', 3)];
    expect(mergeById(base, mine, theirs)).toEqual({ mine: [d('a', 2), d('b', 3)], theirs: [d('a', 2), d('b', 3)], conflicts: [] });
  });

  test('additions on both sides are kept: theirs first, then mine', () => {
    const r = mergeById([d('a')], [d('a'), d('m')], [d('a'), d('t')]);
    expect(r.mine.map((x) => x.id)).toEqual(['a', 't', 'm']);
    expect(r.conflicts).toEqual([]);
  });

  test('a delete on one side wins over an untouched item', () => {
    expect(mergeById([d('a'), d('b')], [d('b')], [d('a'), d('b')]).mine).toEqual([d('b')]);
    expect(mergeById([d('a'), d('b')], [d('a'), d('b')], [d('b')]).mine).toEqual([d('b')]);
  });

  test('the same edit on both sides is not a conflict', () => {
    expect(mergeById([d('a')], [d('a', 5)], [d('a', 5)]).conflicts).toEqual([]);
  });

  test('different edits to one item conflict and offer both versions', () => {
    const r = mergeById([d('a'), d('b')], [d('a', 2), d('b')], [d('a', 3), d('b', 4)]);
    expect(r.conflicts).toEqual(['a']);
    expect(r.mine).toEqual([d('a', 2), d('b', 4)]);
    expect(r.theirs).toEqual([d('a', 3), d('b', 4)]);
  });

  test('edit here and delete there conflict', () => {
    const r = mergeById([d('a')], [d('a', 2)], []);
    expect(r.conflicts).toEqual(['a']);
    expect(r.mine).toEqual([d('a', 2)]);
    expect(r.theirs).toEqual([]);
  });
});

describe('mergeFields', () => {
  const base = { symbol: 'TCS', range: '1Y', mas: [50], panes: [] as string[] };

  test('fields changed on one side each keep that side', () => {
    const mine = { ...base, range: 'MAX' };
    const theirs = { ...base, mas: [20, 50], panes: ['rsi'] };
    const r = mergeFields(base, mine, theirs);
    expect(r).toEqual({ mine: { ...base, range: 'MAX', mas: [20, 50], panes: ['rsi'] }, theirs: r.mine, conflicts: [] });
  });

  test('the same field changed differently is a conflict, never a silent overwrite', () => {
    const r = mergeFields(base, { ...base, mas: [20, 50] }, { ...base, mas: [] });
    expect(r.conflicts).toEqual(['mas']);
    expect(r.mine.mas).toEqual([20, 50]);
    expect(r.theirs.mas).toEqual([]);
  });

  test('the same change on both sides is not a conflict', () => {
    expect(mergeFields(base, { ...base, range: 'MAX' }, { ...base, range: 'MAX' }).conflicts).toEqual([]);
  });

  test('a latest-wins field takes this window\'s value without a conflict', () => {
    const r = mergeFields(base, { ...base, symbol: 'INFY' }, { ...base, symbol: 'SBIN' }, ['symbol']);
    expect(r).toEqual({ mine: { ...base, symbol: 'INFY' }, theirs: { ...base, symbol: 'INFY' }, conflicts: [] });
  });

  test('with no base, every field the two sides set differently conflicts', () => {
    const r = mergeFields(undefined, { ...base, range: 'MAX' }, base);
    expect(r.conflicts).toEqual(['range']);
  });

  test('with no server copy, mine stands', () => {
    expect(mergeFields(undefined, { a: 1 }, undefined)).toEqual({ mine: { a: 1 }, theirs: { a: 1 }, conflicts: [] });
  });
});
