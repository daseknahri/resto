<template>
  <div class="space-y-4 px-4 py-4 ui-safe-bottom">
    <header class="ui-hero-stage ui-reveal overflow-hidden p-3 md:p-4">
      <div class="relative overflow-hidden rounded-[1.4rem] border border-slate-800/60 bg-slate-950/60">
        <img
          v-if="categoryImage"
          :src="categoryImage"
          :alt="categoryName"
          class="absolute inset-0 h-full w-full object-cover opacity-35"
          loading="lazy"
        />
        <div class="relative space-y-2 p-4">
          <p class="ui-kicker">{{ t("category.kicker") }}</p>
          <h1 class="ui-display text-2xl font-semibold capitalize text-white md:text-3xl">{{ categoryName }}</h1>
          <p class="text-sm text-slate-300">{{ categoryDescription }}</p>
          <div class="flex flex-wrap gap-2">
            <span class="ui-chip-strong">{{ t("category.dishesAvailable", { count: filteredDishes.length }) }}</span>
            <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline px-3 py-1.5 text-xs">
              {{ t("customerLayout.navMenu") }}
            </RouterLink>
          </div>
        </div>
      </div>
    </header>

    <section class="ui-glass ui-reveal p-3 md:p-4" style="--ui-delay: 60ms">
      <div class="grid gap-3 md:grid-cols-[1fr,auto]">
        <input
          v-model.trim="search"
          class="ui-input"
          :placeholder="t('category.searchPlaceholder')"
        />
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
      <div class="mt-3 ui-scroll-row">
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
    </section>

    <div class="grid gap-4">
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
              <p class="shrink-0 text-lg font-semibold text-[var(--color-secondary)]">
                {{ formatCurrency(dish.price, dish.currency) }}
              </p>
            </div>

            <div class="mt-auto flex items-center justify-between gap-2">
              <span v-if="dish.variants?.length" class="ui-data-strip">
                {{ t("dishPage.optionsCount", { count: dish.variants.length }) }}
              </span>
              <RouterLink
                :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }"
                class="ui-btn-outline justify-center"
              >
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
import { useMenuStore } from "../stores/menu";

const props = defineProps({ slug: String });
const menu = useMenuStore();
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
