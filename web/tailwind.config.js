/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Space Grotesk', 'Segoe UI', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 20px 60px rgba(0,0,0,0.45)',
      },
    },
  },
  plugins: [],
}

