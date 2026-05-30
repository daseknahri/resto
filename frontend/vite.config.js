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
  build: {
    // Target modern browsers — smaller bundles, no legacy transforms
    target: 'esnext',
    // Raise warning threshold slightly; our vendor chunk is intentionally large
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Split vendor code from app code so browser caches them independently.
        // vue/pinia/vue-router rarely change; axios/sentry less so.
        manualChunks: {
          'vendor-vue': ['vue', 'vue-router', 'pinia'],
          'vendor-http': ['axios'],
        },
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
