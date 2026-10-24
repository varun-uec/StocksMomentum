/**
 * The MF workstation's design tokens: the one place to change how it looks.
 *
 * Components never name a colour. They use the `mf-*` Tailwind colours and the
 * `--mf-*` CSS variables generated from these tokens, so a new theme is one more
 * entry in `THEMES`. Brand, semantic and chart colours are separate groups, and
 * typography, radii and shadows are independent of colour.
 */

/** Every colour role a theme defines, as a hex value. */
export interface ColorTokens {
  // Surfaces and ink
  paper: string; // page background
  surface: string; // cards, tables, dialogs
  sunken: string; // wells, table headers, inputs
  ink: string; // primary text
  inkSoft: string; // secondary text
  muted: string; // metadata; still AA on surface
  line: string; // dividers and grid
  lineStrong: string; // control outlines
  // Brand
  brand: string; // primary action, selection, evidence highlight
  brandStrong: string; // hover and pressed state of the brand colour
  brandSoft: string; // selected background
  onBrand: string; // text on the brand colour
  brandAlt: string; // second brand colour (sea green)
  heroFrom: string; // hero wash, top
  heroTo: string; // hero wash, bottom
  accent: string; // warm highlight: fills, markers, the hero glow; never body text
  accentSoft: string; // accent background behind ink text
  accentInk: string; // accent-coloured text
  // Semantic
  gain: string;
  loss: string;
  lossSoft: string;
  warning: string;
  warningSoft: string;
  info: string;
  infoSoft: string;
  focus: string;
  scrim: string; // dimmed page behind a dialog
  // Charts: up to five series, a band fill and the grid
  chart1: string;
  chart2: string;
  chart3: string;
  chart4: string;
  chart5: string;
  chartBand: string;
  chartGrid: string;
}

export interface Theme {
  label: string;
  light: ColorTokens;
  dark: ColorTokens;
}

/**
 * Wickstreet: clear paper, deep ink, a vivid emerald for action and gain, and a
 * saffron accent for highlights (ui-ux doc 02, 2026-10-24 refresh). Every text
 * role meets WCAG AA on surface, paper and sunken (themes.test.ts checks it).
 */
const paperAndInk: Theme = {
  label: 'Wickstreet',
  light: {
    paper: '#F3F6F4',
    surface: '#FFFFFF',
    sunken: '#ECF1EE',
    ink: '#0D1F1A',
    inkSoft: '#2B3F38',
    muted: '#56685F',
    line: '#DFE7E2',
    lineStrong: '#C2CFC8',
    brand: '#047857',
    brandStrong: '#065F46',
    brandSoft: '#D9F2E6',
    onBrand: '#FFFFFF',
    brandAlt: '#10A37F',
    heroFrom: '#D6F0E4',
    heroTo: '#F3F6F4',
    accent: '#E8890C',
    accentSoft: '#FFF1DC',
    accentInk: '#8A4B00',
    gain: '#0F7A45',
    loss: '#C0312B',
    lossSoft: '#FDE8E6',
    warning: '#965400',
    warningSoft: '#FDF0D9',
    info: '#2C5BA6',
    infoSoft: '#E5EDFA',
    focus: '#047857',
    scrim: '#06110D',
    chart1: '#047857',
    chart2: '#E8890C',
    chart3: '#5B5BD6',
    chart4: '#1D8BC4',
    chart5: '#D6457A',
    chartBand: '#A7E3C9',
    chartGrid: '#E6ECE8',
  },
  dark: {
    paper: '#08130F',
    surface: '#0F1E19',
    sunken: '#0B1814',
    ink: '#EAF5F0',
    inkSoft: '#C6D8D0',
    muted: '#98AFA5',
    line: '#1F322B',
    lineStrong: '#30483F',
    brand: '#34D399',
    brandStrong: '#6EE7B7',
    brandSoft: '#0F3A2C',
    onBrand: '#03130D',
    brandAlt: '#2BB88A',
    heroFrom: '#0F3A2C',
    heroTo: '#08130F',
    accent: '#F5A524',
    accentSoft: '#3A2A10',
    accentInk: '#FBBF4D',
    gain: '#4ADE80',
    loss: '#FF8578',
    lossSoft: '#3A1C19',
    warning: '#FBBF4D',
    warningSoft: '#3A2C12',
    info: '#8FB8F7',
    infoSoft: '#172846',
    focus: '#6EE7B7',
    scrim: '#000000',
    chart1: '#34D399',
    chart2: '#F5A524',
    chart3: '#A5A3FF',
    chart4: '#6CC4F0',
    chart5: '#F589B0',
    chartBand: '#1C5A46',
    chartGrid: '#1A2C26',
  },
};

