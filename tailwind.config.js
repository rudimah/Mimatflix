/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./templates/**/*.html",
    "./static/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      colors: {
        primary: '#e50914',
        primaryHover: '#f40612',
        bgCard: '#18181b',
        bgBase: '#09090b',
      }
    }
  },
  plugins: [],
}