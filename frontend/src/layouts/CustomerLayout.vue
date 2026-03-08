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
            Table {{ cart.tableLabel }}
          </span>
          <RouterLink to="/cart" class="relative inline-flex ui-touch-target min-w-[2.25rem] items-center justify-center rounded-full border border-slate-700/80 bg-slate-900/70 px-3 text-sm text-slate-100 hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]">
            Cart
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

    <nav class="fixed bottom-0 left-0 right-0 z-20 border-t border-slate-700/40 bg-slate-950/90 px-4 py-2 backdrop-blur-xl ui-safe-bottom md:hidden">
      <div class="mx-auto grid w-full max-w-5xl grid-cols-4 gap-2 text-xs text-slate-300">
        <RouterLink :to="{ name: 'customer-home' }" class="ui-chip ui-press justify-center py-2">Info</RouterLink>
        <RouterLink :to="{ name: 'menu' }" class="ui-chip ui-press justify-center py-2">Menu</RouterLink>
        <RouterLink to="/cart" class="ui-chip ui-press justify-center py-2">
          Cart
          <span v-if="cart.count" class="rounded-full bg-[var(--color-secondary)] px-1.5 py-0.5 text-[10px] font-semibold text-slate-900">{{ cart.count }}</span>
        </RouterLink>
        <RouterLink :to="{ name: 'reserve' }" class="ui-chip ui-press justify-center py-2">Reserve</RouterLink>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import api from "../lib/api";
import CustomerFlowRail from "../components/CustomerFlowRail.vue";
import { useCartStore } from "../stores/cart";
import { useTenantStore } from "../stores/tenant";

const cart = useCartStore();
const tenant = useTenantStore();
const route = useRoute();

const tenantName = computed(() => tenant.meta?.name || "Restaurant Menu");
const tenantLogo = computed(() => String(tenant.meta?.profile?.logo_url || "").trim());

const tenantNotice = computed(() => {
  const profile = tenant.meta?.profile;
  if (!profile) return null;
  if (profile.is_menu_temporarily_disabled) {
    return {
      className: "border-red-500/40 bg-red-500/10 text-red-200",
      text: profile.menu_disabled_note || "Menu is temporarily unavailable. Please try again later.",
    };
  }
  if (profile.is_open === false) {
    return {
      className: "border-amber-500/40 bg-amber-500/10 text-amber-200",
      text: "Restaurant is currently closed. You can still browse the menu.",
    };
  }
  if (tenant.isBrowseOnlyPlan) {
    return {
      className: "border-sky-500/40 bg-sky-500/10 text-sky-200",
      text: "Ordering is currently disabled for this restaurant plan. You can still browse the menu.",
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
  } catch (err) {
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
