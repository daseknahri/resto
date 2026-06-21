<template>
  <div class="ui-shell">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[9999] focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white focus:outline-none focus:ring-2 focus:ring-brand-secondary">{{ t('common.skipToMain') }}</a>
    <header class="ui-header ui-reveal">
      <div class="mx-auto w-full max-w-6xl px-4 py-3.5 sm:px-5 sm:py-4">
          <div class="flex items-center justify-between gap-3">
            <RouterLink :to="{ name: 'customer-home' }" class="flex min-w-0 items-center gap-3">
              <img
                v-if="tenantLogo"
                :src="tenantLogo"
                :alt="`${tenantName} logo`"
                class="h-7 w-7 rounded-lg border border-slate-700/70 object-cover shadow-lg shadow-black/30 sm:h-9 sm:w-9"
                loading="eager"
                decoding="async"
                @error="$event.target.style.display='none'"
              />
              <div class="min-w-0">
                <p class="truncate text-base font-semibold text-slate-100 md:text-lg" :title="tenantName">{{ tenantName }}</p>
                <p v-if="tenantTagline" class="hidden truncate text-[10px] text-slate-400 md:block md:text-[11px]" :title="tenantTagline">{{ tenantTagline }}</p>
              </div>
            </RouterLink>

            <div class="flex items-center gap-2">
              <LanguageSwitcher compact dropdown />
              <CurrencySelector />
              <!-- Persistent in-app notification inbox (bell + unread badge) -->
              <NotificationBell />
              <!-- Driver-mode switch: only shown to users who are also drivers -->
              <RouterLink
                v-if="customerStore.customer?.is_driver"
                to="/driver"
                :aria-label="t('roleSwitch.driverMode')"
                class="ui-touch-target ui-press inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/8 px-2.5 py-1 text-[11px] font-semibold text-emerald-300 transition-colors hover:border-emerald-400/70 hover:bg-emerald-500/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950"
              >
                <AppIcon name="truck" class="h-3 w-3" aria-hidden="true" />
                <span class="hidden sm:inline">{{ t('roleSwitch.driverMode') }}</span>
              </RouterLink>
              <!-- Color scheme toggle -->
              <button
                class="ui-touch-target ui-press inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-700/60 bg-slate-900/70 text-slate-400 transition-colors hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)] focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950"
                type="button"
                :aria-label="t('customerLayout.toggleColorScheme')"
                :aria-pressed="colorScheme === 'system'"
                @click="toggleColorScheme"
              >
                <svg v-if="colorScheme === 'dark'" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5">
                  <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
                </svg>
                <svg v-else aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5">
                  <path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"/>
                </svg>
              </button>
              <!-- PWA install -->
              <button
                v-if="pwaCanInstall"
                class="ui-press inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-900/70 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)] focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950"
                type="button"
                :aria-label="t('customerLayout.installApp')"
                @click="pwaInstall"
              >
                <AppIcon name="download" class="h-3 w-3" aria-hidden="true" />
                {{ t('customerLayout.installApp') }}
              </button>
              <!-- sr-only live region announces cart count changes to screen readers -->
              <span class="sr-only" aria-live="polite" aria-atomic="true">
                {{ cart.count ? t('customerLayout.cartItems', { count: cart.count }) : '' }}
              </span>
              <RouterLink
                to="/cart"
                :aria-label="cart.count ? `${t('customerLayout.viewCart')} (${t('customerLayout.cartItems', { count: cart.count })})` : t('customerLayout.viewCart')"
                class="ui-touch-target ui-press relative inline-flex min-h-[2.75rem] min-w-[2.75rem] items-center justify-center rounded-full border border-slate-700/80 bg-slate-900/75 px-2 text-xs font-semibold text-slate-100 transition-colors hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)] focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950 sm:px-3 sm:text-sm"
              >
                <AppIcon name="cart" class="h-4 w-4 sm:hidden" aria-hidden="true" />
                <span class="hidden sm:inline" aria-hidden="true">{{ t("common.cart") }}</span>
                <span
                  v-show="cart.count"
                  aria-hidden="true"
                  class="absolute -end-2 -top-2 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-[var(--color-secondary)] px-1 text-xs font-semibold tabular-nums text-slate-950"
                >
                  {{ cart.count }}
                </span>
              </RouterLink>
            </div>
          </div>

        <div class="mt-2 hidden items-center justify-center gap-4 md:flex">
          <nav class="ui-segmented max-w-fit" :aria-label="t('customerLayout.navDesktop')">
            <RouterLink
              v-for="item in navItems"
              :key="`desktop-${item.key}`"
              :to="item.to"
              class="ui-segmented-button min-w-[7rem] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)] focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950"
              :data-active="activeCustomerSection === item.key"
              :aria-current="activeCustomerSection === item.key ? 'page' : undefined"
            >
              <AppIcon :name="item.icon" class="h-3.5 w-3.5" aria-hidden="true" />
              <span>{{ item.label }}</span>
              <span v-if="item.badge" aria-hidden="true" class="ms-2 rounded-full bg-[var(--color-secondary)] px-1.5 py-0.5 text-[10px] font-semibold text-slate-950">{{ item.badge }}</span>
              <span v-if="item.badge" class="sr-only">{{ t('customerLayout.signedIn') }}</span>
            </RouterLink>
          </nav>
        </div>
      </div>
    </header>

    <div v-if="tenantNotice" class="mx-auto w-full max-w-6xl px-4 pt-3">
      <div :role="tenantNotice.isError ? 'alert' : 'status'" class="ui-state-strip px-4 py-3 text-sm" :class="tenantNotice.className">
        {{ tenantNotice.text }}
      </div>
    </div>

    <!-- Track-order banner: shown when a recent in-app order exists and user is not on the order-status page -->
    <div v-if="trackBannerOrder" class="mx-auto w-full max-w-6xl px-4 pt-2">
      <div class="ui-panel-soft ui-reveal flex items-center justify-between border-[var(--color-secondary)]/30 bg-[var(--color-secondary)]/8 px-4 py-2.5">
        <RouterLink
          :to="{ name: 'order-status', params: { orderNumber: trackBannerOrder } }"
          class="flex min-w-0 items-center gap-2.5 text-sm font-semibold text-[var(--color-secondary)] hover:opacity-80"
        >
          <span aria-hidden="true" class="relative flex h-2.5 w-2.5 shrink-0">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--color-secondary)] opacity-50" />
            <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--color-secondary)]" />
          </span>
          <span class="truncate">{{ t("customerLayout.trackOrderBanner", { number: trackBannerOrder }) }}</span>
        </RouterLink>
        <button
          class="ui-touch-target ui-press ms-3 shrink-0 rounded-full p-1 text-slate-400 transition-colors hover:text-slate-200"
          :aria-label="t('customerLayout.trackOrderDismiss')"
          @click="dismissTrackBanner"
        >
          <AppIcon name="close" class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>

    <main id="main-content" tabindex="-1" class="mx-auto w-full max-w-6xl pb-24 md:pb-8">
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="ui-route" mode="out-in">
          <div :key="viewRoute.fullPath" class="ui-route-frame">
            <component :is="Component" />
          </div>
        </Transition>
      </RouterView>

      <!-- Super-app discovery: a tasteful "Kepoli · explore more" strip links the
           restaurant storefront back into the wider super-app (so tenant pages are
           no longer a dead-end), plus a Drive switch for drivers. Inside <main> so
           it inherits the bottom-dock clearance. -->
      <div class="px-4 pt-6">
        <div class="ui-panel-soft flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <RouterLink
            :to="{ name: 'super-app-hub' }"
            class="ui-touch-target inline-flex items-center gap-2 text-xs text-slate-400 transition-colors hover:text-slate-200"
          >
            <span class="font-semibold text-slate-300">{{ platformName }}</span>
            <span aria-hidden="true" class="text-slate-600">·</span>
            <span class="inline-flex items-center gap-1">
              {{ t('customerLayout.exploreKepoli') }}
              <AppIcon name="arrowRight" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" />
            </span>
          </RouterLink>
          <RouterLink
            v-if="customerStore.customer?.is_driver"
            to="/driver"
            :aria-label="t('roleSwitch.driverMode')"
            class="ui-btn-outline ui-touch-target inline-flex items-center gap-1.5 border-emerald-500/40 px-3 py-1.5 text-[11px] text-emerald-200 hover:border-emerald-400/70"
          >
            <AppIcon name="truck" class="h-3.5 w-3.5" aria-hidden="true" />
            <span>{{ t('roleSwitch.driverMode') }}</span>
          </RouterLink>
        </div>
      </div>
    </main>

    <nav class="ui-bottom-dock md:hidden" :aria-label="t('customerLayout.navMobile')">
      <div class="ui-bottom-dock-grid grid-cols-5 text-xs">
        <RouterLink
          v-for="item in navItems"
          :key="item.key"
          :to="item.to"
          class="ui-touch-target ui-press flex flex-col items-center justify-center gap-1 rounded-2xl border px-2 py-1.5 text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)] focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950"
          :class="navItemClass(item.key)"
          :aria-current="activeCustomerSection === item.key ? 'page' : undefined"
        >
          <AppIcon :name="item.icon" class="h-3.5 w-3.5" aria-hidden="true" />
          <span class="text-[11px] font-semibold leading-none">{{ item.label }}</span>
          <span
            v-if="item.badge"
            aria-hidden="true"
            class="tabular-nums rounded-full bg-[var(--color-secondary)] px-1.5 py-0.5 text-[10px] font-semibold leading-none text-slate-950"
          >{{ item.badge }}</span>
          <span v-if="item.badge" class="sr-only">{{ t('customerLayout.signedIn') }}</span>
        </RouterLink>
      </div>
    </nav>

    <!-- App-wide: surfaces a pending wallet-charge approval on any customer page. -->
    <ChargeApprovalWatcher />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import api from "../lib/api";