/** A second palette that shows a theme swap needs no component change. */
const monsoon: Theme = {
  label: 'Monsoon',
  light: {
    ...paperAndInk.light,
    paper: '#F4F6F8',
    sunken: '#EDF0F3',
    ink: '#16243A',
    inkSoft: '#2F3E55',
    muted: '#536176',
    line: '#DFE4EA',
    lineStrong: '#C6CFDA',
    brand: '#2F5DA8',
    brandStrong: '#244A88',
    brandSoft: '#E4ECF8',
    brandAlt: '#3F7FBF',
    heroFrom: '#E8EEF6',
    heroTo: '#F6F8FA',
    gain: '#1F7A5A',
    focus: '#2F5DA8',
    chart1: '#2F5DA8',
    chartBand: '#A9C2E6',
    chartGrid: '#E4E8ED',
  },
  dark: {
    ...paperAndInk.dark,
    paper: '#0E1622',
    surface: '#151F2E',
    sunken: '#111A27',
    line: '#26344A',
    lineStrong: '#36475F',
    brand: '#93B6EE',
    brandStrong: '#B3CDF5',
    brandSoft: '#1E2D45',
    brandAlt: '#7FA8DC',
    heroFrom: '#17243A',
    heroTo: '#0E1622',
    focus: '#B3CDF5',
    chart1: '#93B6EE',
    chartBand: '#2C4A75',
    chartGrid: '#1F2B3D',
  },
};

export const THEMES = { paper: paperAndInk, monsoon } satisfies Record<string, Theme>;
export type ThemeId = keyof typeof THEMES;
export const DEFAULT_THEME: ThemeId = 'paper';

/** Type families. The display serif is a system font: no font request leaves the machine. */
export const typography = {
  display: "'Iowan Old Style', 'Palatino Linotype', Palatino, 'Book Antiqua', Georgia, serif",
  sans: "'Inter Variable', ui-sans-serif, system-ui, sans-serif",
} as const;

export const radii = { control: '10px', card: '16px', dialog: '20px' } as const;

/** Ink-tinted shadows in light; deeper, with a faint top edge, in dark. */
export const shadows = {
  light: {
    card: '0 1px 2px rgb(13 31 26 / 0.05), 0 6px 18px -10px rgb(13 31 26 / 0.12)',
    raised: '0 22px 44px -18px rgb(13 31 26 / 0.28), 0 4px 10px rgb(13 31 26 / 0.06)',
  },
  dark: {
    card: 'inset 0 1px 0 rgb(255 255 255 / 0.03), 0 8px 22px -12px rgb(0 0 0 / 0.7)',
    raised: 'inset 0 1px 0 rgb(255 255 255 / 0.05), 0 26px 52px -18px rgb(0 0 0 / 0.8)',
  },
} as const;

export const COLOR_ROLES = Object.keys(paperAndInk.light) as (keyof ColorTokens)[];

/** `brandSoft` → `brand-soft`: the CSS variable and Tailwind name of a role. */
export function roleName(role: string): string {
  return role.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`).replace(/(\D)(\d)/, '$1-$2');
}

/** `#176B55` → `23 107 85`, so Tailwind can add an alpha channel. */
export function channels(hex: string): string {
  const n = Number.parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}

function declarations(tokens: ColorTokens): string {
  return COLOR_ROLES.map((role) => `--mf-${roleName(role)}:${channels(tokens[role])};`).join('');
}

/** The stylesheet for one theme: light under `.mf-root`, dark under `.dark .mf-root`. */
export function themeCss(theme: Theme): string {
  const shared =
    `--mf-font-display:${typography.display};--mf-font-sans:${typography.sans};` +
    `--mf-radius-control:${radii.control};--mf-radius-card:${radii.card};--mf-radius-dialog:${radii.dialog};`;
  const shadow = (mode: 'light' | 'dark') => `--mf-shadow-card:${shadows[mode].card};--mf-shadow-raised:${shadows[mode].raised};`;
  return (
    `.mf-root{color-scheme:light;${shared}${shadow('light')}${declarations(theme.light)}}` +
    `.dark .mf-root{color-scheme:dark;${shadow('dark')}${declarations(theme.dark)}}`
  );
}

/** Tailwind colours that read the variables, e.g. `bg-mf-surface`, `text-mf-loss/70`. */
export function tailwindColors(): Record<string, string> {
  return Object.fromEntries(
    COLOR_ROLES.map((role) => [roleName(role), `rgb(var(--mf-${roleName(role)}) / <alpha-value>)`]),
  );
}

/** A chart series colour as a CSS value: series 0–4, then it repeats. */
export function seriesColor(index: number): string {
  return `rgb(var(--mf-chart-${(index % 5) + 1}))`;
}

/**
 * A tinted cell for heatmaps and matrices: `strength` 0–1 maps to alpha 0.06–0.40.
 * The cap keeps ink text at WCAG AA contrast on the tint in both light and dark.
 */
export function heat(role: keyof ColorTokens, strength: number): string {
  return token(role, 0.06 + 0.34 * Math.max(0, Math.min(1, strength)));
}

/** Any role as a CSS colour value, for SVG attributes and inline styles. */
export function token(role: keyof ColorTokens, alpha?: number): string {
  return alpha === undefined ? `rgb(var(--mf-${roleName(role)}))` : `rgb(var(--mf-${roleName(role)}) / ${alpha})`;
}
