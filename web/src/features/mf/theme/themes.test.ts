import { describe, expect, it } from 'vitest';
import { COLOR_ROLES, THEMES, channels, roleName, tailwindColors, themeCss } from './themes';

describe('MF themes', () => {
  it('define every colour role as a hex value in light and dark', () => {
    for (const [id, theme] of Object.entries(THEMES))
      for (const mode of ['light', 'dark'] as const)
        for (const role of COLOR_ROLES) expect(theme[mode][role], `${id}.${mode}.${role}`).toMatch(/^#[0-9A-F]{6}$/i);
  });

  it('turn tokens into CSS variables and Tailwind colours with matching names', () => {
    expect(roleName('brandSoft')).toBe('brand-soft');
    expect(roleName('chart1')).toBe('chart-1');
    expect(channels('#176B55')).toBe('23 107 85');
    const css = themeCss(THEMES.paper);
    expect(css).toContain('.mf-root{');
    expect(css).toContain('.dark .mf-root{');
    expect(css).toContain('--mf-brand-soft:227 239 231;');
    expect(tailwindColors()['loss']).toBe('rgb(var(--mf-loss) / <alpha-value>)');
  });
});
