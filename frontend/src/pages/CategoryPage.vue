<template>
  <div class="space-y-3 px-3 py-3 pb-24 sm:space-y-4 sm:px-4 sm:py-4 ui-safe-bottom">
    <header class="ui-hero-stage ui-reveal overflow-hidden border border-slate-800/80 bg-slate-950/84 p-3 md:p-4">
      <div class="space-y-3">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div class="min-w-0 space-y-1">
            <p class="ui-kicker">{{ t("category.kicker") }}</p>
            <h1 class="ui-display text-2xl font-semibold capitalize text-white md:text-3xl">{{ categoryName }}</h1>
            <p class="max-w-2xl text-sm text-slate-300">{{ categoryDescription }}</p>
          </div>
          <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline shrink-0 px-3 py-1.5 text-xs">
            {{ t("customerLayout.navMenu") }}
          </RouterLink>
        </div>

        <div class="relative">
          <input v-model.trim="search" class="ui-input pr-12" :placeholder="t('category.searchPlaceholder')" />
          <button
            v-if="search"
            class="absolute right-2 top-1/2 -translate-y-1/2 rounded-full border border-slate-700/80 px-2 py-1 text-[11px] text-slate-300 hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]"
            @click="search = ''"
          >
            <span class="sr-only">{{ t("common.clear") }}</span>
            <svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
      </div>
    </header>

    <div class="grid gap-3">
      <article
        v-for="dish in filteredDishes"
        :key="dish.slug"
        class="ui-orbit-card ui-surface-lift ui-reveal p-3 sm:p-4"
      >
        <div class="grid gap-4 sm:grid-cols-[112px,minmax(0,1fr)] sm:items-start">
          <img :src="dish.image_url || placeholder" :alt="dish.name" class="h-28 w-full rounded-xl object-cover sm:h-[112px]" loading="lazy" />
          <div class="flex min-h-full flex-col gap-3">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 space-y-1">
                <p class="truncate text-lg font-semibold text-white">{{ dish.name }}</p>
                <p class="line-clamp-2 text-sm text-slate-300">{{ dish.description || t("dishPage.noDescription") }}</p>
              </div>
              <p class="shrink-0 text-lg font-semibold text-[var(--color-secondary)]">{{ formatCurrency(dish.price, dish.currency) }}</p>
            </div>

            <div class="mt-auto flex items-center justify-between gap-2">
              <button
                class="ui-btn-primary inline-flex items-center gap-2 px-3 py-2 text-sm"
                :disabled="quickAddDisabled"
                :class="quickAddDisabled ? 'cursor-not-allowed opacity-50' : ''"
                @click="addDishQuick(dish)"
              >
                <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" /></svg>
                <span>{{ t("dishPage.add") }}</span>
              </button>
              <RouterLink :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }" class="ui-btn-outline justify-center">
                {{ t("category.viewDish") }}
              </RouterLink>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div v-if="!menu.loading && !filteredDishes.length" class="ui-empty-state space-y-3 text-center">
      <p class="text-lg font-semibold text-white">{{ t("category.noMatch") }}</p>
      <div class="flex flex-wrap justify-center gap-2">
        <button class="ui-btn-outline justify-center" @click="search = ''">{{ t("common.clear") }}</button>
        <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline justify-center">{{ t("customerLayout.navMenu") }}</RouterLink>
      </div>
    </div>

    <div v-if="menu.loading" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="n in 3" :key="`loading-${n}`" class="ui-skeleton h-44 rounded-[1.5rem]"></div>
    </div>
    <p v-if="menu.error" class="text-sm text-red-400">{{ menu.error }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "../composables/useI18n";
import { trackEvent } from "../lib/analytics";
import { useCartStore } from "../stores/cart";
import { useMenuStore } from "../stores/menu";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const props = defineProps({ slug: String });
const menu = useMenuStore();
const cart = useCartStore();
const tenant = useTenantStore();
const toast = useToastStore();
const { currentLocale, formatCurrency, t } = useI18n();
const search = ref("");

const dishes = computed(() => menu.dishes[props.slug] || []);
const menuCategories = computed(() => (Array.isArray(menu.categories) ? menu.categories : []));
const currentCategory = computed(() => menuCategories.value.find((c) => c.slug === props.slug) || null);
const categoryName = computed(() => currentCategory.value?.name || props.slug);
const categoryDescription = computed(() => {
  const description = String(currentCategory.value?.description || "").trim();
  return description || t("category.helper");
});

const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const isRestaurantOpen = computed(() => tenant.resolvedMeta?.profile?.is_open !== false);
const quickAddDisabled = computed(() => isBrowseOnlyPlan.value || !isRestaurantOpen.value);

const filteredDishes = computed(() => {
  const term = search.value.toLowerCase();
  return dishes.value.filter((dish) => {
    const name = String(dish.name || "").toLowerCase();
    const description = String(dish.description || "").toLowerCase();
    return !term || name.includes(term) || description.includes(term);
  });
});

const placeholder = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=600&q=80";

const addDishQuick = (dish) => {
  if (isBrowseOnlyPlan.value) {
    toast.show(t("dishPage.orderingDisabledForPlan"), "info");
    return;
  }
  if (!isRestaurantOpen.value) {
    toast.show(t("dishPage.restaurantCurrentlyClosed"), "error");
    return;
  }

  const requiredOptions = Array.isArray(dish.options)
    ? dish.options.filter((opt) => Boolean(opt.is_required))
    : [];
  const optionIds = requiredOptions
    .map((opt) => Number(opt.id))
    .filter((id) => Number.isInteger(id) && id > 0)
    .sort((a, b) => a - b);
  const optionSig = optionIds.join(",");
  const extras = requiredOptions.reduce((sum, opt) => sum + Number(opt.price_delta || 0), 0);
  const unitPrice = Number(dish.price || 0) + extras;
  const note = requiredOptions.length
    ? `${t("dishPage.options")}: ${requiredOptions.map((opt) => opt.name).join(", ")}`
    : "";

  cart.add({
    key: `${dish.slug}::${optionSig}`,
    slug: dish.slug,
    name: dish.name,
    price: Number(unitPrice),
    currency: dish.currency,
    qty: 1,
    note,
    option_ids: optionIds,
    option_labels: requiredOptions.map((opt) => opt.name),
  });

  toast.show(t("dishPage.addedToCart"), "success");
};

onMounted(() => {
  if (!menuCategories.value.length) menu.fetchCategories();
});

watch(
  () => currentLocale.value,
  () => {
    if (!props.slug) return;
    menu.fetchCategories(true);
    menu.fetchDishesByCategory(props.slug, true);
  }
);

watch(
  () => props.slug,
  (slug) => {
    if (!slug) return;
    search.value = "";
    menu.fetchDishesByCategory(slug);
    trackEvent("category_view", { source: "customer_category", category_slug: slug }, { onceKey: `category:${slug}` });
  },
  { immediate: true }
);
</script>
