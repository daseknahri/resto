import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5180,
    proxy: {
      '/api': {
        target: 'https://daseknahri.menu.ibnbatoutaweb.com',
        changeOrigin: true,
        secure: true,
        cookieDomainRewrite: 'localhost',
      },
      '/api-auth': {
        target: 'https://daseknahri.menu.ibnbatoutaweb.com',
        changeOrigin: true,
        secure: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.{test,spec}.{js,ts}"],
    setupFiles: [],
  },
});