import { isRestaurantOpenNow } from "../lib/businessHours";
import { PLATFORM_NAME } from "../lib/brand";
import AppIcon from "../components/AppIcon.vue";
import ChargeApprovalWatcher from "../components/ChargeApprovalWatcher.vue";
import CurrencySelector from "../components/CurrencySelector.vue";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";
import NotificationBell from "../components/NotificationBell.vue";
import { useI18n } from "../composables/useI18n";
import { useInstallPrompt } from "../composables/useInstallPrompt";
import { useCustomerPush } from "../composables/useCustomerPush";
import { useCartStore } from "../stores/cart";
import { useCustomerStore } from "../stores/customer";
import { useCurrencyStore } from "../stores/currency";
import { useTenantStore } from "../stores/tenant";

const cart = useCartStore();
const customerStore = useCustomerStore();
const platformName = PLATFORM_NAME;
const currencyStore = useCurrencyStore();
const tenant = useTenantStore();
const route = useRoute();
const { currentLocale, t } = useI18n();
const { canInstall: pwaCanInstall, install: pwaInstall } = useInstallPrompt();

const meta = computed(() => tenant.resolvedMeta || null);
const tenantName = computed(() => meta.value?.name || t("customerLayout.fallbackTenantName"));
const tenantLogo = computed(() => String(meta.value?.profile?.logo_url || "").trim());
const tenantTagline = computed(() => String(meta.value?.profile?.tagline || meta.value?.profile?.description || "").trim());
const activeCustomerSection = computed(() => {
  const name = String(route.name || "");
  if (name === "customer-home") return "info";
  if (name === "menu" || name === "menu-browse" || name === "table-link" || name === "category" || name === "dish") return "menu";
  if (name === "cart") return "cart";
  if (name === "reserve") return "reserve";
  if (name === "customer-account" || name === "find-my-order") return "account";
  return "info";
});

