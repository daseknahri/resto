<template>
  <div class="space-y-4 px-4 py-4 ui-safe-bottom">
    <header class="ui-glass ui-reveal overflow-hidden p-4 md:p-5">
      <div>
        <p class="ui-kicker">Category</p>
        <h1 class="ui-display text-2xl font-semibold capitalize text-white md:text-3xl">{{ categoryName }}</h1>
        <p class="mt-1 text-sm text-slate-300">{{ filteredDishes.length }} dishes available</p>
      </div>
      <div class="mt-3 ui-divider"></div>
      <div class="mt-3 grid gap-3 md:grid-cols-[1fr,auto] md:items-center">
        <p class="text-sm text-slate-400">Tap any dish to view options, quantity, and pricing before adding to cart.</p>
        <input
          v-model.trim="search"
          class="ui-input"
          placeholder="Search dish in this category..."
        />
      </div>
    </header>

    <div class="grid gap-4">
      <article
        v-for="(dish, index) in filteredDishes"
        :key="dish.slug"
        class="ui-panel ui-surface-lift ui-reveal p-3 sm:p-4"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 30}ms` }"
      >
        <div class="flex flex-col gap-4 sm:flex-row">
          <img :src="dish.image_url || placeholder" :alt="dish.name" class="h-36 w-full rounded-2xl object-cover sm:h-24 sm:w-24" loading="lazy" />
          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="truncate text-lg font-semibold text-white">{{ dish.name }}</p>
                <p class="mt-0.5 line-clamp-2 text-sm text-slate-300">{{ dish.description }}</p>
              </div>
              <p class="font-semibold text-[var(--color-secondary)]">{{ formatPrice(dish.price, dish.currency) }}</p>
            </div>
            <RouterLink
              :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }"
              class="mt-3 inline-flex ui-touch-target items-center text-sm text-[var(--color-secondary)] hover:underline"
            >
              View dish details
            </RouterLink>
          </div>
        </div>
      </article>
    </div>
    <p v-if="!menu.loading && !filteredDishes.length" class="text-sm text-slate-400">No dishes match your search in this category.</p>
    <p v-if="menu.loading" class="text-sm text-slate-400">Loading dishes...</p>
    <p v-if="menu.error" class="text-sm text-red-400">{{ menu.error }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { trackEvent } from "../lib/analytics";
import { useMenuStore } from "../stores/menu";

const props = defineProps({ slug: String });
const menu = useMenuStore();
const search = ref("");

const dishes = computed(() => menu.dishes[props.slug] || []);
const categoryName = computed(() => menu.categories.find((c) => c.slug === props.slug)?.name || props.slug);
const filteredDishes = computed(() => {
  const term = search.value.toLowerCase();
  if (!term) return dishes.value;
  return dishes.value.filter((dish) => {
    const name = String(dish.name || "").toLowerCase();
    const description = String(dish.description || "").toLowerCase();
    return name.includes(term) || description.includes(term);
  });
});
const placeholder = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=600&q=80";

const formatPrice = (value, currency) => new Intl.NumberFormat("en", { style: "currency", currency: currency || "USD" }).format(value);

onMounted(() => {
  if (!menu.categories.length) menu.fetchCategories();
  menu.fetchDishesByCategory(props.slug);
});

watch(
  () => props.slug,
  (slug) => {
    if (!slug) return;
    trackEvent("category_view", { source: "customer_category", category_slug: slug }, { onceKey: `category:${slug}` });
  },
  { immediate: true }
);
</script>
