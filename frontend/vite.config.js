import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";

// Emit a `<link rel="modulepreload">` in <head> for the code-split EN i18n
// message chunk. Cold-load win: without this, the browser only discovers the
// EN chunk when main.js *executes* its dynamic `import("./messages-en.js")` —
// i.e. after main.js and its whole static import graph have downloaded — adding
// ~1 network round-trip before first paint (main.js awaits ensureLocale("en")
// before mount()). The preload lets the browser start fetching the EN chunk in
// PARALLEL with main.js, so it's already in cache when the dynamic import runs.
//
// The runtime await in main.js is unchanged, so this can never cause a raw
// translation-key flash — it only makes the fetch start earlier. Fully
// defensive: if the EN chunk can't be located in the bundle, nothing is
// injected, so it can never break the build.
function preloadEnLocaleChunk() {
  let base = "/";
  return {
    name: "preload-en-locale-chunk",
    apply: "build",
    configResolved(config) {
      base = config.base || "/";
    },
    transformIndexHtml: {
      order: "post",
      handler(html, ctx) {
        const bundle = ctx.bundle;
        if (!bundle) return html; // dev server — no bundle to read.
        const enChunk = Object.values(bundle).find(
          (chunk) =>
            chunk.type === "chunk" &&
            typeof chunk.facadeModuleId === "string" &&
            chunk.facadeModuleId
              .replace(/\\/g, "/")
              .endsWith("/i18n/messages-en.js")
        );
        if (!enChunk) return html; // couldn't locate it — inject nothing.
        const normBase = base.endsWith("/") ? base : `${base}/`;
        return {
          html,
          tags: [
            {
              tag: "link",
              attrs: {
                rel: "modulepreload",
                // Match Vite's own module-preload/module-script tags so the
                // preload's CORS mode lines up with the actual import fetch
                // (module scripts always fetch in CORS mode) and is reused
                // rather than re-fetched.
                crossorigin: true,
                href: `${normBase}${enChunk.fileName}`,
              },
              injectTo: "head",
            },
          ],
        };
      },
    },
  };
}

export default defineConfig({
  plugins: [
    preloadEnLocaleChunk(),
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
