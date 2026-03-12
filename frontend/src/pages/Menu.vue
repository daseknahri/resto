<template>
  <div class="space-y-3 px-4 py-3 pb-32 sm:pb-8 ui-safe-bottom">
    <header class="ui-glass ui-reveal overflow-hidden p-3 md:p-4">
      <div class="space-y-1.5">
        <p class="ui-kicker">{{ t("menu.kicker") }}</p>
        <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl">{{ tenantName }}</h1>
        <p class="text-sm text-slate-300">{{ t("menu.intro") }}</p>
      </div>

      <div class="mt-3 ui-divider"></div>
      <div class="mt-3 flex flex-wrap gap-2">
        <span class="ui-chip">{{ categories.length }} {{ t("common.categories") }}</span>
        <span class="ui-chip">{{ totalDishes }} {{ t("common.dishes") }}</span>
        <span class="ui-chip">{{ t("menu.mode") }}: {{ orderingModeLabel }}</span>
      </div>
    </header>

    <section
      class="ui-panel ui-reveal ui-surface-lift sticky top-[calc(var(--safe-top)+4.8rem)] z-10 space-y-3 p-3.5 md:static md:p-4"
      style="--ui-delay: 50ms"
    >
      <div class="grid gap-3 md:grid-cols-[1fr,auto] md:items-center">
        <div class="relative">
          <input v-model.trim="search" class="ui-input pr-12" :placeholder="t('menu.searchPlaceholder')" />
          <button
            v-if="search"
            class="absolute right-2 top-1/2 -translate-y-1/2 rounded-full border border-slate-700/80 px-2 py-1 text-[11px] text-slate-300 hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]"
            @click="clearSearch"
          >
            {{ t("common.clear") }}
          </button>
        </div>

        <div class="grid grid-cols-2 gap-2 text-xs text-slate-400 md:flex md:flex-wrap md:items-center">
          <button
            class="ui-pill-nav text-xs md:min-w-[7rem]"
            :class="sortBy === 'position' ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
            @click="sortBy = 'position'"
          >
            {{ t("menu.sortOrder") }}
          </button>
          <button
            class="ui-pill-nav text-xs md:min-w-[7rem]"
            :class="sortBy === 'count' ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
            @click="sortBy = 'count'"
          >
            {{ t("menu.sortItems") }}
          </button>
        </div>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <p>{{ t("menu.tip") }}</p>
        <p class="text-slate-400">{{ totalDishes }} {{ t("common.dishes") }}</p>
      </div>
    </section>

    <div class="grid gap-4 sm:grid-cols-2">
      <CategoryCard
        v-for="(cat, index) in categories"
        :key="cat.slug"
        :title="cat.name"
        :image="cat.image_url || placeholder"
        :count="cat.dishes?.length || 0"
        :index="index"
        @click="goToCategory(cat.slug)"
      />

      <div v-if="!menu.loading && !categories.length" class="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 text-slate-300 sm:col-span-2">
        <p class="font-semibold text-slate-100">{{ t("menu.noMatchTitle") }}</p>
        <p class="mt-1 text-sm text-slate-400">{{ t("menu.noMatchText") }}</p>
      </div>

      <div v-if="menu.loading" class="space-y-3 sm:col-span-2">
        <div v-for="n in 4" :key="n" class="h-48 animate-pulse rounded-3xl bg-slate-800/50"></div>
      </div>

      <p v-if="menu.error" class="text-sm text-red-400 sm:col-span-2">{{ menu.error }}</p>
    </div>

    <RouterLink
      v-if="cart.count"
      :to="{ name: 'cart' }"
      class="fixed bottom-20 left-3 right-3 z-20 flex items-center justify-between rounded-2xl border border-slate-700/80 bg-slate-950/92 px-4 py-3 text-sm text-slate-100 shadow-xl shadow-black/40 backdrop-blur sm:hidden"
    >
      <div>
        <p class="text-xs text-slate-400">{{ t("common.cart") }}</p>
        <p class="font-semibold">{{ itemCountLabel(cart.count) }}</p>
      </div>
      <p class="text-base font-semibold text-[var(--color-secondary)]">{{ formatCurrency(cart.total, cartCurrency) }}</p>
    </RouterLink>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import CategoryCard from "../components/CategoryCard.vue";
import { useI18n } from "../composables/useI18n";
import { trackEvent } from "../lib/analytics";
import { useCartStore } from "../stores/cart";
import { useMenuStore } from "../stores/menu";
import { useTenantStore } from "../stores/tenant";

const menu = useMenuStore();
const tenant = useTenantStore();
const cart = useCartStore();
const router = useRouter();
const { formatCurrency, t } = useI18n();

const search = ref("");
const sortBy = ref("position");
const placeholder = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80";
const meta = computed(() => tenant.resolvedMeta || null);
const menuCategories = computed(() => (Array.isArray(menu.categories) ? menu.categories : []));

const tenantName = computed(() => meta.value?.name || t("customerLayout.fallbackTenantName"));
const orderingModeLabel = computed(() => {
  const mode = String(tenant.entitlements?.ordering_mode || "browse").toLowerCase();
  if (mode === "checkout") return t("customerLeadPage.checkout");
  if (mode === "whatsapp") return t("customerLeadPage.whatsapp");
  return t("customerLeadPage.browseOnly");
});
const cartCurrency = computed(() => {
  const firstItemCurrency = cart.items.find((item) => item.currency)?.currency;
  return firstItemCurrency || meta.value?.plan?.currency || "USD";
});

const categories = computed(() => {
  const term = search.value.toLowerCase();
  const filtered = menuCategories.value.filter((cat) => {
    const name = String(cat.name || "").toLowerCase();
    return !term || name.includes(term);
  });

  const sorted = [...filtered];
  if (sortBy.value === "count") {
    sorted.sort((a, b) => (b.dishes?.length || 0) - (a.dishes?.length || 0));
  } else {
    sorted.sort((a, b) => (a.position || 0) - (b.position || 0));
  }
  return sorted;
});

const totalDishes = computed(() => categories.value.reduce((sum, cat) => sum + Number(cat?.dishes?.length || 0), 0));
const goToCategory = (slug) => router.push({ name: "category", params: { slug } });
const clearSearch = () => {
  search.value = "";
};

onMounted(async () => {
  if (!menuCategories.value.length) await menu.fetchCategories();
  trackEvent("menu_view", { source: "customer_menu_browse" });
});
</script>
