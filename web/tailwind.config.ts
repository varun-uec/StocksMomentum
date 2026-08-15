import type { Config } from 'tailwindcss';
import { chartPalette } from './src/lib/theme';

/**
 * Design tokens live in `src/lib/theme.ts` and are wired in here so the same
 * values drive Tailwind classes and inline chart styles.
 * The slate/indigo/emerald/amber/rose/cyan/violet scales in `theme.ts` already
 * match Tailwind's defaults, so only the chart palette and the type scale map.
 */
const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: { chart: chartPalette },
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
