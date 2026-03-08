import defaultTheme from "tailwindcss/defaultTheme";

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["\"Space Grotesk\"", ...defaultTheme.fontFamily.sans],
        body: ["\"Space Grotesk\"", ...defaultTheme.fontFamily.sans],
      },
      colors: {
        brand: {
          primary: "#0F766E",
          secondary: "#F59E0B",
          surface: "#0B1C1A",
        },
      },
    },
  },
  plugins: [],
};
