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

// Load EN (fallback) + the active locale in parallel before mount so:
//   1. The EN fallback catalog is always in catalog.en before first paint —
//      no raw translation-key strings are ever shown.
//   2. AR/FR visitors see their language immediately without a locale-switch flash.
// Both chunks are fetched in parallel; mount waits for both.
// A failed chunk fetch (flaky network) is swallowed — EN alone is enough to
// render the UI without raw keys, and the active locale can retry on next switch.
await Promise.all([
  ensureLocale("en"),
  localeStore.current !== "en" ? ensureLocale(localeStore.current) : Promise.resolve(),
]).catch(() => {});

initSentry(app);
app.mount("#app");
