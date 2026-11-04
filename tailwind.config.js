/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          500: '#1F4E79',
          600: '#163a5c',
          700: '#0f2942'
        }
      }
    },
  },
  plugins: [],
}
