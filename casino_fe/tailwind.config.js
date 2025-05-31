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
        'royal-purple': '#4B0082', // Indigo-900 is close
        'gold': '#FFD700',          // Amber-400 is close
        'silver': '#C0C0C0',        // Gray-400 is close
        'royal-blue': '#4169E1',    // Blue-600 is close
        'dark-gold': '#B8860B',     // Amber-600 is close
        'dark-blue': '#1F3A93',     // Indigo-800 is close
        'light-purple': '#9370DB', // Violet-400 is close
        'success-green': '#27AE60', // Green-600
        'warning-red': '#E74C3C',   // Red-600
        'neutral-gray': '#95A5A6', // CoolGray-400 / Slate-400
        'dark-bg': '#1a1a2e',      // Example dark background
        'dark-card': '#16213e',    // Example dark card background
        'dark-text': '#e0e0e0',     // Example dark text color
      },
      fontFamily: {
        // Add Poppins and Roboto if needed, ensure they are imported via CSS or linked
        sans: ['Poppins', 'ui-sans-serif', 'system-ui'],
        body: ['Roboto', 'ui-sans-serif', 'system-ui'],
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