const navItems = computed(() => [
  { key: "info", icon: "info", label: t("customerLayout.navInfo"), to: { name: "customer-home" }, badge: "" },
  { key: "menu", icon: "menu", label: t("customerLayout.navMenu"), to: { name: "menu" }, badge: "" },
  { key: "cart", icon: "cart", label: t("customerLayout.navCart"), to: { name: "cart" }, badge: cart.count ? String(cart.count) : "" },
  // Reservations are a restaurant-only capability — hide the tab for shops/pharmacies.
  ...(tenant.capabilities.reservations !== false
    ? [{ key: "reserve", icon: "calendar", label: t("customerLayout.navReserve"), to: { name: "reserve" }, badge: "" }]
    : []),
  { key: "account", icon: "user", label: t("customerLayout.navAccount"), to: { name: "customer-account" }, badge: customerStore.isAuthenticated ? "●" : "" },
]);

const navItemClass = (key) =>
  activeCustomerSection.value === key
    ? "border-[var(--color-secondary)] bg-[var(--color-secondary)]/12 text-[var(--color-secondary)] shadow-lg shadow-black/30"
    : "ui-nav-item-inactive";

const tenantNotice = computed(() => {
  const profile = meta.value?.profile;
  if (!profile) return null;
  if (profile.is_menu_temporarily_disabled) {
    return {
      isError: true,
      className: "border-red-500/40 bg-red-500/10 text-red-200",
      text: profile.menu_disabled_note || t("customerLayout.menuDisabledFallback"),
    };
  }
  // Server-authoritative verdict (tenant-local, schedule + closure aware) so this
  // storefront-wide banner agrees with the Menu/MenuSelect/Cart headers — was raw
  // is_open, which missed schedule-closed / closure-date restaurants. (temp-disable
  // is handled by its own branch above.)
  if (!isRestaurantOpenNow(profile)) {
    return {
      className: "border-amber-500/40 bg-amber-500/10 text-amber-200",
      text: t("customerLayout.closedNotice"),
    };
  }
  if (tenant.isBrowseOnlyPlan) {
    return {
      className: "border-sky-500/40 bg-sky-500/10 text-sky-200",
      text: t("customerLayout.browseOnlyNotice"),
    };
  }
  return null;
});

