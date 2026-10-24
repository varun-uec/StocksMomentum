import { describe, expect, it } from 'vitest';
import { COLOR_ROLES, THEMES, channels, roleName, tailwindColors, themeCss, type ColorTokens } from './themes';

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
    expect(css).toContain('--mf-brand-soft:217 242 230;');
    expect(tailwindColors()['loss']).toBe('rgb(var(--mf-loss) / <alpha-value>)');
  });

  it('keep every text role at WCAG AA contrast on its backgrounds', () => {
    const luminance = (hex: string) => {
      const [r, g, b] = channels(hex).split(' ').map((c) => {
        const v = Number(c) / 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const ratio = (a: string, b: string) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (hi + 0.05) / (lo + 0.05);
    };
    const text = ['ink', 'inkSoft', 'muted', 'brand', 'brandStrong', 'gain', 'loss', 'warning', 'info', 'accentInk'] as const;
    const pairs: [keyof ColorTokens, keyof ColorTokens][] = [
      ...text.flatMap((t) => (['surface', 'paper', 'sunken'] as const).map((bg) => [t, bg] as [keyof ColorTokens, keyof ColorTokens])),
      ['onBrand', 'brand'], ['brandStrong', 'brandSoft'], ['loss', 'lossSoft'], ['warning', 'warningSoft'], ['info', 'infoSoft'], ['accentInk', 'accentSoft'], ['ink', 'accentSoft'],
    ];
    for (const mode of ['light', 'dark'] as const)
      for (const [fg, bg] of pairs) expect(ratio(THEMES.paper[mode][fg], THEMES.paper[mode][bg]), `${mode} ${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5);
  });
});
