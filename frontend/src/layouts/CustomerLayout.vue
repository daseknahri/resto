<template>
  <div class="ui-shell">
    <header class="ui-header">
      <div class="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-4 py-3">
        <RouterLink :to="{ name: 'customer-home' }" class="flex min-w-0 items-center gap-2.5">
          <img
            v-if="tenantLogo"
            :src="tenantLogo"
            :alt="`${tenantName} logo`"
            class="h-8 w-8 rounded-lg border border-slate-700/70 object-cover"
            loading="lazy"
          />
          <p class="truncate text-lg font-semibold text-slate-100">{{ tenantName }}</p>
        </RouterLink>

        <div class="flex items-center gap-2">
          <span v-if="cart.tableLabel" class="hidden ui-chip text-[10px] uppercase tracking-[0.15em] text-slate-300 md:inline-flex">
            {{ t("customerLayout.table") }} {{ cart.tableLabel }}
          </span>
          <LanguageSwitcher />
          <RouterLink to="/cart" class="relative inline-flex ui-touch-target min-w-[2.25rem] items-center justify-center rounded-full border border-slate-700/80 bg-slate-900/70 px-3 text-sm text-slate-100 hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]">
            {{ t("common.cart") }}
            <span
              v-if="cart.count"
              class="absolute -right-2 -top-2 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-[var(--color-secondary)] px-1 text-xs font-semibold text-slate-950"
            >
              {{ cart.count }}
            </span>
          </RouterLink>
        </div>
      </div>
    </header>

    <div v-if="tenantNotice" class="mx-auto w-full max-w-5xl px-4 pt-3">
      <div class="rounded-2xl border px-4 py-3 text-sm shadow-lg shadow-black/20" :class="tenantNotice.className">
        {{ tenantNotice.text }}
      </div>
    </div>

    <CustomerFlowRail />

    <main class="mx-auto w-full max-w-5xl pb-28 md:pb-8">
      <RouterView />
    </main>

    <section class="mx-auto w-full max-w-5xl px-4 pt-3 md:hidden">
      <div class="ui-hero-ribbon flex flex-wrap items-center gap-2 px-3 py-2.5 text-[11px] text-slate-300">
        <span class="ui-data-strip">{{ currentSectionLabel }}</span>
        <span v-if="cart.tableLabel" class="ui-data-strip">
          {{ t("customerLayout.table") }} {{ cart.tableLabel }}
        </span>
        <span class="ui-data-strip">{{ orderingModeLabel }}</span>
      </div>
    </section>

    <nav class="ui-bottom-dock md:hidden">
      <div class="ui-bottom-dock-grid grid-cols-4 text-xs">
        <RouterLink
          v-for="item in navItems"
          :key="item.key"
          :to="item.to"
          class="ui-press flex min-h-[3.1rem] flex-col items-center justify-center gap-1 rounded-2xl border px-2 py-2 text-center transition"
          :class="navItemClass(item.key)"
          :aria-current="activeCustomerSection === item.key ? 'page' : undefined"
        >
          <span class="text-[11px] font-semibold leading-none">{{ item.label }}</span>
          <span
            v-if="item.badge"
            class="rounded-full bg-[var(--color-secondary)] px-1.5 py-0.5 text-[10px] font-semibold leading-none text-slate-950"
          >
            {{ item.badge }}
          </span>
        </RouterLink>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import api from "../lib/api";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";
import CustomerFlowRail from "../components/CustomerFlowRail.vue";
import { useI18n } from "../composables/useI18n";
import { useCartStore } from "../stores/cart";
import { useTenantStore } from "../stores/tenant";

const cart = useCartStore();
const tenant = useTenantStore();
const route = useRoute();
const { t } = useI18n();

const meta = computed(() => tenant.resolvedMeta || null);
const tenantName = computed(() => meta.value?.name || t("customerLayout.fallbackTenantName"));
const tenantLogo = computed(() => String(meta.value?.profile?.logo_url || "").trim());
const orderingModeLabel = computed(() => {
  const mode = String(tenant.entitlements?.ordering_mode || "browse").toLowerCase();
  if (mode === "checkout") return t("customerLeadPage.checkout");
  if (mode === "whatsapp") return t("customerLeadPage.whatsapp");
  return t("customerLeadPage.browseOnly");
});

const activeCustomerSection = computed(() => {
  const name = String(route.name || "");
  if (name === "customer-home") return "info";
  if (name === "menu" || name === "category" || name === "dish") return "menu";
  if (name === "cart") return "cart";
  if (name === "reserve") return "reserve";
  return "info";
});

const currentSectionLabel = computed(() => {
  if (activeCustomerSection.value === "menu") return t("customerLayout.navMenu");
  if (activeCustomerSection.value === "cart") return t("customerLayout.navCart");
  if (activeCustomerSection.value === "reserve") return t("customerLayout.navReserve");
  return t("customerLayout.navInfo");
});

const navItems = computed(() => [
  { key: "info", label: t("customerLayout.navInfo"), to: { name: "customer-home" }, badge: "" },
  { key: "menu", label: t("customerLayout.navMenu"), to: { name: "menu" }, badge: "" },
  { key: "cart", label: t("customerLayout.navCart"), to: { name: "cart" }, badge: cart.count ? String(cart.count) : "" },
  { key: "reserve", label: t("customerLayout.navReserve"), to: { name: "reserve" }, badge: "" },
]);

const navItemClass = (key) =>
  activeCustomerSection.value === key
    ? "border-[var(--color-secondary)] bg-[var(--color-secondary)]/12 text-[var(--color-secondary)] shadow-lg shadow-black/30"
    : "border-slate-700/70 bg-slate-950/55 text-slate-300";

const tenantNotice = computed(() => {
  const profile = meta.value?.profile;
  if (!profile) return null;
  if (profile.is_menu_temporarily_disabled) {
    return {
      className: "border-red-500/40 bg-red-500/10 text-red-200",
      text: profile.menu_disabled_note || t("customerLayout.menuDisabledFallback"),
    };
  }
  if (profile.is_open === false) {
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

onMounted(syncTableFromQuery);
watch(() => route.query?.table, syncTableFromQuery);
watch(() => route.query?.t, syncTableFromQuery);
watch(() => route.params?.tableSlug, syncTableFromQuery);
</script>
