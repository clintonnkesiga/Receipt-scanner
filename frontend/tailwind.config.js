/** @type {import('tailwindcss').Config} */
export default {
  // Toggle dark mode via a `dark` class on <html> (managed in src/lib/theme.js
  // plus the no-flash init script in src/app.html).
  darkMode: "class",
  content: ["./src/**/*.{html,js,svelte}"],
  theme: { extend: {} },
  plugins: [],
};
