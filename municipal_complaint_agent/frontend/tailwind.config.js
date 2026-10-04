/** @type {import('tailwindcss').Config} */
// Colors are CSS variables (see index.css) so dark mode swaps them in one place.
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cream: v('cream'),     // page background
        sand: v('sand'),       // borders / soft surfaces
        leaf: v('leaf'),       // accent
        forest: v('forest'),   // headings + primary fill
        ink: v('ink'),         // body text
        surface: v('surface'), // cards / inputs
        deep: v('deep'),       // always-dark panels (sidebar, footer)
        paper: v('paper'),     // light text on deep panels (constant)
        sandc: v('sandc'),     // soft text on deep panels (constant)
        crit: v('crit'),
        high: '#D9771A',
        med: '#C9A227',
        medtext: v('medtext'),
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        urdu: ['"Noto Nastaliq Urdu"', 'serif'],
      },
      boxShadow: { card: '0 1px 2px rgba(13,83,14,.06), 0 4px 16px rgba(13,83,14,.06)' },
    },
  },
  plugins: [],
}
