/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./public/index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}", // Scan Vue and JS files
  ],
  darkMode: 'class', // Enable dark mode using a class
  theme: {
    extend: {
      colors: {
        // Primary Palette (semantic names from CSS variables)
        'text-primary': 'var(--color-text-primary)', // Use CSS vars directly
        'text-secondary': 'var(--color-text-secondary)',
        'bg-primary': 'var(--color-bg-primary)',
        'bg-secondary': 'var(--color-bg-secondary)',
        'accent': 'var(--color-accent)',
        'accent-hover': 'var(--color-accent-hover)',
        'highlight': 'var(--color-highlight)',
        'border': 'var(--color-border)', // Simplified name

        // Utility/Brand Colors (direct hex for Tailwind, CSS vars manage dark/light)
        'brand-royal-purple': '#4B0082', // Same as light --color-accent
        'brand-gold': '#FFD700',         // Same as --color-highlight
        'brand-silver': '#C0C0C0',
        'brand-royal-blue': '#4169E1',
        'brand-dark-gold': '#B8860B',
        'brand-dark-blue': '#1F3A93',
        'brand-light-purple': '#9370DB', // Same as dark --color-accent
        'brand-success': '#27AE60',
        'brand-warning': '#E74C3C',
      },
      fontFamily: {
        sans: ['Poppins', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', '"Noto Sans"', 'sans-serif', '"Apple Color Emoji"', '"Segoe UI Emoji"', '"Segoe UI Symbol"', '"Noto Color Emoji"'],
        roboto: ['Roboto', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', '"Helvetica Neue"', 'Arial', '"Noto Sans"', 'sans-serif', '"Apple Color Emoji"', '"Segoe UI Emoji"', '"Segoe UI Symbol"', '"Noto Color Emoji"'],
      },
      backgroundImage: {
        // Add custom background images if needed
        'hero-pattern': "url('@/assets/background.png')",
      },
      zIndex: { // Add higher z-index values if needed
        '60': '60',
        '70': '70',
        '100': '100',
      }
    },
  },
  variants: {
    extend: {
        // Extend variants like 'opacity' for 'disabled' state etc.
        opacity: ['disabled'],
        cursor: ['disabled'],
    },
  },
  plugins: [
    // require('@tailwindcss/forms'), // Uncomment if using forms plugin
  ],
}

