/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        primary: '#3B82F6',
        'background-light': '#F3F4F6',
        'background-dark': '#111827',
        'card-light': '#FFFFFF',
        'card-dark': '#1F2937',
        'text-light': '#1F2937',
        'text-dark': '#F9FAFB'
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif']
      },
      boxShadow: {
        card: '0 10px 30px -12px rgba(0,0,0,0.15)'
      }
    }
  },
  plugins: []
};
