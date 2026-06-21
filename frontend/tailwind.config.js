import defaultTheme from "tailwindcss/defaultTheme";

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  safelist: [
    { pattern: /^grid-cols-(3|4|5|6)$/ },
  ],
  theme: {
    extend: {
      fontFamily: {
        // Arabic fallback inserted before system-ui so RTL text renders correctly
        // without separate utility classes.
        display: ["\"Space Grotesk\"", "\"Noto Sans Arabic\"", ...defaultTheme.fontFamily.sans],
        body: ["\"Space Grotesk\"", "\"Noto Sans Arabic\"", ...defaultTheme.fontFamily.sans],
      },
      colors: {
        brand: {
          // Hardcoded hex (NOT CSS vars): Tailwind's /opacity syntax (bg-brand-secondary/10,
          // used widely in onboarding) requires a literal color, not a var() reference.
          primary: "#0F766E",
          secondary: "#F59E0B",
          surface: "#0B1C1A",
        },
      },
    },
  },
  plugins: [],
};
