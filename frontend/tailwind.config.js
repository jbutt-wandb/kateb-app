/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Custom dark theme colors (Obsidian-inspired)
        dark: {
          bg: '#1e1e2e',
          surface: '#282838',
          'surface-hover': '#313244',
          border: '#45475a',
          'text-primary': '#cdd6f4',
          'text-secondary': '#a6adc8',
          'text-muted': '#6c7086',
        },
        // Light theme colors
        light: {
          bg: '#f5f5f7',
          surface: '#ffffff',
          border: '#e5e5ea',
          'text-primary': '#1d1d1f',
          'text-secondary': '#6e6e73',
        },
        // Accent colors
        accent: {
          DEFAULT: '#8b5cf6',
          hover: '#a78bfa',
          muted: 'rgba(139, 92, 246, 0.15)',
          light: '#7c3aed',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
