<template>
  <div class="space-y-4 px-4 py-4 ui-safe-bottom">
    <header class="ui-hero-stage ui-reveal overflow-hidden p-0">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.1fr),320px]">
        <div class="relative min-h-[240px] overflow-hidden rounded-[1.6rem] border border-slate-800/60 bg-slate-950/60 lg:min-h-[296px]">
          <img
            v-if="categoryImage"
            :src="categoryImage"
            :alt="categoryName"
            class="absolute inset-0 h-full w-full object-cover"
            loading="lazy"
          />
          <div class="absolute inset-0 bg-slate-950/76"></div>
          <div class="absolute inset-0 bg-gradient-to-br from-black/15 via-slate-950/60 to-black/80"></div>

          <div class="relative flex min-h-[240px] flex-col justify-end gap-3 p-4 lg:min-h-[296px] lg:p-5">
            <div class="flex flex-wrap gap-2">
              <span class="ui-chip-strong">{{ t("category.dishesAvailable", { count: dishes.length }) }}</span>
              <span v-if="cart.count" class="ui-chip">{{ t("common.cart") }} / {{ cart.count }}</span>
              <span v-if="hasSearch" class="ui-chip text-[var(--color-secondary)]">{{ search }}</span>
            </div>
            <div class="space-y-1.5">
              <p class="ui-kicker">{{ t("category.kicker") }}</p>
              <h1 class="ui-display text-3xl font-semibold capitalize text-white md:text-4xl">{{ categoryName }}</h1>
              <p class="max-w-2xl text-sm text-slate-200 md:text-base">{{ categoryDescription }}</p>
            </div>
          </div>
        </div>

        <aside class="ui-command-deck ui-reveal flex flex-col gap-4 p-4 lg:sticky lg:top-24 lg:h-fit lg:p-5" style="--ui-delay: 60ms">
          <div class="space-y-1.5">
            <p class="ui-kicker">{{ t("menu.kicker") }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t("category.helper") }}</h2>
            <p class="text-sm text-slate-300">{{ t("menu.intro") }}</p>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <article class="ui-admin-subcard">
              <p class="ui-stat-label">{{ t("customerLeadPage.dishes") }}</p>
              <p class="mt-2 text-2xl font-semibold text-white">{{ filteredDishes.length }}</p>
            </article>
            <article class="ui-admin-subcard">
              <p class="ui-stat-label">{{ t("common.cart") }}</p>
              <p class="mt-2 text-2xl font-semibold text-white">{{ cart.count }}</p>
            </article>
          </div>

          <label class="space-y-1 text-sm text-slate-200">
            {{ t("category.searchPlaceholder") }}
            <input
              v-model.trim="search"
              class="ui-input"
              :placeholder="t('category.searchPlaceholder')"
            />
          </label>

          <button v-if="hasSearch" class="ui-btn-outline justify-center" @click="search = ''">
            {{ t("common.clear") }}
          </button>

          <div class="space-y-2">
            <div class="flex items-center justify-between gap-2">
              <p class="ui-kicker">{{ t("dishPage.options") }}</p>
              <span class="ui-chip text-[10px]">{{ filteredDishes.length }}</span>
            </div>
            <div class="ui-scroll-row">
              <button
                v-for="filter in filterOptions"
                :key="filter.key"
                class="ui-pill-nav inline-flex items-center gap-2 whitespace-nowrap"
                :class="activeFilter === filter.key ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
                @click="activeFilter = filter.key"
              >
                <span>{{ filter.label }}</span>
                <span class="ui-chip bg-slate-950/75 text-[10px]">{{ filter.count }}</span>
              </button>
            </div>
          </div>

          <div class="space-y-2">
            <div class="flex items-center justify-between gap-2">
              <p class="ui-kicker">{{ t("common.categories") }}</p>
              <span class="ui-chip text-[10px]">{{ menuCategories.length }}</span>
            </div>
            <div class="ui-scroll-row">
              <RouterLink
                v-for="category in menuCategories"
                :key="category.slug"
                :to="{ name: 'category', params: { slug: category.slug } }"
                class="ui-pill-nav whitespace-nowrap"
                :data-active="category.slug === props.slug"
              >
                {{ category.name }}
              </RouterLink>
            </div>
          </div>

          <div class="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
            <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline justify-center">
              {{ t("customerLayout.navMenu") }}
            </RouterLink>
            <RouterLink :to="{ name: 'cart' }" class="ui-btn-outline justify-center">
              {{ t("customerLayout.navCart") }}
            </RouterLink>
            <RouterLink :to="{ name: 'reserve' }" class="ui-btn-primary justify-center">
              {{ t("customerLayout.navReserve") }}
            </RouterLink>
          </div>
        </aside>
      </div>
    </header>

    <section v-if="featuredDish" class="grid gap-3 xl:grid-cols-[minmax(0,1.08fr),320px]">
      <article class="ui-focus-card ui-reveal overflow-hidden p-0" style="--ui-delay: 90ms">
        <div class="grid gap-4 md:grid-cols-[220px,minmax(0,1fr)]">
          <div class="relative min-h-[220px] overflow-hidden rounded-[1.5rem] border border-slate-800/60 bg-slate-950/60">
            <img
              :src="featuredDish.image_url || placeholder"
              :alt="featuredDish.name"
              class="absolute inset-0 h-full w-full object-cover"
              loading="lazy"
            />
            <div class="absolute inset-0 bg-gradient-to-br from-slate-950/82 via-slate-950/56 to-slate-950/84"></div>
            <div class="relative flex min-h-[220px] flex-col justify-between p-4">
              <span class="ui-chip-strong">{{ t("category.viewDish") }}</span>
              <div class="space-y-1">
                <p class="ui-kicker">{{ t("customerLeadPage.stepOne") }}</p>
                <p class="text-xl font-semibold text-white">{{ featuredDish.name }}</p>
              </div>
            </div>
          </div>

          <div class="flex min-h-full flex-col justify-between gap-4 p-4 md:pr-5 md:pt-5">
            <div class="space-y-2">
              <div class="flex flex-wrap items-center gap-2">
                <span class="ui-chip">{{ categoryName }}</span>
                <span class="ui-chip">{{ formatCurrency(featuredDish.price, featuredDish.currency) }}</span>
                <span v-if="activeFilter !== 'all'" class="ui-chip text-[var(--color-secondary)]">{{ activeFilterLabel }}</span>
              </div>
              <h2 class="text-2xl font-semibold text-white">{{ featuredDish.name }}</h2>
              <p class="text-sm leading-relaxed text-slate-300">
                {{ featuredDish.description || t("dishPage.noDescription") }}
              </p>
            </div>

            <div class="flex flex-wrap gap-2">
              <RouterLink
                :to="{ name: 'dish', params: { category: props.slug, dish: featuredDish.slug } }"
                class="ui-btn-primary justify-center"
              >
                {{ t("category.viewDish") }}
              </RouterLink>
              <RouterLink :to="{ name: 'cart' }" class="ui-btn-outline justify-center">
                {{ t("customerLayout.navCart") }}
              </RouterLink>
            </div>
          </div>
        </div>
      </article>

      <aside class="ui-command-deck ui-reveal p-4 md:p-5" style="--ui-delay: 110ms">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("customerLeadPage.stepTwo") }}</p>
          <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.reserveTitle") }}</h2>
          <p class="text-sm text-slate-300">{{ t("customerLeadPage.reserveText") }}</p>
        </div>

        <div class="mt-4 grid gap-2">
          <RouterLink :to="{ name: 'reserve' }" class="ui-btn-primary justify-center">
            {{ t("customerLayout.navReserve") }}
          </RouterLink>
          <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline justify-center">
            {{ t("customerLayout.navMenu") }}
          </RouterLink>
          <RouterLink v-if="cart.count" :to="{ name: 'cart' }" class="ui-btn-outline justify-center">
            {{ t("customerLayout.navCart") }}
          </RouterLink>
        </div>
      </aside>
    </section>

    <div class="grid gap-4">
      <article
        v-for="(dish, index) in filteredDishes"
        :key="dish.slug"
        class="ui-orbit-card ui-surface-lift ui-reveal p-3 sm:p-4"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 30}ms` }"
      >
        <div class="grid gap-4 sm:grid-cols-[132px,minmax(0,1fr)] sm:items-start">
          <div class="relative overflow-hidden rounded-[1.3rem] border border-slate-800/70 bg-slate-950/70">
            <img :src="dish.image_url || placeholder" :alt="dish.name" class="h-36 w-full object-cover sm:h-[132px]" loading="lazy" />
            <div class="absolute inset-x-0 top-0 flex items-center justify-between p-2">
              <span class="ui-chip bg-slate-950/80 text-[10px]">{{ String(index + 1).padStart(2, "0") }}</span>
              <span v-if="dish.variants?.length" class="ui-chip bg-slate-950/80 text-[10px]">
                {{ t("dishPage.optionsCount", { count: dish.variants.length }) }}
              </span>
            </div>
          </div>

          <div class="flex min-h-full flex-col gap-3">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 space-y-1">
                <p class="truncate text-lg font-semibold text-white sm:text-xl">{{ dish.name }}</p>
                <p class="line-clamp-3 text-sm text-slate-300">{{ dish.description || t("dishPage.noDescription") }}</p>
              </div>
              <p class="shrink-0 text-lg font-semibold text-[var(--color-secondary)]">
                {{ formatCurrency(dish.price, dish.currency) }}
              </p>
            </div>

            <div class="mt-auto flex flex-wrap items-center gap-2">
              <span class="ui-data-strip">{{ categoryName }}</span>
              <span v-if="activeFilter !== 'all'" class="ui-data-strip text-[var(--color-secondary)]">{{ activeFilterLabel }}</span>
              <span v-if="cart.tableLabel" class="ui-data-strip">{{ t("customerLayout.table") }} {{ cart.tableLabel }}</span>
              <RouterLink
                :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }"
                class="ui-btn-outline ml-auto justify-center"
              >
                {{ t("category.viewDish") }}
              </RouterLink>
            </div>
          </div>
        </div>
      </article>
    </div>
    <div v-if="!menu.loading && !filteredDishes.length" class="ui-empty-state space-y-4 text-center">
      <div class="space-y-1">
        <p class="ui-kicker">{{ categoryName }}</p>
        <p class="text-lg font-semibold text-white">{{ t("category.noMatch") }}</p>
      </div>
      <div class="flex flex-wrap justify-center gap-2">
        <button class="ui-btn-outline justify-center" @click="search = ''">
          {{ t("common.clear") }}
        </button>
        <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline justify-center">
          {{ t("customerLayout.navMenu") }}
        </RouterLink>
        <RouterLink :to="{ name: 'reserve' }" class="ui-btn-primary justify-center">
          {{ t("customerLayout.navReserve") }}
        </RouterLink>
      </div>
    </div>
    <div v-if="filteredDishes.length > 1" class="ui-section-band space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ categoryName }}</p>
          <h2 class="text-xl font-semibold text-white">{{ t("category.helper") }}</h2>
        </div>
        <RouterLink :to="{ name: 'reserve' }" class="ui-btn-primary justify-center">
          {{ t("common.reserve") }}
        </RouterLink>
      </div>
      <div class="ui-scroll-row">
        <RouterLink
          v-for="dish in filteredDishes.slice(0, 8)"
          :key="`${dish.slug}-footer`"
          :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }"
          class="ui-chip"
        >
          {{ dish.name }}
        </RouterLink>
      </div>
    </div>
    <div v-if="menu.loading" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="n in 3"
        :key="`loading-${n}`"
        class="ui-skeleton h-44 rounded-[1.5rem]"
      ></div>
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

const props = defineProps({ slug: String });
const menu = useMenuStore();
const cart = useCartStore();
const { formatCurrency, t } = useI18n();
const search = ref("");
const activeFilter = ref("all");

const dishes = computed(() => menu.dishes[props.slug] || []);
const menuCategories = computed(() => (Array.isArray(menu.categories) ? menu.categories : []));
const currentCategory = computed(() => menuCategories.value.find((c) => c.slug === props.slug) || null);
const categoryName = computed(() => currentCategory.value?.name || props.slug);
const categoryDescription = computed(() => {
  const description = String(currentCategory.value?.description || "").trim();
  return description || t("category.helper");
});
const categoryImage = computed(() => String(currentCategory.value?.image_url || "").trim());
const hasSearch = computed(() => Boolean(search.value.trim()));
const filterOptions = computed(() => [
  { key: "all", label: categoryName.value, count: dishes.value.length },
  { key: "vegan", label: t("dishPage.vegan"), count: dishes.value.filter((dish) => dish.is_vegan).length },
  { key: "spicy", label: t("dishPage.spicy"), count: dishes.value.filter((dish) => dish.is_spicy).length },
  { key: "options", label: t("dishPage.options"), count: dishes.value.filter((dish) => Array.isArray(dish.options) && dish.options.length > 0).length },
]);
const activeFilterLabel = computed(() => filterOptions.value.find((filter) => filter.key === activeFilter.value)?.label || categoryName.value);
const filteredDishes = computed(() => {
  const term = search.value.toLowerCase();
  return dishes.value.filter((dish) => {
    const name = String(dish.name || "").toLowerCase();
    const description = String(dish.description || "").toLowerCase();
    const matchesSearch = !term || name.includes(term) || description.includes(term);
    if (!matchesSearch) return false;
    if (activeFilter.value === "vegan") return Boolean(dish.is_vegan);
    if (activeFilter.value === "spicy") return Boolean(dish.is_spicy);
    if (activeFilter.value === "options") return Array.isArray(dish.options) && dish.options.length > 0;
    return true;
  });
});
const featuredDish = computed(() => filteredDishes.value[0] || null);
const placeholder = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=600&q=80";

onMounted(() => {
  if (!menuCategories.value.length) menu.fetchCategories();
  menu.fetchDishesByCategory(props.slug);
});

watch(
  () => props.slug,
  (slug) => {
    if (!slug) return;
    activeFilter.value = "all";
    search.value = "";
    trackEvent("category_view", { source: "customer_category", category_slug: slug }, { onceKey: `category:${slug}` });
  },
  { immediate: true }
);
</script>
