/** @type {import('tailwindcss').Config} */
export default {
  // Toggle dark mode via a `dark` class on <html> (managed in src/lib/theme.js
  // plus the no-flash init script in src/app.html).
  darkMode: "class",
  content: ["./src/**/*.{html,js,svelte}"],
  theme: {
    extend: {
      // Brand typeface — Commuza-style. Loaded in src/app.html.
      fontFamily: {
        sans: [
          "Poppins",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      // Primary palette remapped to the Commuza indigo (#3C5DAA). The app uses
      // `blue-*` as its primary throughout, so overriding the scale re-skins
      // every button / link / active state / focus ring at once. Deep navy
      // 800/900 match Commuza's heading/section tones.
      colors: {
        blue: {
          50: "#eef2fa",
          100: "#dbe4f4",
          200: "#bccdeb",
          300: "#7e9cd8",
          400: "#5378c4",
          500: "#4063ad",
          600: "#3c5daa",
          700: "#324e8f",
          800: "#243866",
          900: "#182544",
          950: "#0b1224",
        },
        // Explicit alias for future use / clarity.
        brand: {
          50: "#eef2fa",
          100: "#dbe4f4",
          200: "#bccdeb",
          300: "#7e9cd8",
          400: "#5378c4",
          500: "#4063ad",
          600: "#3c5daa",
          700: "#324e8f",
          800: "#243866",
          900: "#182544",
          950: "#0b1224",
        },
      },
      // Soft, slightly brand-tinted card shadow.
      boxShadow: {
        sm: "0 1px 2px 0 rgba(60, 93, 170, 0.06), 0 1px 3px 0 rgba(60, 93, 170, 0.08)",
      },
    },
  },
  plugins: [],
};
