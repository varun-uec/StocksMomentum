import { describe, expect, it } from 'vitest';
import { initials } from './FundMark';

describe('initials', () => {
  it('skips generic words', () => {
    expect(initials('PPFAS Asset Management Pvt. Ltd.')).toBe('PP');
    expect(initials('Aditya Birla Sun Life AMC Limited')).toBe('AB');
    expect(initials('HDFC Asset Management Company Limited')).toBe('HD');
    expect(initials(null)).toBe('··');
  });
});
