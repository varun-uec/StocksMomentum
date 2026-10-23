import type { Config } from 'tailwindcss';
import { chartPalette, colors } from './src/lib/theme';
import { tailwindColors } from './src/features/mf/theme/themes';

/**
 * Design tokens live in `src/lib/theme.ts` and are wired in here so the same
 * values drive Tailwind classes and inline chart styles.
 * Wickstreet's owned ink/paper and sea-green scales replace the corresponding
 * utility scales; components and runtime chart styles share the same source.
 * The MF workstation's `mf-*` colours read CSS variables from its own theme
 * config (src/features/mf/theme/themes.ts), so its themes swap at runtime.
 */
const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: { ...colors, chart: chartPalette, mf: tailwindColors() },
      fontFamily: { display: ['var(--mf-font-display)'] },
      borderRadius: { control: 'var(--mf-radius-control)', card: 'var(--mf-radius-card)', dialog: 'var(--mf-radius-dialog)' },
      boxShadow: { card: 'var(--mf-shadow-card)', raised: 'var(--mf-shadow-raised)' },
      fontSize: {
        pageTitle: ['1.5rem', { lineHeight: '2rem', fontWeight: '700' }],
        sectionTitle: ['1.125rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        cardTitle: ['0.875rem', { lineHeight: '1.25rem', fontWeight: '600' }],
        subHeading: ['0.875rem', { lineHeight: '1.25rem', fontWeight: '600' }],
        body: ['0.875rem', { lineHeight: '1.5rem' }],
        cardValue: ['1.25rem', { lineHeight: '1.75rem', fontWeight: '700' }],
        caption: ['0.75rem', { lineHeight: '1rem' }],
      },
    },
  },
  plugins: [],
};

export default config;