// ── Color scheme ─────────────────────────────────────────────────────────────
let _mqDark = null
const colorScheme = ref(
  (() => { try { return localStorage.getItem('ui-color-scheme') || 'dark' } catch { return 'dark' } })()
)

const applyColorScheme = () => {
  const restaurantTheme = meta.value?.profile?.menu_theme || 'light'
  if (colorScheme.value === 'system') {
    const osDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (osDark) document.documentElement.removeAttribute('data-menu-theme')
    else document.documentElement.setAttribute('data-menu-theme', restaurantTheme)
  } else {
    document.documentElement.removeAttribute('data-menu-theme')
  }
}

const toggleColorScheme = () => {
  colorScheme.value = colorScheme.value === 'dark' ? 'system' : 'dark'
  try { localStorage.setItem('ui-color-scheme', colorScheme.value) } catch { /* best-effort: ignore failures */ }
  applyColorScheme()
}

const _onOsThemeChange = () => { if (colorScheme.value === 'system') applyColorScheme() }
// ─────────────────────────────────────────────────────────────────────────────

// ── Track-order banner ────────────────────────────────────────────────────────
const ORDER_TRACK_TTL_MS = 2 * 60 * 60 * 1000; // 2 hours
const trackedOrderNumber = ref(null);
const trackedOrderAt = ref(0);

const loadOrderTracking = () => {
  try {
    trackedOrderNumber.value = localStorage.getItem('lastOrderNumber') || null;
    trackedOrderAt.value = Number(localStorage.getItem('lastOrderAt') || 0);
  } catch {
    trackedOrderNumber.value = null;
    trackedOrderAt.value = 0;
  }
};

const trackBannerOrder = computed(() => {
  if (!trackedOrderNumber.value) return null;
  if (route.name === 'order-status') return null;
  if (Date.now() - trackedOrderAt.value > ORDER_TRACK_TTL_MS) return null;
  return trackedOrderNumber.value;
});

const dismissTrackBanner = () => {
  try {
    localStorage.removeItem('lastOrderNumber');
    localStorage.removeItem('lastOrderAt');
  } catch { /* best-effort: ignore failures */ }
  trackedOrderNumber.value = null;
};
// ─────────────────────────────────────────────────────────────────────────────

const humanizeSlug = (value) =>
  String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const resolveTableFromSlug = async (tableSlug) => {
  const normalizedSlug = String(tableSlug || "").trim().toLowerCase();
  if (!normalizedSlug) return;
  try {
    const { data } = await api.get(`/table-context/${encodeURIComponent(normalizedSlug)}/`);
    const label = String(data?.label || "").trim();
    const slug = String(data?.slug || normalizedSlug).trim().toLowerCase();
    if (label) {
      cart.setTableContext(label, slug);
      return;
    }
  } catch {
    // Fallback to a humanized slug so cart still has useful context in degraded cases.
  }
  cart.setTableContext(humanizeSlug(normalizedSlug), normalizedSlug);
};

const syncTableFromQuery = async () => {
  const queryValue = route.query?.table ?? route.query?.t;
  const slugValue = route.params?.tableSlug;

  const normalizedSlug = Array.isArray(slugValue) ? "" : String(slugValue || "").trim().toLowerCase();
  if (Array.isArray(queryValue)) return;

  if (queryValue) {
    cart.setTableContext(String(queryValue).trim(), normalizedSlug);
    return;
  }

  if (!normalizedSlug) return;
  await resolveTableFromSlug(normalizedSlug);
};

const { autoRestore: pushAutoRestore, checkEnabled: pushCheckEnabled } = useCustomerPush();

onMounted(() => {
  loadOrderTracking();
  syncTableFromQuery();
  customerStore.fetchCustomer().then(() => {
    // Re-establish a previously-granted push subscription so charge nudges keep working.
    if (customerStore.isAuthenticated) {
      pushCheckEnabled().then((on) => { if (on) pushAutoRestore(); });
    }
  });
  currencyStore.fetchRates();
  applyColorScheme();
  _mqDark = window.matchMedia('(prefers-color-scheme: dark)')
  _mqDark.addEventListener('change', _onOsThemeChange)
});

onUnmounted(() => {
  _mqDark?.removeEventListener('change', _onOsThemeChange)
});
watch(() => route.query?.table, syncTableFromQuery);
watch(() => route.query?.t, syncTableFromQuery);
watch(() => route.params?.tableSlug, syncTableFromQuery);
// Re-read localStorage whenever leaving order-status so the banner appears immediately
watch(() => route.name, (name) => {
  if (name !== 'order-status') loadOrderTracking();
  // Re-apply color scheme on every route change so non-menu pages stay in sync
  applyColorScheme();
});
watch(
  () => currentLocale.value,
  () => {
    tenant.fetchMeta();
  }
);
</script>
