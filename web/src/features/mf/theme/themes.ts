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

/** Paper and ink with forest-green and sea-green accents (ui-ux doc 02). */
const paperAndInk: Theme = {
  label: 'Paper & ink',
  light: {
    paper: '#F6F5F0',
    surface: '#FFFFFF',
    sunken: '#F0EFE8',
    ink: '#172D27',
    inkSoft: '#34483F',
    muted: '#53675E',
    line: '#E2E5DD',
    lineStrong: '#C9D2C7',
    brand: '#176B55',
    brandStrong: '#0F5543',
    brandSoft: '#E3EFE7',
    onBrand: '#FFFFFF',
    brandAlt: '#2E8B74',
    heroFrom: '#EEF3EC',
    heroTo: '#F8F7F2',
    gain: '#176B55',
    loss: '#A64340',
    lossSoft: '#F7E6E3',
    warning: '#84581E',
    warningSoft: '#F6ECDC',
    info: '#3C6380',
    infoSoft: '#E5EDF3',
    focus: '#176B55',
    scrim: '#0A1410',
    chart1: '#176B55',
    chart2: '#976320',
    chart3: '#655A9B',
    chart4: '#356C8A',
    chart5: '#A34B65',
    chartBand: '#9CCDB8',
    chartGrid: '#E6E8E1',
  },
  dark: {
    paper: '#0F1C18',
    surface: '#162722',
    sunken: '#12211D',
    ink: '#EEF4EF',
    inkSoft: '#D2DED6',
    muted: '#AFC2B7',
    line: '#2A3F37',
    lineStrong: '#3A5045',
    brand: '#83D1B3',
    brandStrong: '#A2E5CB',
    brandSoft: '#1F3C31',
    onBrand: '#0B1915',
    brandAlt: '#5DBB9C',
    heroFrom: '#17302A',
    heroTo: '#0F1C18',
    gain: '#83D1B3',
    loss: '#FFAAA3',
    lossSoft: '#3A2422',
    warning: '#F0C47B',
    warningSoft: '#3A2F1C',
    info: '#A5CBE5',
    infoSoft: '#1E3140',
    focus: '#A2E5CB',
    scrim: '#000000',
    chart1: '#83D1B3',
    chart2: '#E0B061',
    chart3: '#B4A9EE',
    chart4: '#86BFE0',
    chart5: '#EE9AB4',
    chartBand: '#2F6B57',
    chartGrid: '#233730',
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

export const radii = { control: '8px', card: '14px', dialog: '18px' } as const;

export const shadows = {
  card: '0 1px 2px rgb(16 32 26 / 0.04), 0 1px 1px rgb(16 32 26 / 0.03)',
  raised: '0 12px 32px rgb(16 32 26 / 0.12), 0 2px 6px rgb(16 32 26 / 0.06)',
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
    `--mf-radius-control:${radii.control};--mf-radius-card:${radii.card};--mf-radius-dialog:${radii.dialog};` +
    `--mf-shadow-card:${shadows.card};--mf-shadow-raised:${shadows.raised};`;
  return (
    `.mf-root{color-scheme:light;${shared}${declarations(theme.light)}}` +
    `.dark .mf-root{color-scheme:dark;${declarations(theme.dark)}}`
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
