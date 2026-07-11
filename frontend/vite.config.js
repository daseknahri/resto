import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.js",
      // usePushNotifications.js registers '/sw.js' manually — no auto-registration needed.
      injectRegister: null,
      // manifest-loader.js + backend serve the per-persona manifests — skip injection.
      manifest: false,
      injectManifest: {
        injectionPoint: "self.__WB_MANIFEST",
        // Precache all Vite-generated assets: JS chunks, CSS, HTML shell, icons.
        globPatterns: ["**/*.{js,css,html,ico,png,svg}"],
      },
      // Never activate in dev — push infra is prod-only.
      devOptions: { enabled: false },
    }),
  ],
  // Dev-only dependency pre-bundling. Pin esbuild's target to esnext so it does
  // NOT try to lower modern syntax (destructuring, etc.) to Vite's default
  // "modules" baseline (chrome87/es2020/…): esbuild 0.28.x — pinned via the
  // `overrides` below for a CVE fix — regressed that lowering and aborts dep
  // optimization with "Transforming destructuring … is not supported yet",
  // which crashes `vite dev` on startup (the browser is modern; no lowering is
  // needed here anyway, and `build.target` is already esnext).
  optimizeDeps: {
    esbuildOptions: {
      target: "esnext",
    },
  },
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
        // Function form lets us isolate large, stable packages (Sentry, Leaflet)
        // into their own named chunks so app-code deploys don't bust their cache.
        manualChunks(id) {
          if (id.includes('/node_modules/@sentry/')) return 'vendor-sentry';
          if (id.includes('/node_modules/leaflet/')) return 'vendor-leaflet';
          if (
            id.includes('/node_modules/vue/') ||
            id.includes('/node_modules/vue-router/') ||
            id.includes('/node_modules/pinia/')
          ) return 'vendor-vue';
          if (id.includes('/node_modules/axios/')) return 'vendor-http';
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
