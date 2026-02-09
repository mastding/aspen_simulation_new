/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        'aspen-dark': '#0f172a',
        'aspen-panel': '#1e293b'
      }
    },
  },
  plugins: [],
}