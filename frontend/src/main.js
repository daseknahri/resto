import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import { useLocaleStore } from "./stores/locale";
import { primeOwnerTheme } from "./composables/useOwnerTheme";
import { initSentry } from "./lib/sentry";
import { ensureLocale } from "./i18n/localeLoader";
import "./styles/tailwind.css";

const normalizeDevHost = () => {
  if (typeof window === "undefined") return;
  if (window.location.hostname !== "localhost") return;
  const apiBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_ADMIN_API_BASE_URL;
  if (!apiBase) return;
  try {
    const targetHost = new URL(apiBase).hostname;
    if (!targetHost || targetHost === "localhost" || !targetHost.endsWith(".localhost")) return;
    const targetUrl = `${window.location.protocol}//${targetHost}:${window.location.port}${window.location.pathname}${window.location.search}${window.location.hash}`;
    window.location.replace(targetUrl);
  } catch {
    // Ignore malformed env URL and keep current host.
  }
};

normalizeDevHost();

// Pre-paint the owner color scheme before mount to avoid a flash of the wrong
// theme on hard reloads of owner pages (no-op on non-owner routes).
if (typeof window !== "undefined") {
  primeOwnerTheme(window.location.pathname);
}

const pinia = createPinia();
const app = createApp(App);
app.use(pinia);
app.use(router);

const localeStore = useLocaleStore(pinia);
localeStore.bootstrap();

// Pre-load the active locale catalog so the first paint uses the right language.
// EN is already bundled synchronously; for FR/AR this kicks off a parallel fetch
// that resolves before or shortly after the first render without blocking mount.
// Fire-and-forget: swallow a failed chunk fetch (the UI falls back to EN strings)
// so it doesn't surface as an unhandledRejection / Sentry noise.
ensureLocale(localeStore.current).catch(() => {});

initSentry(app);
app.mount("#app");
